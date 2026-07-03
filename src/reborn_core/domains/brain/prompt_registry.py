import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from string import Formatter
from typing import Any


class PromptRegistryError(ValueError):
    """Raised when a prompt template cannot be loaded or rendered safely."""


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    prompt_id: str
    version: str
    role: str
    variables: tuple[str, ...]
    template: str
    path: Path
    template_sha256: str

    def as_message(self) -> dict[str, str]:
        return {"role": self.role, "content": self.template}


@dataclass(frozen=True, slots=True)
class RenderedPrompt:
    prompt_id: str
    version: str
    role: str
    content: str
    sha256: str
    path: Path

    def as_message(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class PromptRegistry:
    """Loads versioned Markdown prompt templates and renders explicit variables."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).with_name("prompts")
        self._templates: dict[str, PromptTemplate] | None = None
        self._snapshot: dict[Path, int] | None = None

    def load(self, prompt_id: str) -> PromptTemplate:
        templates = self._load_all()
        try:
            return templates[prompt_id]
        except KeyError as exc:
            raise PromptRegistryError(f"Prompt not found: {prompt_id}") from exc

    def render(self, prompt_id: str, variables: dict[str, Any] | None = None) -> RenderedPrompt:
        template = self.load(prompt_id)
        values = variables or {}
        self._validate_variables(template, values)
        rendered = _render_template(template.template, template.variables, values)
        return RenderedPrompt(
            prompt_id=template.prompt_id,
            version=template.version,
            role=template.role,
            content=rendered,
            sha256=_sha256(rendered),
            path=template.path,
        )

    def message(self, prompt_id: str, variables: dict[str, Any] | None = None) -> dict[str, str]:
        return self.render(prompt_id, variables).as_message()

    def render_from_context(self, prompt_id: str, context: dict[str, Any]) -> RenderedPrompt:
        template = self.load(prompt_id)
        unsupported = sorted(set(template.variables) - set(context))
        if unsupported:
            raise PromptRegistryError(
                f"Prompt {prompt_id} declares variables not provided by caller context: "
                f"{', '.join(unsupported)}"
            )
        variables = {name: context[name] for name in template.variables}
        return self.render(prompt_id, variables)

    def _load_all(self) -> dict[str, PromptTemplate]:
        current_snapshot = _prompt_file_snapshot(self.root)
        if self._templates is not None and self._snapshot == current_snapshot:
            return self._templates
        if not self.root.exists():
            raise PromptRegistryError(f"Prompt directory does not exist: {self.root}")

        templates: dict[str, PromptTemplate] = {}
        for path in current_snapshot:
            template = _load_template(path)
            if template.prompt_id in templates:
                raise PromptRegistryError(f"Duplicate prompt_id: {template.prompt_id}")
            templates[template.prompt_id] = template
        self._templates = templates
        self._snapshot = current_snapshot
        return templates

    @staticmethod
    def _validate_variables(template: PromptTemplate, values: dict[str, Any]) -> None:
        allowed = set(template.variables)
        provided = set(values)
        extra = sorted(provided - allowed)
        if extra:
            raise PromptRegistryError(
                f"Prompt {template.prompt_id} received undeclared variables: {', '.join(extra)}"
            )

        missing = [
            name
            for name in template.variables
            if name not in values or values[name] is None or str(values[name]).strip() == ""
        ]
        if missing:
            env_names = ", ".join(name.upper() for name in missing)
            raise PromptRegistryError(
                f"Prompt {template.prompt_id} is missing required variables: {env_names}"
            )


@lru_cache(maxsize=1)
def get_prompt_registry() -> PromptRegistry:
    return PromptRegistry()


def _load_template(path: Path) -> PromptTemplate:
    raw = path.read_text(encoding="utf-8")
    metadata, template = _split_frontmatter(raw, path)
    prompt_id = _required_str(metadata, "prompt_id", path)
    version = _required_str(metadata, "version", path)
    role = _required_str(metadata, "role", path)
    variables = tuple(_parse_list(metadata.get("variables", "[]"), path, "variables"))
    _validate_template_fields(prompt_id, variables, template, path)
    return PromptTemplate(
        prompt_id=prompt_id,
        version=version,
        role=role,
        variables=variables,
        template=template.strip(),
        path=path,
        template_sha256=_sha256(template.strip()),
    )


def _split_frontmatter(raw: str, path: Path) -> tuple[dict[str, str], str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.DOTALL)
    if not match:
        raise PromptRegistryError(f"Prompt missing YAML frontmatter: {path}")
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            raise PromptRegistryError(f"Invalid frontmatter line in {path}: {line}")
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata, match.group(2)


def _required_str(metadata: dict[str, str], key: str, path: Path) -> str:
    value = metadata.get(key, "").strip().strip("\"'")
    if not value:
        raise PromptRegistryError(f"Prompt {path} missing required frontmatter key: {key}")
    return value


def _parse_list(value: str, path: Path, key: str) -> list[str]:
    value = value.strip()
    if value == "[]":
        return []
    if not (value.startswith("[") and value.endswith("]")):
        raise PromptRegistryError(f"Prompt {path} frontmatter key {key} must be an inline list")
    items = value[1:-1].strip()
    if not items:
        return []
    return [item.strip().strip("\"'") for item in items.split(",") if item.strip()]


def _validate_template_fields(
    prompt_id: str,
    declared_variables: tuple[str, ...],
    template: str,
    path: Path,
) -> None:
    stripped_template = _without_fenced_code_blocks(template)
    try:
        fields = {
            field_name
            for _, field_name, _, _ in Formatter().parse(stripped_template)
            if field_name is not None
        }
    except ValueError as exc:
        raise PromptRegistryError(f"Invalid format braces in prompt {path}: {exc}") from exc

    invalid = sorted(
        field for field in fields if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field)
    )
    if invalid:
        raise PromptRegistryError(
            f"Prompt {prompt_id} contains unsupported format fields: {', '.join(invalid)}"
        )

    declared = set(declared_variables)
    undeclared = sorted(fields - declared)
    all_declared_usage = _declared_field_usage(stripped_template)
    unused = sorted(declared - all_declared_usage)
    if undeclared:
        raise PromptRegistryError(
            f"Prompt {prompt_id} uses undeclared variables: {', '.join(undeclared)}"
        )
    if unused:
        raise PromptRegistryError(
            f"Prompt {prompt_id} declares unused variables: {', '.join(unused)}"
        )


def _prompt_file_snapshot(root: Path) -> dict[Path, int]:
    if not root.exists():
        return {}
    return {path: path.stat().st_mtime_ns for path in sorted(root.rglob("*.md"))}


def _without_fenced_code_blocks(template: str) -> str:
    return re.sub(r"```.*?```", "", template, flags=re.DOTALL)


def _declared_field_usage(template: str) -> set[str]:
    return set(re.findall(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})", template))


def _render_template(
    template: str,
    declared_variables: tuple[str, ...],
    values: dict[str, Any],
) -> str:
    declared = set(declared_variables)

    def replace(match: re.Match[str]) -> str:
        field_name = match.group(1)
        if field_name not in declared:
            return match.group(0)
        return str(values[field_name])

    return re.sub(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})", replace, template)


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


__all__ = [
    "PromptRegistry",
    "PromptRegistryError",
    "PromptTemplate",
    "RenderedPrompt",
    "get_prompt_registry",
]
