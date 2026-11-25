from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable


class JobService:
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        # OCR、向量模型和LLM均较重，本地第一版串行执行更稳定。
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="safeon")

    def create(self, job_type: str, runner: Callable[[str], None]) -> dict:
        prefix = "ext" if job_type == "extraction" else "reason"
        job_id = f"{prefix}_{datetime.now():%Y%m%d%H%M%S}_{uuid.uuid4().hex[:8]}"
        job = {
            "job_id": job_id,
            "job_type": job_type,
            "status": "queued",
            "progress": 0,
            "stage_message": "任务已进入队列",
            "error": None,
            "result": None,
            "download_url": None,
        }
        with self._lock:
            self._jobs[job_id] = job
        self._executor.submit(runner, job_id)
        return job.copy()

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.copy() if job else None

    def update(self, job_id: str, **values) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(values)


job_service = JobService()
