from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import threading
from typing import Callable

from agent.service import SafeONAnalyzer
from agent.settings import Settings as AgentSettings
from agent.parsers import ParsedDocument, parse_file
from backend.app.config import OUTPUT_DIR


class _ReasoningRuntime:
    """Reuse the heavy FAISS/embedding runtime across sequential API jobs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._analyzer: SafeONAnalyzer | None = None
        self._signature: tuple[str, str] | None = None

    def analyze_parsed(
        self, parsed: ParsedDocument, output_dir: Path, model: str, api_key: str
    ) -> dict:
        with self._lock:
            signature = (model, api_key)
            if self._analyzer is None or self._signature != signature:
                if self._analyzer is not None:
                    self._analyzer.close()
                settings = replace(AgentSettings(), model=model, api_key=api_key)
                self._analyzer = SafeONAnalyzer(settings)
                self._signature = signature
            return self._analyzer.analyze_parsed(parsed, output_dir)


_runtime = _ReasoningRuntime()


def reason_to_txt(
    input_path: Path,
    model: str,
    api_key: str,
    job_id: str,
    update: Callable[..., None],
) -> tuple[Path, dict]:
    if input_path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
        update(
            status="ocr",
            progress=10,
            stage_message="正在使用常驻 PaddleOCR 识别图片",
        )
    else:
        update(status="parsing", progress=10, stage_message="正在解析输入文件")
    parsed = parse_file(input_path)
    update(
        status="reasoning",
        progress=35,
        stage_message="正在融合向量库与知识图谱进行风险研判",
    )
    output = _runtime.analyze_parsed(
        parsed, Path(OUTPUT_DIR) / job_id, model=model, api_key=api_key
    )
    result = output["result"]
    text_path = Path(output["text_path"])
    update(status="generating", progress=90, stage_message="正在生成TXT研判报告")
    return text_path, result
