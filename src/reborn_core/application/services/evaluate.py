import re
import unicodedata
import uuid
from datetime import UTC, datetime

from reborn_core.application.models import (
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationCategory,
    EvaluationCategoryMetrics,
    EvaluationReport,
    EvaluationSuite,
    ModelMetadata,
    PromptMetadata,
)
from reborn_core.application.ports import EvaluationConversationPort
from reborn_core.core.exceptions import ConfigurationError
from reborn_core.observability import logger


class EvaluateRunner:
    """Runs deterministic safety and persona checks against isolated conversations."""

    def __init__(
        self,
        conversation: EvaluationConversationPort,
        model_metadata: ModelMetadata,
        prompt_metadata: PromptMetadata,
    ) -> None:
        self.conversation = conversation
        self.model_metadata = model_metadata
        self.prompt_metadata = prompt_metadata

    def run(self, suite: EvaluationSuite) -> EvaluationReport:
        """Run every case sequentially and require all cases to pass."""
        self._validate_suite(suite)
        started_at = datetime.now(UTC).isoformat()
        results = tuple(self._run_case(case) for case in suite.cases)
        completed_at = datetime.now(UTC).isoformat()
        passed_cases = sum(result.passed for result in results)
        total_cases = len(results)
        pass_rate = passed_cases / total_cases
        categories = self._category_metrics(results)
        return EvaluationReport(
            run_id=uuid.uuid4().hex,
            suite_id=suite.suite_id,
            suite_version=suite.version,
            model=self.model_metadata,
            prompt=self.prompt_metadata,
            started_at=started_at,
            completed_at=completed_at,
            results=results,
            categories=categories,
            passed_cases=passed_cases,
            total_cases=total_cases,
            pass_rate=pass_rate,
            passed=passed_cases == total_cases,
        )

    def _run_case(self, case: EvaluationCase) -> EvaluationCaseResult:
        total_rules = len(case.required_any) + len(case.forbidden)
        try:
            response, _ = self.conversation.generate_avatar_response(
                case.query,
                [
                    {"role": message["role"], "content": message["content"]}
                    for message in case.chat_history
                ],
                temperature=0.0,
                record_memory_gap=False,
            )
        except Exception as exc:
            logger.exception("Evaluation case {} failed during generation", case.case_id)
            return EvaluationCaseResult(
                case_id=case.case_id,
                category=case.category,
                response=None,
                passed_rules=0,
                total_rules=total_rules,
                score=0.0,
                passed=False,
                failed_rules=("response_generation",),
                error=f"{type(exc).__name__}: {exc}",
            )

        normalized_response = _normalize(response)
        failed_rules: list[str] = []
        passed_rules = 0
        for index, alternatives in enumerate(case.required_any, start=1):
            if any(_normalize(term) in normalized_response for term in alternatives):
                passed_rules += 1
            else:
                failed_rules.append(f"required_any[{index}]: {' | '.join(alternatives)}")
        for term in case.forbidden:
            if _normalize(term) in normalized_response:
                failed_rules.append(f"forbidden: {term}")
            else:
                passed_rules += 1

        score = passed_rules / total_rules
        return EvaluationCaseResult(
            case_id=case.case_id,
            category=case.category,
            response=response,
            passed_rules=passed_rules,
            total_rules=total_rules,
            score=score,
            passed=not failed_rules,
            failed_rules=tuple(failed_rules),
        )

    def _validate_suite(self, suite: EvaluationSuite) -> None:
        if not suite.suite_id.strip() or not suite.version.strip():
            raise ConfigurationError("Evaluation suite ID and version must not be empty")
        if suite.prompt_id != self.prompt_metadata.prompt_id:
            raise ConfigurationError(
                "Evaluation suite prompt does not match the configured prompt: "
                f"{suite.prompt_id} != {self.prompt_metadata.prompt_id}"
            )
        if not suite.cases:
            raise ConfigurationError("Evaluation suite must contain at least one case")

        case_ids: set[str] = set()
        for case in suite.cases:
            if not case.case_id.strip() or not case.query.strip():
                raise ConfigurationError("Evaluation case ID and query must not be empty")
            if case.case_id in case_ids:
                raise ConfigurationError(f"Duplicate evaluation case ID: {case.case_id}")
            case_ids.add(case.case_id)
            if not case.required_any and not case.forbidden:
                raise ConfigurationError(f"Evaluation case has no rules: {case.case_id}")
            if any(
                not group or any(not term.strip() for term in group) for group in case.required_any
            ):
                raise ConfigurationError(
                    f"Evaluation case has an empty required rule: {case.case_id}"
                )
            if any(not term.strip() for term in case.forbidden):
                raise ConfigurationError(
                    f"Evaluation case has an empty forbidden rule: {case.case_id}"
                )

    @staticmethod
    def _category_metrics(
        results: tuple[EvaluationCaseResult, ...],
    ) -> tuple[EvaluationCategoryMetrics, ...]:
        metrics: list[EvaluationCategoryMetrics] = []
        for category in EvaluationCategory:
            category_results = [result for result in results if result.category is category]
            if not category_results:
                continue
            passed_cases = sum(result.passed for result in category_results)
            metrics.append(
                EvaluationCategoryMetrics(
                    category=category,
                    passed_cases=passed_cases,
                    total_cases=len(category_results),
                    pass_rate=passed_cases / len(category_results),
                )
            )
        return tuple(metrics)


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", normalized).strip()
