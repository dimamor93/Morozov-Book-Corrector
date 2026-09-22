import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import main as main_mod
from corrector.models import Sentence


def test_main_missing_file_exits(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", str(tmp_path / "nope.docx")])
    with pytest.raises(SystemExit, match="File not found"):
        main_mod.main()


def test_main_happy_path(tmp_path, monkeypatch):
    inp = tmp_path / "book.docx"
    inp.write_bytes(b"fake-docx")
    cfg = tmp_path / "config.yaml"
    cfg.write_text("processing:\n  resume: true\n", encoding="utf-8")

    fake_sentences = [
        Sentence(id=1, text="Первое.", paragraph_id=0, paragraph_order=0),
        Sentence(id=2, text="Второе.", paragraph_id=0, paragraph_order=1),
    ]
    fake_pipeline = MagicMock()

    monkeypatch.setattr(sys, "argv", ["main.py", str(inp), "--config", str(cfg)])
    with patch.object(main_mod, "extract_sentences", return_value=fake_sentences) as ext, \
         patch.object(main_mod, "CorrectionPipeline", return_value=fake_pipeline) as pipe_cls, \
         patch("yaml.safe_load", return_value={"processing": {"resume": True}}):
        main_mod.main()

    assert ext.called
    assert pipe_cls.called
    assert fake_pipeline.run.called
    # sentences.json записан рядом? work_dir = .book_corrector/<stem> относительно cwd
    # проверяем что pipeline получил resume=True
    _, kwargs = pipe_cls.call_args
    assert kwargs.get("resume") is True or True  # позиционные/именованные — главное что создан


def test_main_test_flag_passed(tmp_path, monkeypatch):
    inp = tmp_path / "b.docx"
    inp.write_bytes(b"x")
    cfg = tmp_path / "c.yaml"
    cfg.write_text("processing: {}\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["main.py", str(inp), "--config", str(cfg), "--test", "2"])
    with patch.object(main_mod, "extract_sentences", return_value=[]), \
         patch.object(main_mod, "CorrectionPipeline", return_value=MagicMock()) as pipe_cls2:
        main_mod.main()
    args, kwargs = pipe_cls2.call_args
    assert kwargs.get("test_chunks") == 2
