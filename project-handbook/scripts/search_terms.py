"""Keyword terms shared by the flow source lookup and the legacy chat relay."""
from __future__ import annotations

import re

WORD_RE = re.compile(r"[a-z0-9_\-]+", re.I)
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def terms(value: str) -> list[str]:
    """Lowercase ASCII words plus overlapping Chinese character pairs."""
    normalized = str(value or "").lower()
    output = WORD_RE.findall(normalized)
    cjk = "".join(CJK_RE.findall(normalized))
    output.extend(cjk[index:index + 2] for index in range(max(0, len(cjk) - 1)))
    if len(cjk) == 1:
        output.append(cjk)
    return [item for item in output if item]
