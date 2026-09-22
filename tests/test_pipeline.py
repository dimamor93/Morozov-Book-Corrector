import json
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from corrector.models import Sentence, CorrectionResponse, Correction
from corrector.pipeline import CorrectionPipeline
from corrector.ollama import JobCancelled


def _s(sid, text=None):
    return Sentence(id=sid, text=text or f"Предложение {sid}.", paragraph_id=0, paragraph_order=0)


def _config(**over):
    cfg = {
        "chunking": {"target_sentences": 2, "max_input_chars": 100000},
        "processing": {"retry_count": 1, "test_chunks": 0},
        "report": {"filename": "orthography_report.docx"},
    }
    for k, v in over.items():
        cfg[k] = v
    return cfg


def _pipeline(tmp_path: Path, sentences, config=None, **kw):
    work = tmp_path / "work"
    work.mkdir(parents=True, exist_ok=True)
    inp = tmp_path / "input.docx"
    inp.write_bytes(b"fake")
    cfg = config or _config()
    kw.setdefault("resume", False)
    with patch("corrector.pipeline.OllamaClient"):
        p = CorrectionPipeline(inp, sentences, work, cfg, **kw)
    # подменяем client на мок чтобы не ходить в сеть
    p.client = MagicMock()
    return p


def test_fmt_seconds():
    assert CorrectionPipeline._fmt_seconds(None) == "--"
    assert CorrectionPipeline._fmt_seconds(-5) == "--"
    assert CorrectionPipeline._fmt_seconds(5) == "5с"
    assert CorrectionPipeline._fmt_seconds(65) == "1м 5с"
    assert CorrectionPipeline._fmt_seconds(3700) == "1ч 1м"


def test_progress():
    assert CorrectionPipeline._progress(0, 0) == "[------------------------------]"
    bar = CorrectionPipeline._progress(1, 2)
    assert bar.startswith("[") and bar.endswith("]")
    assert len(bar) == 32
    full = CorrectionPipeline._progress(5, 5)
    assert "-" not in full


def test_write_run_state_merges(tmp_path):
    p = _pipeline(tmp_path, [_s(1)])
    p._write_run_state(status="running", chunks_done=1)
    p._write_run_state(chunks_total=5)
    state = json.loads((p.work_dir / "run_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "running"
    assert state["chunks_done"] == 1
    assert state["chunks_total"] == 5


def test_write_run_state_corrupt_file_recovers(tmp_path):
    p = _pipeline(tmp_path, [_s(1)])
    (p.work_dir / "run_state.json").write_text("not json {{{", encoding="utf-8")
    p._write_run_state(status="running")
    state = json.loads((p.work_dir / "run_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "running"


def test_run_happy_path(tmp_path):
    sents = [_s(1, "Он пошол."), _s(2, "Всё хорошо."), _s(3, "Ещё текст.")]
    p = _pipeline(tmp_path, sents)
    # один чанк из 2 + один из 1 (target=2)
    def fake_retry(chunk, name, retries, cancel_event=None):
        # исправляем первое предложение чанка
        return CorrectionResponse(corrections=[Correction(id=chunk[0].id, corrected=chunk[0].text + "!")])
    p.client.check.return_value = None
    p.client.correct_with_retry.side_effect = fake_retry
    with patch("corrector.pipeline.create_report") as rep:
        p.run()
    assert p.client.check.called
    assert p.client.correct_with_retry.call_count == 2
    assert rep.called
    corr = json.loads((p.work_dir / "corrections.json").read_text(encoding="utf-8"))
    assert len(corr) == 2
    state = json.loads((p.work_dir / "run_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "completed"
    assert state["chunks_done"] == 2
    assert (p.work_dir / "chunks.json").exists()


def test_run_test_chunks_limit(tmp_path):
    sents = [_s(i) for i in range(1, 7)]  # 3 чанка по 2
    p = _pipeline(tmp_path, sents, test_chunks=1)
    p.client.check.return_value = None
    p.client.correct_with_retry.return_value = CorrectionResponse(corrections=[])
    with patch("corrector.pipeline.create_report"):
        p.run()
    assert p.client.correct_with_retry.call_count == 1


def test_run_resume_skips_existing(tmp_path):
    sents = [_s(1, "Раз."), _s(2, "Два.")]
    p = _pipeline(tmp_path, sents, resume=True)
    p.client.check.return_value = None
    # предсоздаём result-файл для единственного чанка (target=2 -> 1 чанк)
    name = "chunk_000001_000002"
    rf = p.results_dir / f"{name}.json"
    rf.write_text(json.dumps({"corrections": [{"id": 1, "original": "Раз.", "corrected": "Раз!"}],
                              "suspicious": []}), encoding="utf-8")
    with patch("corrector.pipeline.create_report"):
        p.run()
    # correct не должен вызываться — всё из resume
    assert p.client.correct_with_retry.call_count == 0
    corr = json.loads((p.work_dir / "corrections.json").read_text(encoding="utf-8"))
    assert corr[0]["id"] == 1


def test_run_cancel_before_start(tmp_path):
    sents = [_s(1), _s(2)]
    ev = threading.Event()
    ev.set()
    p = _pipeline(tmp_path, sents, cancel_event=ev)
    p.client.check.return_value = None
    with patch("corrector.pipeline.create_report"):
        with pytest.raises(JobCancelled):
            p.run()


def test_run_empty_sentences(tmp_path):
    p = _pipeline(tmp_path, [])
    p.client.check.return_value = None
    with patch("corrector.pipeline.create_report") as rep:
        p.run()
    assert p.client.correct_with_retry.call_count == 0
    assert rep.called
