from __future__ import annotations
from .models import Sentence


def make_chunks(sentences: list[Sentence], target_sentences: int, max_chars: int):
    chunks = []
    current = []
    chars = 0

    for sentence in sentences:
        if current and (
            len(current) >= target_sentences
            or chars + len(sentence.text) > max_chars
        ):
            chunks.append(current)
            current = []
            chars = 0

        current.append(sentence)
        chars += len(sentence.text)

    if current:
        chunks.append(current)

    return chunks
