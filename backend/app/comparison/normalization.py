from __future__ import annotations

import unicodedata
from typing import Any


def l0_normalize(value: Any) -> Any:
    """Apply only meaning-preserving normalization shared by every field."""

    if not isinstance(value, str):
        return value
    unicode_normalized = unicodedata.normalize("NFKC", value)
    whitespace_normalized = " ".join(unicode_normalized.split())
    return whitespace_normalized.casefold()
