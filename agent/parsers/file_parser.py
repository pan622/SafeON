from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import fitz
from docx import Document

from agent.parsers.resident_ocr import resident_ocr


@dataclass
class ParsedDocument:
    path: Path
    input_type: str
    text: str
    warnings: list[str] = field(default_factory=list)


def _parse_docx(path: Path) -> ParsedDocument:
    document = Document(path)
    # 按需求只读取普通段落，不处理表格。
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs)
    warnings = [] if text else ["DOCX中未提取到普通段落文本"]
    return ParsedDocument(path=path, input_type="docx", text=text, warnings=warnings)


def _run_image_ocr(path: Path) -> tuple[str, list[str]]:
    try:
        text = resident_ocr.recognize(path)
    except Exception as error:
        return "", [f"PaddleOCR识别失败：{error}"]
    return text, ([] if text else ["图片中未识别到有效文字"])


def _parse_image(path: Path) -> ParsedDocument:
    text, warnings = _run_image_ocr(path)
    return ParsedDocument(path=path, input_type="image", text=text, warnings=warnings)


def _parse_pdf(path: Path) -> ParsedDocument:
    document = fitz.open(path)
    page_texts: list[str] = []
    warnings: list[str] = []
    try:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text().strip()
            if not text:
                pixmap = page.get_pixmap(dpi=180, alpha=False)
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp:
                    temp_path = Path(temp.name)
                try:
                    pixmap.save(temp_path)
                    text, page_warnings = _run_image_ocr(temp_path)
                    warnings.extend(f"第{page_number}页：{item}" for item in page_warnings)
                finally:
                    temp_path.unlink(missing_ok=True)
            if text:
                page_texts.append(f"【输入文件第{page_number}页】\n{text}")
    finally:
        document.close()
    if not page_texts:
        warnings.append("PDF中未提取到有效文字")
    return ParsedDocument(
        path=path,
        input_type="pdf",
        text="\n\n".join(page_texts),
        warnings=warnings,
    )


def parse_file(path_value: str | Path) -> ParsedDocument:
    path = Path(path_value).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"输入文件不存在：{path}")
    suffix = path.suffix.lower()
    if suffix == ".docx":
        parsed = _parse_docx(path)
    elif suffix == ".pdf":
        parsed = _parse_pdf(path)
    elif suffix in {".jpg", ".jpeg", ".png"}:
        parsed = _parse_image(path)
    else:
        raise ValueError(f"不支持的文件类型：{suffix}")
    if not parsed.text.strip():
        detail = "；".join(parsed.warnings) if parsed.warnings else "未知解析错误"
        raise ValueError(f"输入文件未解析出有效文字，无法进行知识推理：{detail}")
    return parsed
