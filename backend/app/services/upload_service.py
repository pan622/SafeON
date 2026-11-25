from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

from backend.app.config import ApiConfig, UPLOAD_DIR


async def save_upload(file: UploadFile, allowed_suffixes: set[str]) -> Path:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed_suffixes:
        raise ValueError(f"不支持的文件类型：{suffix or '未知'}")
    content = await file.read()
    if not content:
        raise ValueError("上传文件为空")
    if len(content) > ApiConfig().max_upload_bytes:
        raise ValueError("文件超过30MB限制")
    destination = Path(UPLOAD_DIR) / f"{Path(file.filename or 'upload').stem}{suffix}"
    counter = 1
    while destination.exists():
        destination = Path(UPLOAD_DIR) / (
            f"{Path(file.filename or 'upload').stem}_{counter}{suffix}"
        )
        counter += 1
    destination.write_bytes(content)
    return destination
