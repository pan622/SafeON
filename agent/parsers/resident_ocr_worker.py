"""Long-lived PaddleOCR worker using a JSON-lines stdin/stdout protocol.

Paddle and SentenceTransformer load overlapping native runtimes on Windows.  The
worker therefore stays in a dedicated process: it initializes PaddleOCR once,
handles any number of images, and keeps the FastAPI process isolated.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
# Paddle 2.x ships legacy generated protobuf descriptors. Keep compatibility
# local to this worker so the API process can use its own protobuf runtime.
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

if sys.platform == "win32":
    import ctypes

    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)

import numpy as np
from paddleocr import PaddleOCR
from PIL import Image


def _extract_texts(result: object) -> list[str]:
    texts: list[str] = []
    if result is None:
        return texts

    def visit(item: object) -> None:
        payload = getattr(item, "json", None)
        if callable(payload):
            payload = payload()
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = None
        if isinstance(payload, dict):
            payload = payload.get("res", payload)
            texts.extend(
                str(text).strip()
                for text in payload.get("rec_texts", [])
                if str(text).strip()
            )
            return
        if not isinstance(item, (list, tuple)):
            return
        # PaddleOCR 2.x entry: [box, (recognized_text, confidence)].
        if (
            len(item) > 1
            and isinstance(item[1], (list, tuple))
            and item[1]
            and isinstance(item[1][0], str)
        ):
            text = item[1][0].strip()
            if text:
                texts.append(text)
            return
        for child in item:
            visit(child)

    visit(result)
    return texts


def _load_image(path: Path) -> np.ndarray:
    with Image.open(path) as source_image:
        image = source_image.convert("RGB")
        max_side = max(image.size)
        if max_side > 1800:
            scale = 1800 / max_side
            image = image.resize(
                (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
                Image.Resampling.LANCZOS,
            )
        return np.asarray(image)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue-dir", required=True)
    arguments = parser.parse_args()
    queue_dir = Path(arguments.queue_dir)
    queue_dir.mkdir(parents=True, exist_ok=True)
    # Match the stable PaddleOCR 2.x API used by entract/ocr_worker_utf8.py.
    bundled = os.getenv("SAFEON_OCR_MODEL_ROOT")
    options = {}
    if bundled:
        root = Path(bundled)
        for option, name in {
            "det_model_dir": "ch_PP-OCRv4_det_infer",
            "rec_model_dir": "ch_PP-OCRv4_rec_infer",
            "cls_model_dir": "ch_ppocr_mobile_v2.0_cls_infer",
        }.items():
            folder = root / name
            if any(not (folder / file).is_file() for file in ("inference.pdmodel", "inference.pdiparams")):
                raise FileNotFoundError(f"Missing bundled PaddleOCR model: {folder}")
            options[option] = str(folder)
    ocr = PaddleOCR(
        **options,
        use_angle_cls=False,
        lang="ch",
        use_mkldnn=False,
        show_log=False,
        cpu_threads=1,
        det_limit_side_len=1800,
    )
    (queue_dir / "ready.json").write_text(
        json.dumps({"pid": os.getpid()}), encoding="utf-8"
    )
    while not (queue_dir / "shutdown").exists():
        requests = sorted(queue_dir.glob("request-*.json"))
        if not requests:
            time.sleep(0.05)
            continue
        for request_path in requests:
            request_id = request_path.stem.removeprefix("request-")
            try:
                request = json.loads(request_path.read_text("utf-8"))
                request_path.unlink(missing_ok=True)
                image_array = _load_image(Path(request["path"]))
                result = ocr.ocr(image_array, cls=False)
                response = {
                    "ok": True,
                    "text": "\n".join(_extract_texts(result)),
                }
            except Exception as error:
                response = {
                    "ok": False,
                    "error": f"{type(error).__name__}: {error}",
                }
            finally:
                response_path = queue_dir / f"response-{request_id}.json"
                temporary = response_path.with_suffix(".tmp")
                temporary.write_text(
                    json.dumps(response, ensure_ascii=False), encoding="utf-8"
                )
                temporary.replace(response_path)


if __name__ == "__main__":
    main()
