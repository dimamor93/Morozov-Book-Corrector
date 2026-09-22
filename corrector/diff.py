
from __future__ import annotations

from difflib import SequenceMatcher
import re

# Keep every character as a token, but classify whitespace separately.
# This avoids the v0.3 problem where whitespace became part of a replacement
# and caused punctuation to appear visually detached.
def _chars(text: str):
    return list(text)


def diff(original: str, corrected: str):
    a = _chars(original)
    b = _chars(corrected)
    sm = SequenceMatcher(None, a, b, autojunk=False)

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for ch in b[j1:j2]:
                yield "equal", ch

        elif tag in ("replace", "insert"):
            for ch in b[j1:j2]:
                # Whitespace is never independently coloured.
                if ch.isspace():
                    yield "equal", ch
                else:
                    yield "changed", ch

        elif tag == "delete":
            # Deleted characters do not occur in the corrected sentence.
            # We intentionally do not show them.
            continue
