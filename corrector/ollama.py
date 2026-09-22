
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
import threading

import httpx

from .models import CorrectionResponse
from .prompt import SYSTEM_PROMPT, user_prompt


class OllamaResponseError(RuntimeError):
    pass


class JobCancelled(RuntimeError):
    pass


def extract_json(raw: str):
    if raw is None:
        raise OllamaResponseError("Ollama response is None")

    text = raw.strip()
    if not text:
        raise OllamaResponseError("Ollama returned an empty response")

    candidates = [text]

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
    if fence:
        candidates.append(fence.group(1))

    starts = [m.start() for m in re.finditer(r"\{", text)]
    for start in starts:
        candidates.append(text[start:])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise OllamaResponseError(
        "Could not extract valid JSON from Ollama response. "
        f"Raw response prefix: {text[:500]!r}"
    )


class OllamaClient:
    def __init__(self, config, work_dir: Path):
        cfg = config["ollama"]
        self.base_url = cfg["base_url"].rstrip("/")
        self.model = cfg["model"]
        self.keep_alive = cfg.get("keep_alive", -1)
        self.think = bool(cfg.get("think", False))
        self.num_ctx = int(cfg.get("num_ctx", 8192))
        self.temperature = float(cfg.get("temperature", 0.1))
        self.num_predict = int(cfg.get("num_predict", 3000))
        self.timeout = float(cfg.get("timeout_seconds", 900))
        self.work_dir = work_dir
        self.raw_dir = work_dir / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def check(self):
        with httpx.Client(timeout=30) as client:
            r = client.get(f"{self.base_url}/api/tags")
            r.raise_for_status()
            names = [m.get("name", "") for m in r.json().get("models", [])]

        if not any(n == self.model or n.startswith(self.model + ":") for n in names):
            raise RuntimeError(
                f"Модель {self.model!r} не найдена. Доступны: {names}"
            )

    def correct(self, sentences, chunk_name: str, cancel_event: threading.Event | None = None):
        payload = {
            "model": self.model,
            "system": SYSTEM_PROMPT,
            "prompt": user_prompt(sentences),
            "stream": True,
            "think": self.think,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
            "format": "json",
        }

        raw_parts = []

        # Streaming lets us close the HTTP connection as soon as the user
        # presses Cancel. Ollama then stops producing the current generation.
        with httpx.Client(timeout=self.timeout) as client:
            with client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json=payload,
            ) as r:
                r.raise_for_status()

                for line in r.iter_lines():
                    if cancel_event is not None and cancel_event.is_set():
                        raise JobCancelled("Проверка отменена пользователем")

                    if not line:
                        continue

                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    piece = item.get("response", "")
                    if piece:
                        raw_parts.append(piece)

                    if item.get("done"):
                        break

        raw = "".join(raw_parts)
        raw_file = self.raw_dir / f"{chunk_name}.txt"
        raw_file.write_text(raw or "", encoding="utf-8")

        if not raw:
            raise OllamaResponseError(
                f"Empty response for {chunk_name}. Raw response saved to {raw_file}"
            )

        parsed = extract_json(raw)
        return CorrectionResponse.model_validate(parsed)

    def correct_with_retry(self, sentences, chunk_name: str, retries: int,
                           cancel_event: threading.Event | None = None):
        last = None
        for attempt in range(retries + 1):
            if cancel_event is not None and cancel_event.is_set():
                raise JobCancelled("Проверка отменена пользователем")

            try:
                return self.correct(
                    sentences,
                    f"{chunk_name}_attempt{attempt + 1}",
                    cancel_event=cancel_event,
                )
            except JobCancelled:
                raise
            except Exception as exc:
                last = exc
                logging.error(
                    "Chunk %s attempt %d failed: %s",
                    chunk_name, attempt + 1, exc
                )
                if attempt < retries:
                    time.sleep(2)

        raise last
