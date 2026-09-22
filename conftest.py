"""Перенаправляем pytest tmp на доступный каталог.

В этой Windows-среде C:\\Users\\dimam\\AppData\\Local\\Temp\\pytest-of-dimam
недоступен (WinError 5). Чтобы `pytest` был зелёным без флагов,
подменяем tempfile.tempdir до создания basetemp.
"""
import os
import tempfile
from pathlib import Path

_REDIRECT = Path(r"C:\Users\dimam\AppData\Local\Temp\opencode\pytest-tmp")
try:
    _REDIRECT.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(_REDIRECT)
    os.environ["TMPDIR"] = str(_REDIRECT)
    os.environ["TEMP"] = str(_REDIRECT)
    os.environ["TMP"] = str(_REDIRECT)
except Exception:
    pass
