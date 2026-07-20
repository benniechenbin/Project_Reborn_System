import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from reborn_core.application.models import (
    ChatMessage,
    EvaluationCase,
    EvaluationCategory,
    EvaluationSuite,
)
from reborn_core.core.exceptions import ConfigurationError


def load_evaluation_suite(path: Path) -> EvaluationSuite:
    """Load and validate a versioned evaluation suite from JSON."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(f"Could not read evaluation suite {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"Evaluation suite is not valid JSON: {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ConfigurationError("Evaluation suite root must be a JSON object")
    suite_id = _required_string(payload, "suite_id", "evaluation suite")
    version = _required_string(payload, "version", "evaluation suite")
    prompt_id = _required_string(payload, "prompt_id", "evaluation suite")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ConfigurationError("Evaluation suite cases must be a non-empty array")

    cases = tuple(_parse_case(item, index) for index, item in enumerate(raw_cases, start=1))
    duplicate_ids = _duplicates(case.case_id for case in cases)
    if duplicate_ids:
        raise ConfigurationError(
            f"Duplicate evaluation case IDs: {', '.join(sorted(duplicate_ids))}"
        )
    return EvaluationSuite(
        suite_id=suite_id,
        version=version,
        prompt_id=prompt_id,
        cases=cases,
    )


def _parse_case(payload: Any, index: int) -> EvaluationCase:
    location = f"evaluation case #{index}"
    if not isinstance(payload, dict):
        raise ConfigurationError(f"{location} must be a JSON object")
    case_id = _required_string(payload, "case_id", location)
    query = _required_string(payload, "query", location)
    category_value = _required_string(payload, "category", location)
    try:
        category = EvaluationCategory(category_value)
    except ValueError as exc:
        supported = ", ".join(item.value for item in EvaluationCategory)
        raise ConfigurationError(
            f"{location} has unsupported category {category_value!r}; expected {supported}"
        ) from exc

    required_any = _parse_required_groups(payload.get("required_any", []), location)
    forbidden = _parse_string_array(payload.get("forbidden", []), location, "forbidden")
    if not required_any and not forbidden:
        raise ConfigurationError(f"{location} must define at least one evaluation rule")
    chat_history = _parse_chat_history(payload.get("chat_history", []), location)
    return EvaluationCase(
        case_id=case_id,
        category=category,
        query=query,
        required_any=required_any,
        forbidden=forbidden,
        chat_history=chat_history,
    )


def _parse_required_groups(value: Any, location: str) -> tuple[tuple[str, ...], ...]:
    if not isinstance(value, list):
        raise ConfigurationError(f"{location} required_any must be an array of arrays")
    groups: list[tuple[str, ...]] = []
    for index, group in enumerate(value, start=1):
        if not isinstance(group, list) or not group:
            raise ConfigurationError(
                f"{location} required_any group #{index} must be a non-empty array"
            )
        groups.append(_parse_string_array(group, location, f"required_any group #{index}"))
    return tuple(groups)


def _parse_string_array(value: Any, location: str, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ConfigurationError(f"{location} {field_name} must be an array")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ConfigurationError(f"{location} {field_name} entries must be non-empty strings")
        items.append(item.strip())
    return tuple(items)


def _parse_chat_history(value: Any, location: str) -> tuple[ChatMessage, ...]:
    if not isinstance(value, list):
        raise ConfigurationError(f"{location} chat_history must be an array")
    history: list[ChatMessage] = []
    for index, message in enumerate(value, start=1):
        if not isinstance(message, dict):
            raise ConfigurationError(f"{location} chat_history item #{index} must be an object")
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str) or not content.strip():
            raise ConfigurationError(
                f"{location} chat_history item #{index} requires role user/assistant "
                "and non-empty content"
            )
        history.append({"role": role, "content": content})
    return tuple(history)


def _required_string(payload: dict[str, Any], key: str, location: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{location} {key} must be a non-empty string")
    return value.strip()


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates
