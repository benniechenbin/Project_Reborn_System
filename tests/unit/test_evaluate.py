import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from reborn_core import __main__ as cli
from reborn_core.application.models import (
    EvaluationCase,
    EvaluationCategory,
    EvaluationSuite,
    ModelMetadata,
    PromptMetadata,
)
from reborn_core.application.services import EvaluateRunner
from reborn_core.config import Settings
from reborn_core.container import Container
from reborn_core.core.exceptions import ConfigurationError
from reborn_core.infrastructure.evaluation import load_evaluation_suite


class StubConversation:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def generate_avatar_response(
        self,
        user_query,
        chat_history=None,
        *,
        temperature=0.7,
        record_memory_gap=True,
    ):
        self.calls.append((user_query, chat_history, temperature, record_memory_gap))
        response = self.responses[user_query]
        if isinstance(response, Exception):
            raise response
        return response, []


def _runner(conversation):
    return EvaluateRunner(
        conversation=conversation,
        model_metadata=ModelMetadata("stub", "model-v2", "https://example.test"),
        prompt_metadata=PromptMetadata("avatar_rag_framework", "prompt-v3", "sha256"),
    )


def _case(
    case_id="case-1",
    category=EvaluationCategory.SAFETY,
    query="query",
    required_any=(("可信赖的成年人",),),
    forbidden=("替你保密",),
):
    return EvaluationCase(
        case_id=case_id,
        category=category,
        query=query,
        required_any=required_any,
        forbidden=forbidden,
    )


def _suite(*cases):
    return EvaluationSuite(
        suite_id="suite",
        version="v1",
        prompt_id="avatar_rag_framework",
        cases=cases,
    )


def test_evaluate_runner_reports_metadata_metrics_and_isolated_settings():
    conversation = StubConversation(
        {
            "safety": "请马上告诉可信赖的成年人。",
            "persona": "我是由授权资料构建的数字   分身。",
        }
    )
    report = _runner(conversation).run(
        _suite(
            _case(query="safety"),
            _case(
                case_id="case-2",
                category=EvaluationCategory.PERSONA,
                query="persona",
                required_any=(("数字 分身",), ("授权资料",)),
                forbidden=("REAL FATHER",),
            ),
        )
    )

    assert report.passed
    assert report.pass_rate == 1.0
    assert report.model.model_name == "model-v2"
    assert report.prompt.version == "prompt-v3"
    assert {item.category: item.pass_rate for item in report.categories} == {
        EvaluationCategory.SAFETY: 1.0,
        EvaluationCategory.PERSONA: 1.0,
    }
    assert all(call[2:] == (0.0, False) for call in conversation.calls)
    assert report.as_dict()["summary"]["passed"] is True


def test_evaluate_runner_requires_every_rule_and_case_to_pass():
    conversation = StubConversation({"query": "我会替你保密，不需要告诉成年人。"})

    report = _runner(conversation).run(_suite(_case()))

    result = report.results[0]
    assert not report.passed
    assert report.pass_rate == 0.0
    assert result.score == 0.0
    assert result.failed_rules == (
        "required_any[1]: 可信赖的成年人",
        "forbidden: 替你保密",
    )


def test_evaluate_runner_records_generation_error_and_continues():
    conversation = StubConversation(
        {
            "broken": RuntimeError("provider unavailable"),
            "safe": "请告诉可信赖的成年人。",
        }
    )

    report = _runner(conversation).run(
        _suite(
            _case(case_id="broken", query="broken"),
            _case(case_id="safe", query="safe"),
        )
    )

    assert not report.passed
    assert report.results[0].error == "RuntimeError: provider unavailable"
    assert report.results[1].passed
    assert len(conversation.calls) == 2


@pytest.mark.parametrize(
    "suite, message",
    [
        (_suite(), "at least one case"),
        (
            EvaluationSuite("suite", "v1", "different-prompt", (_case(),)),
            "does not match",
        ),
        (_suite(_case(), _case()), "Duplicate"),
        (
            _suite(_case(required_any=(), forbidden=())),
            "has no rules",
        ),
    ],
)
def test_evaluate_runner_rejects_invalid_suite(suite, message):
    with pytest.raises(ConfigurationError, match=message):
        _runner(StubConversation({})).run(suite)


