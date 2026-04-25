"""Architecture invariant: only `app/main.py` and `app/api/v1/ai_chat/`
may import from `app.ai.*`. This guarantees the AI module is a leaf
that can be removed by following Recipe A in docs/template-customization.md.
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
APP = ROOT / "app"
AI_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+app\.ai(?:\.|\s|$)", re.MULTILINE)

ALLOWED_IMPORTERS = {
    APP / "main.py",
    APP / "api" / "v1" / "ai_chat" / "routes.py",
    APP / "api" / "v1" / "ai_chat" / "__init__.py",
}


def test_no_unexpected_module_imports_from_app_ai():
    offenders: list[Path] = []
    for py_file in APP.rglob("*.py"):
        if py_file in ALLOWED_IMPORTERS:
            continue
        if APP / "ai" in py_file.parents or py_file == APP / "ai" / "__init__.py":
            continue
        text = py_file.read_text(encoding="utf-8")
        if AI_IMPORT_RE.search(text):
            offenders.append(py_file)
    assert not offenders, (
        "AI module is not a leaf. The following files import from app.ai but "
        "are not in the allowlist:\n  - "
        + "\n  - ".join(str(p.relative_to(ROOT)) for p in offenders)
        + "\n\nIf this is intentional, add the file to ALLOWED_IMPORTERS in this test "
          "and update docs/template-customization.md → Recipe A so removal stays accurate."
    )
