from __future__ import annotations

import atexit
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path


class ResidentOCRClient:
    """Controller for one reusable PaddleOCR process isolated by a file queue."""

    def __init__(self, timeout_seconds: int = 240) -> None:
        self.timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self._process: subprocess.Popen[bytes] | None = None
        self._queue_dir: Path | None = None
        self._start_count = 0
        atexit.register(self.close)

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process and self._process.poll() is None else None

    @property
    def start_count(self) -> int:
        return self._start_count

    def _start(self) -> None:
        self.close()
        worker = Path(__file__).with_name("resident_ocr_worker.py")
        queue_dir = Path(tempfile.mkdtemp(prefix="safeon-ocr-"))
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        process = subprocess.Popen(
            [sys.executable, str(worker), "--queue-dir", str(queue_dir)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        self._process = process
        self._queue_dir = queue_dir
        self._start_count += 1

        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    f"PaddleOCR 常驻服务启动失败（退出码 {process.returncode}）"
                )
            if (queue_dir / "ready.json").is_file():
                return
            time.sleep(0.1)
        self.close()
        raise TimeoutError("PaddleOCR 常驻服务初始化超时")

    def _recognize_once(self, path: Path) -> str:
        if self._process is None or self._process.poll() is not None:
            self._start()
        assert self._process is not None and self._queue_dir is not None
        request_id = uuid.uuid4().hex
        request_path = self._queue_dir / f"request-{request_id}.json"
        temporary = request_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"path": str(path)}, ensure_ascii=False), encoding="utf-8"
        )
        temporary.replace(request_path)
        response_path = self._queue_dir / f"response-{request_id}.json"
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise ConnectionError(
                    f"PaddleOCR 常驻服务意外退出（退出码 {self._process.returncode}）"
                )
            if response_path.is_file():
                response = json.loads(response_path.read_text("utf-8"))
                response_path.unlink(missing_ok=True)
                if not response.get("ok"):
                    raise RuntimeError(str(response.get("error", "未知OCR错误")))
                return str(response.get("text", "")).strip()
            time.sleep(0.1)
        raise TimeoutError(f"PaddleOCR 超过 {self.timeout_seconds} 秒未返回结果")

    def recognize(self, path: str | Path) -> str:
        image_path = Path(path).resolve()
        with self._lock:
            try:
                return self._recognize_once(image_path)
            except (BrokenPipeError, ConnectionError, EOFError, OSError):
                self._start()
                return self._recognize_once(image_path)

    def close(self) -> None:
        process = self._process
        queue_dir = self._queue_dir
        self._process = None
        self._queue_dir = None
        if process is not None and process.poll() is None:
            if queue_dir is not None:
                (queue_dir / "shutdown").touch()
            try:
                process.wait(timeout=5)
            except Exception:
                process.kill()
                try:
                    process.wait(timeout=2)
                except Exception:
                    pass
        if queue_dir is not None:
            temp_root = Path(tempfile.gettempdir()).resolve()
            resolved = queue_dir.resolve()
            if temp_root in resolved.parents and resolved.name.startswith("safeon-ocr-"):
                shutil.rmtree(resolved, ignore_errors=True)


resident_ocr = ResidentOCRClient()
