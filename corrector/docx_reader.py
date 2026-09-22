from __future__ import annotations

from pathlib import Path
import re

from docx import Document
from .models import Sentence

PROTECTED = {
    "г.", "гг.", "ул.", "д.", "рис.", "стр.", "им.", "т.е.", "т.к.",
    "и т.д.", "и т.п.", "см.", "др.", "руб.", "коп.", "млн.", "тыс.",
    "ч.", "п.", "с.", "акад.", "проф.", "доц.", "гр."
}
END_CHARS = ".!?…"


def _looks_like_abbreviation(text: str) -> bool:
    s = text.strip().lower()
    if s in PROTECTED:
        return True
    return bool(re.search(r"\b[А-ЯЁ]\.$", text))


def _next_starts_sentence(text: str, pos: int) -> bool:
    j = pos
    while j < len(text) and text[j] in '»”"\'’)]}':
        j += 1
    if j >= len(text):
        return True
    if not text[j].isspace():
        return False
    k = j
    while k < len(text) and text[k].isspace():
        k += 1
    if k >= len(text):
        return True
    c = text[k]

    # «— прошептал он» — авторские слова, не новое предложение.
    if c in "—-":
        m = re.match(r"[—-]+\s*", text[k:])
        after_dash = k + (m.end() if m else 1)
        if after_dash < len(text) and text[after_dash].islower():
            return False
        return True

    return c in '«„“"' or c.isupper() or c.isdigit()


def split_paragraph(text: str) -> list[str]:
    text = re.sub(r"[ \t\r\n]+", " ", text).strip()
    if not text:
        return []

    result = []
    start = 0
    i = 0

    while i < len(text):
        ch = text[i]
        if ch in END_CHARS:
            if text[i:i + 3] == "...":
                end = i + 3
            elif ch == "…":
                end = i + 1
                while end < len(text) and text[end] == "…":
                    end += 1
            else:
                end = i + 1

            j = end
            while j < len(text) and text[j] in '»”"\'’)]}':
                j += 1

            candidate = text[start:j].strip()
            if candidate and _next_starts_sentence(text, j) and not _looks_like_abbreviation(candidate):
                result.append(candidate)
                start = j
                i = j
                continue
            i = end
            continue
        i += 1

    tail = text[start:].strip()
    if tail:
        result.append(tail)
    return result


def extract_sentences(path: Path) -> list[Sentence]:
    doc = Document(path)
    result = []
    sid = 1

    for paragraph_id, paragraph in enumerate(doc.paragraphs):
        pieces = split_paragraph(paragraph.text)
        style_name = (paragraph.style.name or "").lower()

        # Заголовки Word не нумеруем.
        if style_name.startswith("heading"):
            continue

        # Для тестового файла также не считаем короткие строки без конечного
        # знака заголовками/подзаголовками.
        if (
            len(pieces) <= 2
            and paragraph.text.strip()
            and not re.search(r"[.!?…]$", paragraph.text.strip())
            and len(paragraph.text.strip()) < 100
        ):
            continue

        for order, piece in enumerate(pieces):
            result.append(
                Sentence(
                    id=sid,
                    text=piece,
                    paragraph_id=paragraph_id,
                    paragraph_order=order,
                )
            )
            sid += 1

    return result
