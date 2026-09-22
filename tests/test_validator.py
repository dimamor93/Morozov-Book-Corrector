import pytest
from corrector.models import Sentence, Correction, CorrectionResponse
from corrector.validator import validate_response


def _sent(sid, text):
    return Sentence(id=sid, text=text, paragraph_id=0, paragraph_order=0)


def _resp(*pairs):
    return CorrectionResponse(
        corrections=[Correction(id=i, corrected=c) for i, c in pairs]
    )


def test_valid_small_edit_accepted():
    chunk = [_sent(1, "Он пошол к двери.")]
    resp = _resp((1, "Он пошёл к двери."))
    valid, susp = validate_response(chunk, resp)
    assert len(valid) == 1
    assert valid[0]["id"] == 1
    assert valid[0]["original"] == "Он пошол к двери."
    assert valid[0]["corrected"] == "Он пошёл к двери."
    assert susp == []


def test_identical_correction_skipped():
    chunk = [_sent(1, "Всё хорошо.")]
    resp = _resp((1, "Всё хорошо."))
    valid, susp = validate_response(chunk, resp)
    assert valid == []
    assert susp == []


def test_empty_corrected_skipped():
    chunk = [_sent(1, "Текст.")]
    resp = _resp((1, "   "))
    valid, susp = validate_response(chunk, resp)
    assert valid == [] and susp == []


def test_unknown_id_suspicious():
    chunk = [_sent(1, "Раз.")]
    resp = _resp((999, "Два."))
    valid, susp = validate_response(chunk, resp)
    assert valid == []
    assert len(susp) == 1
    assert susp[0]["reason"] == "unknown_sentence_id"


def test_duplicate_id_suspicious():
    chunk = [_sent(1, "Раз.")]
    resp = _resp((1, "Раз!"), (1, "Раз?"))
    valid, susp = validate_response(chunk, resp)
    assert len(susp) == 1
    assert susp[0]["reason"] == "duplicate_sentence_id"
    # первое вхождение либо valid либо пропущено, но не дублируется
    assert len(valid) <= 1


def test_large_edit_suspicious():
    chunk = [_sent(1, "Короткое.")]
    resp = _resp((1, "Совершенно другой длинный текст про космос и философию жизни вообще."))
    valid, susp = validate_response(chunk, resp)
    assert valid == []
    assert len(susp) == 1
    assert susp[0]["reason"] == "large_edit"
    assert "similarity" in susp[0]


def test_strips_whitespace_before_compare():
    chunk = [_sent(5, "  Текст с пробелами.  ")]
    resp = _resp((5, "Текст с пробелами."))
    valid, susp = validate_response(chunk, resp)
    # после strip совпадают -> пропуск
    assert valid == [] and susp == []


def test_empty_response_returns_empty():
    chunk = [_sent(1, "А.")]
    resp = CorrectionResponse(corrections=[])
    valid, susp = validate_response(chunk, resp)
    assert valid == [] and susp == []


def test_models_validation():
    s = Sentence(id=1, text="x", paragraph_id=2, paragraph_order=3)
    assert s.id == 1
    with pytest.raises(Exception):
        Sentence(id="bad", text="x", paragraph_id=0, paragraph_order=0)
    r = CorrectionResponse.model_validate({"corrections": [{"id": 1, "corrected": "y"}]})
    assert r.corrections[0].corrected == "y"
    r2 = CorrectionResponse.model_validate({})
    assert r2.corrections == []
