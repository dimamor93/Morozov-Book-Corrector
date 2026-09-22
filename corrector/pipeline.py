from __future__ import annotations

import json
import logging
import time
import threading
from .ollama import JobCancelled
from pathlib import Path

from .chunker import make_chunks
from .ollama import OllamaClient
from .report import create_report
from .validator import validate_response


class CorrectionPipeline:
    def __init__(self, input_path, sentences, work_dir, config, resume, test_chunks=0, cancel_event=None):
        self.input_path = input_path
        self.sentences = sentences
        self.work_dir = work_dir
        self.config = config
        self.resume = resume
        self.test_chunks = test_chunks
        self.cancel_event = cancel_event or threading.Event()

        self.results_dir = work_dir / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.client = OllamaClient(config, work_dir)

    @staticmethod
    def _fmt_seconds(seconds):
        if seconds is None or seconds < 0:
            return "--"
        seconds = int(seconds)
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}ч {m}м"
        if m:
            return f"{m}м {s}с"
        return f"{s}с"

    @staticmethod
    def _progress(done, total, width=30):
        if total <= 0:
            return "[------------------------------]"
        filled = int(width * done / total)
        return "[" + "#" * filled + "-" * (width - filled) + "]"

    def _write_run_state(self, **kwargs):
        path = self.work_dir / "run_state.json"
        state = {}
        if path.exists():
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                state = {}
        state.update(kwargs)
        path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def run(self):
        self.client.check()

        ccfg = self.config["chunking"]
        chunks = make_chunks(
            self.sentences,
            int(ccfg.get("target_sentences", 25)),
            int(ccfg.get("max_input_chars", 18000)),
        )

        limit = self.test_chunks or int(
            self.config["processing"].get("test_chunks", 0)
        )
        if limit > 0:
            chunks = chunks[:limit]
            logging.info("TEST MODE: processing first %d chunks", len(chunks))

        manifest = [
            {
                "chunk": i + 1,
                "start": c[0].id,
                "end": c[-1].id,
                "sentences": len(c),
            }
            for i, c in enumerate(chunks)
        ]
        (self.work_dir / "chunks.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        total = len(chunks)
        all_corrections = []
        all_suspicious = []
        timings = []
        retries = int(self.config["processing"].get("retry_count", 2))

        self._write_run_state(
            status="running",
            chunks_total=total,
            chunks_done=0,
            started_at=time.time(),
        )

        for index, chunk in enumerate(chunks, 1):
            if self.cancel_event.is_set():
                raise JobCancelled("Проверка отменена пользователем")
            name = f"chunk_{chunk[0].id:06d}_{chunk[-1].id:06d}"
            result_file = self.results_dir / f"{name}.json"

            if self.resume and result_file.exists():
                data = json.loads(result_file.read_text(encoding="utf-8"))
                all_corrections.extend(data.get("corrections", []))
                all_suspicious.extend(data.get("suspicious", []))
                logging.info(
                    "[%d/%d] %s resume: sentences %d-%d",
                    index, total, self._progress(index, total),
                    chunk[0].id, chunk[-1].id
                )
                continue

            logging.info(
                "[%d/%d] %s Qwen: sentences %d-%d",
                index, total, self._progress(index - 1, total),
                chunk[0].id, chunk[-1].id
            )

            started = time.perf_counter()
            response = self.client.correct_with_retry(chunk, name, retries, cancel_event=self.cancel_event)
            elapsed = time.perf_counter() - started
            timings.append(elapsed)

            corrections, suspicious = validate_response(chunk, response)

            result = {
                "chunk": index,
                "start": chunk[0].id,
                "end": chunk[-1].id,
                "elapsed_seconds": round(elapsed, 3),
                "corrections": corrections,
                "suspicious": suspicious,
            }

            result_file.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            all_corrections.extend(corrections)
            all_suspicious.extend(suspicious)

            avg = sum(timings) / len(timings)
            remaining = avg * (total - index)

            logging.info(
                "[%d/%d] %s saved | %.1fs | corrections=%d | suspicious=%d | ETA %s",
                index, total, self._progress(index, total),
                elapsed, len(corrections), len(suspicious),
                self._fmt_seconds(remaining)
            )

            self._write_run_state(
                status="running",
                chunks_total=total,
                chunks_done=index,
                last_chunk_start=chunk[0].id,
                last_chunk_end=chunk[-1].id,
                avg_seconds=round(avg, 3),
                eta_seconds=round(remaining, 1),
            )

        (self.work_dir / "corrections.json").write_text(
            json.dumps(all_corrections, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        (self.work_dir / "suspicious.json").write_text(
            json.dumps(all_suspicious, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        report_path = self.input_path.parent / self.config["report"]["filename"]
        create_report(
            report_path,
            all_corrections,
            all_suspicious,
            len(self.sentences),
        )

        total_elapsed = sum(timings)
        self._write_run_state(
            status="completed",
            chunks_total=total,
            chunks_done=total,
            total_seconds=round(total_elapsed, 3),
            corrections=len(all_corrections),
            suspicious=len(all_suspicious),
            report=str(report_path),
        )

        logging.info("DONE: %s", report_path)
        logging.info("Corrections: %d", len(all_corrections))
        logging.info("Suspicious: %d", len(all_suspicious))
        if timings:
            logging.info("Average chunk time: %.1fs", sum(timings) / len(timings))
