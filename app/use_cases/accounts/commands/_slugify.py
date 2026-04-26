from __future__ import annotations
import re
import unicodedata
from uuid import uuid4


_NON_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(raw: str) -> str:
    """Return a kebab-case slug derived from `raw`. Always returns a non-empty
    Slug-VO-valid string (length >= 2, starts with a letter or digit).
    """
    s = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = _NON_SLUG_RE.sub("-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    # Slug VO requires ^[a-z][a-z0-9-]*[a-z0-9]$ — must start with a letter.
    if not s or len(s) < 2 or not s[0].isalpha():
        s = f"u-{uuid4().hex[:8]}"
    return s
