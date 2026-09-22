"""Покрытие служебных скриптов и конфигов без побочных эффектов."""
import ast
import py_compile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def test_run_web_compiles_and_guarded():
    p = BASE / "run_web.py"
    assert p.exists()
    py_compile.compile(str(p), doraise=True)
    tree = ast.parse(p.read_text(encoding="utf-8"))
    # uvicorn.run только под __main__, импорт безопасен
    src = p.read_text(encoding="utf-8")
    assert 'if __name__ == "__main__"' in src
    import run_web
    assert run_web.URL == "http://127.0.0.1:8000"


def test_run_server_compiles_and_guarded():
    p = BASE / "run_server.py"
    assert p.exists()
    py_compile.compile(str(p), doraise=True)
    src = p.read_text(encoding="utf-8")
    assert 'if __name__ == "__main__"' in src
    assert "uvicorn" in src


def test_open_browser_compiles():
    # open_browser.py открывает браузер на импорте — только compile, без import
    p = BASE / "open_browser.py"
    assert p.exists()
    py_compile.compile(str(p), doraise=True)
    assert "webbrowser" in p.read_text(encoding="utf-8")


def test_config_yaml_valid():
    import yaml
    cfg = yaml.safe_load((BASE / "config.yaml").read_text(encoding="utf-8"))
    assert "ollama" in cfg and "chunking" in cfg
    assert "processing" in cfg and "report" in cfg
    assert cfg["ollama"]["base_url"].startswith("http")
    assert int(cfg["chunking"]["target_sentences"]) > 0


def test_index_html_exists():
    html = (BASE / "webapp" / "index.html").read_text(encoding="utf-8")
    assert "Book Corrector" in html
    assert "/api/jobs" in html


def test_corrector_package_importable():
    import corrector.chunker
    import corrector.diff
    import corrector.docx_reader
    import corrector.models
    import corrector.ollama
    import corrector.pipeline
    import corrector.prompt
    import corrector.report
    import corrector.validator
    assert all([corrector.chunker, corrector.diff, corrector.docx_reader])
