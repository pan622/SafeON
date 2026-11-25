from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
DATA_DIR = BACKEND_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"

for directory in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class ApiConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    frontend_origin: str = "http://localhost:5173"
    max_upload_bytes: int = 30 * 1024 * 1024


SUPPORTED_MODELS = {
    "qwen3-8b": {
        "label": "Qwen3-8B",
        "requires_api_key": False,
        "available": False,
        "description": "本地模型接口预留，暂未接入",
    },
    "deepseek-v4-pro": {
        "label": "DeepSeek V4 Pro",
        "requires_api_key": True,
        "available": True,
        "description": "高精度施工安全知识推理",
    },
    "deepseek-v4-flash": {
        "label": "DeepSeek V4 Flash",
        "requires_api_key": True,
        "available": True,
        "description": "快速施工安全知识处理",
    },
}
