from corrector.chunker import make_chunks
from corrector.models import Sentence


def _s(sid, text, pid=0):
    return Sentence(id=sid, text=text, paragraph_id=pid, paragraph_order=0)


def test_empty_list_returns_empty():
    assert make_chunks([], 25, 18000) == []


def test_single_sentence_single_chunk():
    s = [_s(1, "Привет мир.")]
    chunks = make_chunks(s, 25, 18000)
    assert len(chunks) == 1
    assert chunks[0][0].id == 1


def test_split_by_target_sentences():
    sentences = [_s(i, f"Предложение номер {i}.") for i in range(1, 11)]
    chunks = make_chunks(sentences, 3, 100000)
    assert len(chunks) == 4  # 3+3+3+1
    assert [len(c) for c in chunks] == [3, 3, 3, 1]
    # порядок и id сохраняются
    flat = [s.id for c in chunks for s in c]
    assert flat == list(range(1, 11))


def test_split_by_max_chars():
    sentences = [_s(1, "a" * 100), _s(2, "b" * 100), _s(3, "c" * 100)]
    chunks = make_chunks(sentences, 25, 150)
    # первый чанк 1 предложение (100), второй не влезет вместе? 100+100>150 -> split
    assert len(chunks) == 3
    assert chunks[0][0].id == 1


def test_max_chars_boundary_exact_fit():
    sentences = [_s(1, "x" * 50), _s(2, "y" * 50)]
    chunks = make_chunks(sentences, 25, 100)
    assert len(chunks) == 1
    assert len(chunks[0]) == 2


def test_target_one_sentence_per_chunk():
    sentences = [_s(1, "Раз."), _s(2, "Два."), _s(3, "Три.")]
    chunks = make_chunks(sentences, 1, 100000)
    assert len(chunks) == 3


def test_very_long_single_sentence_still_chunked():
    sentences = [_s(1, "z" * 50000)]
    chunks = make_chunks(sentences, 25, 100)
    assert len(chunks) == 1
    assert chunks[0][0].text == "z" * 50000
