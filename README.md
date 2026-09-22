# Book Corrector

Локальный корректор больших русскоязычных книг в формате DOCX на базе Ollama.

Программа вычитывает книгу по предложениям, отправляет их небольшими чанками в локальную LLM, собирает исправления и формирует отчёт `orthography_report.docx`, в котором изменённые символы подсвечены красным. Исходный файл никогда не перезаписывается.

Два режима работы:

- **CLI** (`main.py`) — пакетная проверка книги из терминала;
- **Веб-интерфейс** (`run_web.py` / `start.bat`) — загрузка DOCX в браузере, прогресс-бар, отмена, скачивание отчёта.

## Содержание

- [Возможности](#возможности)
- [Как это работает](#как-это-работает)
- [Требования](#требования)
- [Установка](#установка)
- [Быстрый старт](#быстрый-старт)
- [Режим CLI](#режим-cli)
- [Веб-интерфейс](#веб-интерфейс)
- [Конфигурация](#конфигурация)
- [Результаты и файлы](#результаты-и-файлы)
- [Валидация ответов модели](#валидация-ответов-модели)
- [Тесты](#тесты)
- [Структура проекта](#структура-проекта)
- [Устранение неполадок](#устранение-неполадок)
- [Ограничения](#ограничения)

## Возможности

- Проверка орфографии, пунктуации, грамматики, согласования, НЕ/НИ, слитного/раздельного/дефисного написания, прописных/строчных букв и буквы Ё.
- Деление книги на предложения с учётом аббревиатур (`г.`, `ул.`, `т.е.` и др.) и прямой речи.
- Обработка чанками по ~25 предложений — книга любого размера не упирается в контекст модели.
- Каждый чанк — независимый запрос к Ollama; модель держится в памяти (`keep_alive: -1`).
- Строгий JSON-контракт с моделью + извлечение JSON из свободного текста (в т.ч. из ```-блоков).
- Валидация: отсев дубликатов, чужих ID и «больших правок» (similarity < 0.55) в `suspicious.json`.
- Чекпоинты по чанкам: повторный запуск продолжает с места остановки (`--resume`).
- Точный посимвольный diff: в отчёте красным выделены только изменённые символы, пробелы не красятся.
- Веб-интерфейс: drag-and-drop, выбор модели из Ollama, прогресс/ETA, отмена (обрывает streaming-запрос), светлая/тёмная тема.
- 102 синтетических теста, `pytest` зелёный без живой Ollama (все сетевые вызовы замоканы).

## Как это работает

```text
DOCX
 → split_paragraph (предложения с ID)
 → make_chunks (чанки по target_sentences / max_input_chars)
 → Ollama /api/generate, stream + format: json (по одному запросу на чанк)
 → extract_json → CorrectionResponse (pydantic)
 → validate_response (valid / suspicious)
 → results/chunk_*.json (чекпоинт) + run_state.json
 → create_report (diff, красный цвет) → orthography_report.docx
```

Промпт запрещает модели переписывать художественный текст, менять стиль, синонимы и авторскую манеру; при сомнении — не исправлять; возвращать только предложения с исправлениями (`corrector/prompt.py`).

## Требования

- Python 3.10+ (проверено на 3.14).
- [Ollama](https://ollama.com) установлена и запущена (`http://127.0.0.1:11434`).
- Модель из `config.yaml` (по умолчанию `qwen3.8:27b`), либо любая совместимая:

```powershell
ollama pull qwen3.8:27b
ollama list
```

## Установка

```powershell
cd book_corrector
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Зависимости (`requirements.txt`): `python-docx`, `httpx`, `pydantic`, `PyYAML`, `fastapi`, `uvicorn[standard]`, `python-multipart`.

## Быстрый старт

CLI, проверка целой книги:

```powershell
python main.py "test.docx"
```

Веб-интерфейс:

```powershell
python run_web.py
# открыть http://127.0.0.1:8000
```

Windows, запуск в один клик без окна терминала:

```text
start.bat        # запуск сервера + открытие браузера
stop_server.bat  # остановка сервера
```

## Режим CLI

```powershell
# Полная проверка
python main.py "книга.docx"

# Проверить только первые N чанков (дымовый тест перед длинным прогоном)
python main.py "книга.docx" --test 2

# Продолжить с чекпоинтов (по умолчанию и так включено через config.yaml)
python main.py "книга.docx" --resume

# Другой конфиг
python main.py "книга.docx" --config my_config.yaml
```

В консоли видны: номер чанка, прогресс-бар, время обработки, число исправлений, число подозрительных ответов и ETA. Отчёт сохраняется рядом с входным файлом под именем из `report.filename`.

## Веб-интерфейс

1. Запустите `python run_web.py` (или `start.bat`) и откройте `http://127.0.0.1:8000`.
2. Выберите модель Ollama из списка (список запрашивается у `/api/tags` вживую).
3. Перетащите `.docx` в зону загрузки и нажмите «Начать проверку».
4. Следите за прогрессом; при необходимости нажмите «Отменить проверку» — текущий streaming-запрос к Ollama будет закрыт.
5. Скачайте готовый `orthography_report.docx` по кнопке.

Сервер слушает `0.0.0.0:8000`, поэтому с телефона в той же локальной сети можно открыть `http://<IP-компьютера>:8000`. В первый раз Windows Firewall может запросить разрешение для Python/Uvicorn в **частных сетях**. Не выставляйте порт в интернет.

API (для интеграции):

```text
GET  /api/health
GET  /api/models
POST /api/jobs                 # form: file (.docx), model
GET  /api/jobs/{job_id}        # status, progress, total, eta_seconds
POST /api/jobs/{job_id}/cancel
GET  /api/jobs/{job_id}/download
```

Задания хранятся в памяти процесса (однопользовательский локальный сценарий).

## Конфигурация

Файл `config.yaml`:

```yaml
ollama:
  base_url: "http://127.0.0.1:11434"
  model: "qwen3.8:27b"
  keep_alive: -1        # модель остаётся загруженной
  think: false
  num_ctx: 8192
  temperature: 0.1
  num_predict: 3000
  timeout_seconds: 900

chunking:
  target_sentences: 25
  max_input_chars: 18000

correction:
  yo_policy: "semantic"  # не заменять Е на Ё механически

processing:
  retry_count: 2
  resume: true
  test_chunks: 0

report:
  filename: "orthography_report.docx"
```

Модель, выбранная в веб-интерфейсе, применяется только к текущему заданию и не переписывает `config.yaml`.

## Результаты и файлы

Отчёт — рядом со входным файлом:

```text
orthography_report.docx
```

Рабочие данные (чекпоинты, сырые ответы, состояние):

```text
.book_corrector/<имя-книги>/
  sentences.json     # все предложения с ID
  chunks.json        # манифест чанков
  run_state.json     # статус, chunks_done/total, ETA (читается веб-интерфейсом)
  corrections.json   # принятые исправления
  suspicious.json    # отбракованные/подозрительные ответы
  raw/               # сырые ответы Ollama по чанкам
  results/           # пофайловые результаты чанков (чекпоинты)
```

## Валидация ответов модели

`corrector/validator.py` отбрасывает:

- `duplicate_sentence_id` — повторный ID в одном ответе;
- `unknown_sentence_id` — ID вне текущего чанка;
- пустые ответы и ответы без изменений;
- `large_edit` — сходство оригинала и исправления ниже 0.55 (такое попадает в `suspicious.json`, а не в отчёт).

`corrector/diff.py` строит посимвольный diff через `difflib.SequenceMatcher`: в отчёт попадает **точный** исправленный текст, красным подсвечены только изменённые непробельные символы, удалённый текст не показывается.

## Тесты

102 синтетических теста, внешняя Ollama не нужна:

```powershell
python -m pytest tests -q
# 102 passed
```

Покрыты: `chunker`, `diff`, `docx_reader`, `models`, `ollama` (включая streaming-моки и `correct_with_retry`), `pipeline` (happy path, resume, test-лимит, отмена), `prompt`, `report`, `validator`, `webapp/app` (TestClient: jobs, cancel, download), `main`, служебные скрипты и `config.yaml`.

Примечание для Windows: в репозитории есть `conftest.py`, который перенаправляет временные файлы pytest в доступный каталог, если системный `%TEMP%\pytest-of-<user>` недоступен (иначе возможны `PermissionError WinError 5`).

## Структура проекта

```text
book_corrector/
  main.py            # CLI-вход
  run_web.py         # веб-сервер + автооткрытие браузера
  run_server.py      # сервер для start.bat (без браузера)
  start.bat / stop_server.bat
  config.yaml
  corrector/
    docx_reader.py   # split на предложения, extract_sentences
    chunker.py       # нарезка на чанки
    prompt.py        # системный и пользовательский промпты
    ollama.py        # клиент Ollama, extract_json, retry, отмена
    validator.py     # valid / suspicious
    pipeline.py      # оркестрация, чекпоинты, run_state
    diff.py          # посимвольный diff
    report.py        # генерация DOCX-отчёта
    models.py        # pydantic-модели
  webapp/
    app.py           # FastAPI: jobs API
    index.html       # UI (drag-and-drop, темы, прогресс)
  tests/             # 102 синтетических теста
```

## Устранение неполадок

| Симптом | Что проверить |
|---|---|
| `Модель ... не найдена` | `ollama list`, имя модели в `config.yaml` или выбор в UI; Ollama должна отвечать на `GET /api/tags` |
| `Ollama unavailable` (502 в UI) | запущена ли Ollama, доступен ли `base_url` из `config.yaml` |
| Пустые ответы чанков (`Empty response`) | сырой ответ сохранён в `.book_corrector/<книга>/raw/`; увеличить `num_predict`/`timeout_seconds`, попробовать другую модель |
| Всё попадает в `suspicious.json` как `large_edit` | модель переписывает текст вместо точечных правок — снизить `temperature`, проверить промпт |
| Сервер не стартует через `start.bat` | открыть `server_error.log` (открывается автоматически при ошибке), проверить `server.log` |
| `PermissionError` в pytest tmp | используется локальный `conftest.py`; не удаляйте его |

## Ограничения

- Веб-слой держит задания в памяти процесса — после перезапуска сервера история заданий теряется (файлы отчётов и чекпоинты на диске сохраняются).
- Проверка качества зависит от модели; конвейер настроен консервативно (сомнительные места не исправляются, крупные правки отбраковываются).
- Разметка/стили исходного DOCX в отчёт не переносятся — отчёт содержит только текст исправленных предложений.