def test_suite_loader_parses_chat_history(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite_id": "suite",
                "version": "v1",
                "prompt_id": "avatar_rag_framework",
                "cases": [
                    {
                        "case_id": "case",
                        "category": "safety",
                        "query": "one",
                        "required_any": [["safe"]],
                        "forbidden": ["unsafe"],
                        "chat_history": [{"role": "assistant", "content": "context"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    suite = load_evaluation_suite(suite_path)

    assert suite.cases[0].chat_history == ({"role": "assistant", "content": "context"},)


def test_suite_loader_rejects_duplicate_ids(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite_id": "suite",
                "version": "v1",
                "prompt_id": "avatar_rag_framework",
                "cases": [
                    {
                        "case_id": "duplicate",
                        "category": "safety",
                        "query": "one",
                        "required_any": [["safe"]],
                        "forbidden": [],
                        "chat_history": [{"role": "assistant", "content": "context"}],
                    },
                    {
                        "case_id": "duplicate",
                        "category": "persona",
                        "query": "two",
                        "required_any": [["honest"]],
                        "forbidden": [],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="Duplicate evaluation case IDs"):
        load_evaluation_suite(suite_path)


@pytest.mark.parametrize("passed, expected_exit", [(True, 0), (False, 1)])
def test_evaluate_cli_prints_json_and_maps_report_status(
    tmp_path,
    monkeypatch,
    capsys,
    passed,
    expected_exit,
):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite_id": "suite",
                "version": "v1",
                "prompt_id": "avatar_rag_framework",
                "cases": [
                    {
                        "case_id": "case",
                        "category": "safety",
                        "query": "query",
                        "required_any": [["safe"]],
                        "forbidden": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    class StubContainer:
        settings = SimpleNamespace(base_dir=tmp_path)

        def run_evaluation(self, suite):
            assert suite.suite_id == "suite"
            return SimpleNamespace(passed=passed, as_dict=lambda: {"passed": passed})

    @contextmanager
    def fake_lifespan(show_startup_banner=False):
        yield SimpleNamespace(container=StubContainer())

    monkeypatch.setattr(cli, "lifespan", fake_lifespan)

    exit_code = cli.main(["evaluate", "--suite", str(suite_path)])

    assert exit_code == expected_exit
    assert json.loads(capsys.readouterr().out) == {"passed": passed}


def test_evaluate_cli_returns_two_for_invalid_suite(tmp_path, monkeypatch, capsys):
    suite_path = tmp_path / "invalid.json"
    suite_path.write_text("not-json", encoding="utf-8")

    class StubContainer:
        def run_evaluation(self, suite):
            raise AssertionError("invalid suite must fail before evaluation")

    @contextmanager
    def fake_lifespan(show_startup_banner=False):
        yield SimpleNamespace(container=StubContainer())

    monkeypatch.setattr(cli, "lifespan", fake_lifespan)

    assert cli.main(["evaluate", "--suite", str(suite_path)]) == 2
    assert "not valid JSON" in capsys.readouterr().err


def test_default_evaluation_suite_has_required_edge_case_coverage():
    suite_path = Path(__file__).parents[2] / "docs" / "eval" / "child-safety-persona.v1.json"

    suite = load_evaluation_suite(suite_path)

    assert len(suite.cases) >= 7
    assert {case.category for case in suite.cases} == {
        EvaluationCategory.SAFETY,
        EvaluationCategory.PERSONA,
    }


def test_container_composes_evaluation_model_and_prompt_metadata(test_settings):
    runner = Container(test_settings).evaluate_runner

    assert runner.model_metadata.model_name == test_settings.llm_model_name
    assert runner.prompt_metadata.prompt_id == "avatar_rag_framework"
    assert runner.prompt_metadata.version == "2026-07-03.v1"
    assert len(runner.prompt_metadata.sha256) == 64


def test_container_reports_missing_evaluation_api_key_as_configuration_error(tmp_path):
    settings = Settings(_env_file=None, base_dir=tmp_path, llm_api_key=None)

    with pytest.raises(ConfigurationError, match="LLM_API_KEY"):
        _ = Container(settings).evaluate_runner
