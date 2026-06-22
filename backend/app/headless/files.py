"""File registry for headless conversations.

Manages local files that the driver LLM can reference in messages.
Text files have their content injected inline; binary files (PDF, DOCX) are
base64-encoded and can be passed to upload tools.
"""
import base64
import mimetypes
from pathlib import Path

_TEXT_MIMES = frozenset({
    "text/plain",
    "text/markdown",
    "text/csv",
    "text/html",
    "application/json",
    "application/xml",
    "application/javascript",
})

# Extensions that are always treated as text even if mimetypes guesses otherwise
_FORCE_TEXT_EXTS = frozenset({".txt", ".md", ".markdown", ".csv", ".json", ".xml", ".yaml", ".yml"})


class FileRegistry:
    """Registry of named local files available to the headless runner."""

    def __init__(self, source: str | None = None):
        """
        source formats:
          - ``None`` or empty — empty registry
          - ``/path/to/directory`` — registers all files in that directory
          - ``name1=/path/a,name2=/path/b`` — comma-separated name=path pairs
        """
        self._files: dict[str, Path] = {}
        if source:
            self._load(source.strip())

    def _load(self, source: str) -> None:
        if "=" in source:
            for pair in source.split(","):
                pair = pair.strip()
                if "=" not in pair:
                    continue
                name, path_str = pair.split("=", 1)
                p = Path(path_str.strip())
                if p.is_file():
                    self._files[name.strip()] = p
        else:
            p = Path(source)
            if p.is_dir():
                for child in sorted(p.iterdir()):
                    if child.is_file() and not child.name.startswith("."):
                        self._files[child.name] = child

    @property
    def names(self) -> list[str]:
        return list(self._files.keys())

    def __bool__(self) -> bool:
        return bool(self._files)

    def _is_text(self, path: Path) -> bool:
        if path.suffix.lower() in _FORCE_TEXT_EXTS:
            return True
        mime, _ = mimetypes.guess_type(str(path))
        return bool(mime and (mime in _TEXT_MIMES or mime.startswith("text/")))

    def read_text(self, name: str) -> str | None:
        """Return text content for a text-based file, or None if binary/missing."""
        path = self._files.get(name)
        if not path or not path.exists():
            return None
        if not self._is_text(path):
            return None
        return path.read_text(encoding="utf-8", errors="replace")

    def read_bytes(self, name: str) -> tuple[bytes, str] | None:
        """Return (bytes, mime_type) for any file, or None if missing."""
        path = self._files.get(name)
        if not path or not path.exists():
            return None
        mime, _ = mimetypes.guess_type(str(path))
        return path.read_bytes(), mime or "application/octet-stream"

    def read_b64(self, name: str) -> tuple[str, str] | None:
        """Return (base64_data, mime_type) for any file, or None if missing."""
        result = self.read_bytes(name)
        if result is None:
            return None
        raw, mime = result
        return base64.b64encode(raw).decode(), mime

    def get_path(self, name: str) -> Path | None:
        return self._files.get(name)

    def format_listing(self) -> str:
        if not self._files:
            return "No files available."
        lines = []
        for name, path in self._files.items():
            kind = "text" if self._is_text(path) else "binary"
            size_kb = path.stat().st_size // 1024 if path.exists() else 0
            lines.append(f"- {name}  ({kind}, {size_kb}KB)")
        return "\n".join(lines)
