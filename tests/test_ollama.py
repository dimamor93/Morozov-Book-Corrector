import json
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from corrector.models import Sentence
from corrector.ollama import (
    OllamaClient,
    OllamaResponseError,
    JobCancelled,
    extract_json,
)


def _cfg(**over):
    base = {
        "ollama": {
            "base_url": "http://127.0.0.1:11434/",
            "model": "qwen:test",
            "keep_alive": -1,
            "think": False,
            "num_ctx": 8192,
            "temperature": 0.1,
            "num_predict": 3000,
            "timeout_seconds": 900,
        }
    }
    base["ollama"].update(over)
    return base


def _s(sid, text="Текст."):
    return Sentence(id=sid, text=text, paragraph_id=0, paragraph_order=0)


# ---------- extract_json ----------

def test_extract_json_plain():
    assert extract_json('{"corrections": []}') == {"corrections": []}


def test_extract_json_with_fence():
    raw = '```json\n{"corrections": [{"id": 1, "corrected": "x"}]}\n```'
    data = extract_json(raw)
    assert data["corrections"][0]["id"] == 1


def test_extract_json_with_prefix_text():
    raw = 'Вот результат: {"corrections": []}'
    assert extract_json(raw) == {"corrections": []}


def test_extract_json_empty_raises():
    with pytest.raises(OllamaResponseError):
        extract_json("   ")


def test_extract_json_none_raises():
    with pytest.raises(OllamaResponseError):
        extract_json(None)


def test_extract_json_garbage_raises():
    with pytest.raises(OllamaResponseError):
        extract_json("no json here ((( ")


def test_extract_json_picks_first_valid_brace():
    raw = 'trash {bad json} {"corrections": [{"id": 2, "corrected": "ok"}]}'
    data = extract_json(raw)
    assert data["corrections"][0]["id"] == 2


# ---------- client init ----------

def test_client_init_strips_slash_and_dirs(tmp_path: Path):
    c = OllamaClient(_cfg(), tmp_path)
    assert c.base_url == "http://127.0.0.1:11434"
    assert (tmp_path / "raw").exists()
    assert c.model == "qwen:test"
    assert c.think is False


# ---------- check ----------

def _mock_httpx_get(models):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"models": [{"name": m} for m in models]}
    mock_client.get.return_value = mock_resp
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    return mock_client


def test_check_ok(tmp_path):
    mc = _mock_httpx_get(["qwen:test"])
    with patch("corrector.ollama.httpx.Client", return_value=mc):
        OllamaClient(_cfg(), tmp_path).check()


def test_check_model_prefix_ok(tmp_path):
    mc = _mock_httpx_get(["qwen:test:latest"])
    with patch("corrector.ollama.httpx.Client", return_value=mc):
        OllamaClient(_cfg(), tmp_path).check()  # startswith model + ":"


def test_check_missing_raises(tmp_path):
    mc = _mock_httpx_get(["other:1b"])
    with patch("corrector.ollama.httpx.Client", return_value=mc):
        with pytest.raises(RuntimeError, match="не найдена"):
            OllamaClient(_cfg(), tmp_path).check()


# ---------- correct (streaming mock) ----------

class _FakeStreamResp:
    def __init__(self, lines):
        self._lines = lines

    def raise_for_status(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_lines(self):
        return iter(self._lines)


class _FakeStreamClient:
    def __init__(self, lines):
        self._lines = lines
        self.stream_calls = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def stream(self, *a, **kw):
        self.stream_calls.append((a, kw))
        return _FakeStreamResp(self._lines)


def _stream_lines(payload_obj):
    full = json.dumps(payload_obj, ensure_ascii=False)
    # режем на два куска как streaming
    half = len(full) // 2
    return [
        json.dumps({"response": full[:half], "done": False}),
        json.dumps({"response": full[half:], "done": True}),
    ]


def test_correct_success_writes_raw(tmp_path):
    fake = _FakeStreamClient(_stream_lines({"corrections": [{"id": 1, "corrected": "Исправлено."}]}))
    with patch("corrector.ollama.httpx.Client", return_value=fake):
        c = OllamaClient(_cfg(), tmp_path)
        resp = c.correct([_s(1, "Оригинал.")], "chunk_000001_000001")
    assert resp.corrections[0].id == 1
    raw_file = tmp_path / "raw" / "chunk_000001_000001.txt"
    assert raw_file.exists()
    assert "corrections" in raw_file.read_text(encoding="utf-8")


def test_correct_empty_response_raises(tmp_path):
    fake = _FakeStreamClient([])
    with patch("corrector.ollama.httpx.Client", return_value=fake):
        c = OllamaClient(_cfg(), tmp_path)
        with pytest.raises(OllamaResponseError, match="Empty response"):
            c.correct([_s(1)], "chunk_x")


def test_correct_cancel_event_raises(tmp_path):
    # cancel_event уже установлен -> correct бросает JobCancelled на первой строке
    fake = _FakeStreamClient(_stream_lines({"corrections": []}))
    ev = threading.Event()
    ev.set()
    with patch("corrector.ollama.httpx.Client", return_value=fake):
        c = OllamaClient(_cfg(), tmp_path)
        with pytest.raises(JobCancelled):
            c.correct([_s(1)], "chunk_c", cancel_event=ev)


def test_correct_skips_bad_lines(tmp_path):
    lines = [
        "not a json line",
        "",
        json.dumps({"response": '{"corrections": []}', "done": True}),
    ]
    fake = _FakeStreamClient(lines)
    with patch("corrector.ollama.httpx.Client", return_value=fake):
        c = OllamaClient(_cfg(), tmp_path)
        resp = c.correct([_s(1)], "chunk_bad")
    assert resp.corrections == []


# ---------- correct_with_retry ----------

def test_retry_succeeds_second_attempt(tmp_path):
    c = OllamaClient(_cfg(), tmp_path)
    ok = MagicMock()
    ok.corrections = []
    with patch.object(c, "correct", side_effect=[RuntimeError("boom"), ok]) as m, \
         patch("corrector.ollama.time.sleep", return_value=None):
        out = c.correct_with_retry([_s(1)], "chunk_r", retries=2)
    assert out is ok
    assert m.call_count == 2


def test_retry_exhausts_raises_last(tmp_path):
    c = OllamaClient(_cfg(), tmp_path)
    with patch.object(c, "correct", side_effect=RuntimeError("fail")) as m, \
         patch("corrector.ollama.time.sleep", return_value=None):
        with pytest.raises(RuntimeError, match="fail"):
            c.correct_with_retry([_s(1)], "chunk_f", retries=1)
    assert m.call_count == 2


def test_retry_cancel_event_precheck(tmp_path):
    c = OllamaClient(_cfg(), tmp_path)
    ev = threading.Event()
    ev.set()
    with pytest.raises(JobCancelled):
        c.correct_with_retry([_s(1)], "chunk_cc", retries=2, cancel_event=ev)


def test_retry_jobcancelled_not_retried(tmp_path):
    c = OllamaClient(_cfg(), tmp_path)
    with patch.object(c, "correct", side_effect=JobCancelled("stop")) as m:
        with pytest.raises(JobCancelled):
            c.correct_with_retry([_s(1)], "chunk_jc", retries=3)
    assert m.call_count == 1
