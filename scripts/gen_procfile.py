"""Generate Procfile.dev.local with the current venv Python path baked in."""
import sys
from pathlib import Path

python = sys.executable.replace("\\", "/")
content = (
    f"backend: {python} -m uvicorn app.main:app"
    " --app-dir backend --reload --reload-dir backend/app --port 8000\n"
    "frontend: cd frontend && npm run dev\n"
)
Path("Procfile.dev.local").write_text(content)
print(f"Generated Procfile.dev.local (python={python})")
