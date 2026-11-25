from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

if sys.platform == "win32":
    # OCR原生库异常时由父进程接收退出码，不弹出Windows崩溃对话框。
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
            rec_texts = payload.get("rec_texts", [])
            texts.extend(str(text).strip() for text in rec_texts if str(text).strip())
            return
        if not isinstance(item, (list, tuple)):
            return
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


def main() -> None:
    image_path = Path(sys.argv[1])
    with Image.open(image_path) as source_image:
        image = source_image.convert("RGB")
        max_side = max(image.size)
        if max_side > 1800:
            scale = 1800 / max_side
            image = image.resize(
                (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
                Image.Resampling.LANCZOS,
            )
        image_array = np.asarray(image)

    ocr = PaddleOCR(
        use_angle_cls=False,
        lang="ch",
        use_mkldnn=False,
        show_log=False,
        cpu_threads=1,
        det_limit_side_len=1800,
    )
    result = ocr.ocr(image_array, cls=False)
    print("\n".join(_extract_texts(result)))


if __name__ == "__main__":
    main()
