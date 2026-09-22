
from __future__ import annotations

import json
import shutil
import threading
import uuid
from pathlib import Path

import httpx
import yaml
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from corrector.docx_reader import extract_sentences
from corrector.pipeline import CorrectionPipeline
from corrector.ollama import JobCancelled

BASE = Path(__file__).resolve().parent.parent
UPLOADS = BASE / "webapp" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Book Corrector")
jobs = {}


def load_config():
    return yaml.safe_load((BASE / "config.yaml").read_text(encoding="utf-8"))


def list_models():
    cfg = load_config()
    url = cfg["ollama"]["base_url"].rstrip("/") + "/api/tags"
    with httpx.Client(timeout=20) as client:
        r = client.get(url)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse((BASE / "webapp" / "index.html").read_text(encoding="utf-8"))


@app.get("/api/models")
def models():
    try:
        return {"models": list_models()}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ollama unavailable: {exc}")


@app.post("/api/jobs")
async def create_job(
    file: UploadFile = File(...),
    model: str = Form(...),
):
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Поддерживается только DOCX")

    allowed = list_models()
    if model not in allowed:
        raise HTTPException(status_code=400, detail="Выбранная модель не найдена в Ollama")

    job_id = uuid.uuid4().hex
    job_dir = UPLOADS / job_id
    job_dir.mkdir(parents=True)
    input_path = job_dir / Path(file.filename).name

    with input_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    cfg = load_config()
    cfg["ollama"]["model"] = model

    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "total": 0,
        "message": "В очереди",
        "input": str(input_path),
        "report": None,
        "error": None,
        "cancel_event": threading.Event(),
    }

    def worker():
        try:
            jobs[job_id]["status"] = "running"
            sentences = extract_sentences(input_path)
            work_dir = job_dir / ".book_corrector"
            work_dir.mkdir(parents=True, exist_ok=True)

            # Сначала создаём pipeline, чтобы знать число чанков.
            from corrector.chunker import make_chunks
            ccfg = cfg["chunking"]
            chunks = make_chunks(
                sentences,
                int(ccfg.get("target_sentences", 25)),
                int(ccfg.get("max_input_chars", 18000)),
            )
            jobs[job_id]["total"] = len(chunks)

            # Pipeline пишет своё состояние. UI читает его через polling.
            pipeline = CorrectionPipeline(
                input_path=input_path,
                sentences=sentences,
                work_dir=work_dir,
                config=cfg,
                resume=True,
                cancel_event=jobs[job_id]["cancel_event"],
            )
            pipeline.run()

            report = input_path.parent / cfg["report"]["filename"]
            jobs[job_id].update({
                "status": "completed",
                "progress": len(chunks),
                "total": len(chunks),
                "message": "Готово",
                "report": str(report),
            })
        except JobCancelled:
            jobs[job_id].update({
                "status": "cancelled",
                "message": "Проверка отменена",
            })
        except Exception as exc:
            jobs[job_id].update({
                "status": "error",
                "message": str(exc),
                "error": repr(exc),
            })

    threading.Thread(target=worker, daemon=True).start()
    return {"job_id": job_id}



@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    if job["status"] in ("completed", "error", "cancelled"):
        return {"status": job["status"]}

    job["status"] = "cancelling"
    job["message"] = "Отмена проверки..."
    job["cancel_event"].set()
    return {"status": "cancelling"}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    result = dict(job)

    # Обновляем прогресс из run_state.json, если он существует.
    work_dir = Path(job["input"]).parent / ".book_corrector"
    state_file = work_dir / "run_state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            result["progress"] = state.get("chunks_done", result["progress"])
            result["total"] = state.get("chunks_total", result["total"])
            result["eta_seconds"] = state.get("eta_seconds")
            result["avg_seconds"] = state.get("avg_seconds")
        except Exception:
            pass

    # Не отдаём абсолютные пути клиенту.
    result.pop("input", None)
    result.pop("report", None)
    result.pop("error", None)
    result.pop("cancel_event", None)
    result["can_cancel"] = result["status"] in ("queued", "running", "cancelling")
    if job.get("report"):
        result["download_available"] = True
    else:
        result["download_available"] = False
    return result


@app.get("/api/jobs/{job_id}/download")
def download(job_id: str):
    job = jobs.get(job_id)
    if not job or job["status"] != "completed" or not job.get("report"):
        raise HTTPException(status_code=404, detail="Результат ещё не готов")

    report = Path(job["report"])
    if not report.exists():
        raise HTTPException(status_code=404, detail="Файл результата не найден")

    return FileResponse(
        report,
        filename="orthography_report.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
