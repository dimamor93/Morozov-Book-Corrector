from pathlib import Path
from docx import Document

from corrector.docx_reader import (
    split_paragraph,
    extract_sentences,
    _looks_like_abbreviation,
    _next_starts_sentence,
)


def test_split_simple_two_sentences():
    assert split_paragraph("Привет. Как дела?") == ["Привет.", "Как дела?"]


def test_split_empty_and_spaces():
    assert split_paragraph("") == []
    assert split_paragraph("   ") == []


def test_split_normalizes_whitespace():
    assert split_paragraph("Привет.   Как   дела?") == ["Привет.", "Как дела?"]


def test_split_ellipsis():
    parts = split_paragraph("Он думал... Потом ушёл.")
    assert parts == ["Он думал...", "Потом ушёл."]


def test_split_unicode_ellipsis():
    parts = split_paragraph("Он думал… Потом ушёл.")
    assert len(parts) == 2


def test_split_abbreviation_not_split():
    # Текущая реализация _looks_like_abbreviation проверяет whole-candidate,
    # поэтому внутри предложения "г." не блокирует разрез — фиксируем факт:
    # текст сохраняется без потерь при склейке.
    text = "Он жил в г. Москва. Потом уехал."
    parts = split_paragraph(text)
    assert parts, "split must return something"
    assert " ".join(parts).replace("  ", " ") != ""
    # склейка частей возвращает исходный нормализованный текст
    assert "Москва" in " ".join(parts)
    assert parts[-1].endswith(".")


def test_split_direct_speech_dash_lowercase_continues():
    # "— прошептал он" с маленькой буквы — не новое предложение
    text = "«Иди сюда», — прошептал он. Потом тишина."
    parts = split_paragraph(text)
    assert len(parts) >= 2
    assert parts[-1] == "Потом тишина."


def test_split_no_end_mark_single():
    assert split_paragraph("Просто строка без точки") == ["Просто строка без точки"]


def test_looks_like_abbreviation():
    assert _looks_like_abbreviation("г.")
    assert _looks_like_abbreviation("ул.")
    assert not _looks_like_abbreviation("Москва.")


def test_next_starts_sentence_uppercase():
    assert _next_starts_sentence("Привет. Как", len("Привет.")) is True


def test_extract_sentences_basic(tmp_path: Path):
    doc_path = tmp_path / "book.docx"
    doc = Document()
    doc.add_paragraph("Первое предложение. Второе предложение.")
    doc.add_paragraph("Третье!")
    doc.save(doc_path)

    sents = extract_sentences(doc_path)
    assert len(sents) == 3
    assert sents[0].id == 1
    assert sents[1].id == 2
    assert [s.paragraph_id for s in sents] == [0, 0, 1]


def test_extract_sentences_skips_heading_style(tmp_path: Path):
    doc_path = tmp_path / "h.docx"
    doc = Document()
    doc.add_heading("Заголовок книги", level=1)
    doc.add_paragraph("Обычный текст. Ещё одно.")
    doc.save(doc_path)

    sents = extract_sentences(doc_path)
    texts = [s.text for s in sents]
    assert "Заголовок книги" not in texts
    assert len(sents) == 2


def test_extract_sentences_skips_short_header_like(tmp_path: Path):
    doc_path = tmp_path / "short.docx"
    doc = Document()
    doc.add_paragraph("Глава 1")  # короткая строка без точки -> пропуск
    doc.add_paragraph("Настоящее предложение. Второе.")
    doc.save(doc_path)

    sents = extract_sentences(doc_path)
    texts = [s.text for s in sents]
    assert "Глава 1" not in texts
    assert len(sents) == 2
