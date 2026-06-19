import re
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_TASKS_DIR = _BACKEND_DIR / "instructions" / "tasks"
_ALLOWED_TASKS = frozenset(
    [
        "content-audit",
        "campaign-design",
        "seo-optimization",
        "component-population",
        "site-management",
        "content-dev-workflow",
    ]
)
_TASK_NAME_RE = re.compile(r"^[a-z0-9_-]{1,64}$")
_cache: dict[str, str] = {}


def _load(path: Path) -> str:
    key = str(path)
    if key not in _cache:
        _cache[key] = path.read_text(encoding="utf-8")
    return _cache[key]


def load_instructions(task_name: str | None = None) -> str:
    base = _load(_BACKEND_DIR / "instructions" / "system" / "base.md")
    guardrails = _load(_BACKEND_DIR / "instructions" / "guardrails" / "core.md")
    parts = [base.strip(), "\n\n## Guardrails\n\n" + guardrails.strip()]

    if task_name:
        if not _TASK_NAME_RE.match(task_name):
            return "\n\n".join(parts)
        if task_name not in _ALLOWED_TASKS:
            return "\n\n".join(parts)

        task_path = (_TASKS_DIR / f"{task_name}.md").resolve()
        # Path traversal guard
        if _TASKS_DIR not in task_path.parents:
            return "\n\n".join(parts)

        if task_path.exists():
            overlay = _load(task_path)
            parts.append("\n\n## Task Context\n\n" + overlay.strip())

    return "\n\n".join(parts)
