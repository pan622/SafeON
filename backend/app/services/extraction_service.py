from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Callable

import fitz
from docx import Document

from agent.llm import LLMClient
from backend.app.config import OUTPUT_DIR
from entract.config import BASE_URL
from entract.prompts import CLASSIFY_PROMPT, EXTRACT_PROMPT


CSV_FIELDS = [
    "Document_Name",
    "Page",
    "Cause_Name",
    "Cause_Type",
    "Project_Name",
    "Cause_Level",
    "Version",
]


def _parse_pages(path: Path) -> list[tuple[int, str]]:
    if path.suffix.lower() == ".docx":
        document = Document(path)
        text = "\n".join(
            paragraph.text.strip()
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        )
        return [(1, text)] if text else []
    document = fitz.open(path)
    try:
        return [
            (page_number, page.get_text().strip())
            for page_number, page in enumerate(document, start=1)
            if page.get_text().strip()
        ]
    finally:
        document.close()


def _make_batches(
    pages: list[tuple[int, str]], max_chars: int = 7000
) -> list[list[tuple[int, str]]]:
    batches: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    current_chars = 0
    for page in pages:
        if current and current_chars + len(page[1]) > max_chars:
            batches.append(current)
            current = []
            current_chars = 0
        current.append(page)
        current_chars += len(page[1])
    if current:
        batches.append(current)
    return batches


def extract_to_csv(
    input_path: Path,
    model: str,
    api_key: str,
    job_id: str,
    update: Callable[..., None],
) -> tuple[Path, dict]:
    update(status="parsing", progress=10, stage_message="正在解析上传文献")
    pages = _parse_pages(input_path)
    if not pages:
        raise ValueError("文献中未提取到有效文字")
    batches = _make_batches(pages)
    client = LLMClient(api_key, BASE_URL, model, timeout=120)
    all_rows: list[dict] = []

    for batch_index, batch in enumerate(batches, start=1):
        start_page, end_page = batch[0][0], batch[-1][0]
        batch_text = "\n\n".join(
            f"【第{page}页】\n{text}" for page, text in batch
        )
        progress = 15 + int((batch_index - 1) / max(1, len(batches)) * 55)
        update(
            status="extracting",
            progress=progress,
            stage_message=f"正在抽取第{start_page}-{end_page}页危险因素",
        )
        extracted = client.complete_json(EXTRACT_PROMPT, batch_text)
        hazards = extracted.get("hazards", [])
        hazards = [
            {
                "Cause_Name": str(item.get("Cause_Name", "")).strip(),
                "Cause_Type": str(item.get("Cause_Type", "")).strip(),
            }
            for item in hazards
            if str(item.get("Cause_Name", "")).strip()
        ]
        if not hazards:
            continue

        classified_items: list[dict] = []
        for offset in range(0, len(hazards), 25):
            response = client.complete_json(
                CLASSIFY_PROMPT,
                json.dumps(hazards[offset : offset + 25], ensure_ascii=False),
            )
            classified_items.extend(
                response.get("result", response.get("results", []))
            )

        page_label = (
            f"P{start_page}" if start_page == end_page else f"P{start_page}-P{end_page}"
        )
        for index, hazard in enumerate(hazards):
            classified = classified_items[index] if index < len(classified_items) else {}
            all_rows.append(
                {
                    "Document_Name": input_path.name,
                    "Page": page_label,
                    "Cause_Name": hazard["Cause_Name"],
                    "Cause_Type": hazard["Cause_Type"],
                    "Project_Name": str(classified.get("Project_Name", "")).strip(),
                    "Cause_Level": str(classified.get("Cause_Level", "")).strip(),
                    "Version": "v1",
                }
            )

    update(status="generating", progress=85, stage_message="正在生成CSV文件")
    output_path = Path(OUTPUT_DIR) / f"{job_id}_extraction.csv"
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)
    levels = [row["Cause_Level"] for row in all_rows]
    risk_order = {"低风险": 1, "一般风险": 2, "较大风险": 3, "重大风险": 4}
    highest = max(levels, key=lambda item: risk_order.get(item, 0)) if levels else "未知"
    summary = {
        "row_count": len(all_rows),
        "hazard_count": len({row["Cause_Name"] for row in all_rows}),
        "project_count": len({row["Project_Name"] for row in all_rows if row["Project_Name"]}),
        "highest_risk_level": highest,
        "preview": all_rows[:50],
    }
    return output_path, summary
