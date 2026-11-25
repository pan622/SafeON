from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from entract import config as legacy_config


@dataclass(frozen=True)
class Settings:
    base_url: str = os.getenv("SAFEON_BASE_URL", legacy_config.BASE_URL)
    api_key: str = os.getenv("SAFEON_API_KEY", legacy_config.API_KEY)
    model: str = os.getenv("SAFEON_MODEL", legacy_config.MODEL)

    neo4j_uri: str = os.getenv("SAFEON_NEO4J_URI", legacy_config.NEO4J_URI)
    neo4j_user: str = os.getenv("SAFEON_NEO4J_USER", legacy_config.NEO4J_USER)
    neo4j_password: str = os.getenv(
        "SAFEON_NEO4J_PASSWORD", legacy_config.NEO4J_PASSWORD
    )
    neo4j_database: str = os.getenv(
        "SAFEON_NEO4J_DATABASE", legacy_config.NEO4J_DATABASE
    )

    embedding_model: str = os.getenv(
        "SAFEON_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"
    )
    faiss_index_path: Path = Path(
        os.getenv(
            "SAFEON_FAISS_INDEX",
            r"D:\faiss\result\fused_cause_faiss.index",
        )
    )
    faiss_mapping_path: Path = Path(
        os.getenv(
            "SAFEON_FAISS_MAPPING",
            r"D:\faiss\result\fused_cause_mapping.csv",
        )
    )

    vector_top_k: int = int(os.getenv("SAFEON_VECTOR_TOP_K", "20"))
    project_top_k: int = int(os.getenv("SAFEON_PROJECT_TOP_K", "40"))
    fused_top_k: int = int(os.getenv("SAFEON_FUSED_TOP_K", "30"))
    max_evidence_sources: int = int(os.getenv("SAFEON_MAX_EVIDENCE", "3"))
    rrf_k: int = int(os.getenv("SAFEON_RRF_K", "60"))
    llm_timeout_seconds: int = int(os.getenv("SAFEON_LLM_TIMEOUT", "120"))
    max_input_chars: int = int(os.getenv("SAFEON_MAX_INPUT_CHARS", "18000"))
    allow_degraded: bool = os.getenv("SAFEON_ALLOW_DEGRADED", "1") == "1"
    offline_mode: bool = os.getenv("SAFEON_OFFLINE", "0") == "1"


PROJECT_NAMES = [
    "基坑工程",
    "高处作业",
    "临时用电",
    "模板工程",
    "脚手架工程",
    "起重吊装",
    "施工机械",
    "有限空间",
    "动火消防",
    "拆除工程",
    "地下工程",
    "运输及材料管理",
    "通用安全管理",
    "其他施工活动",
]

RISK_ORDER = {
    "低风险": 1,
    "一般风险": 2,
    "较大风险": 3,
    "重大风险": 4,
}

FACTOR_TYPE_MAP = {
    "Human_Factor": "人员因素",
    "人员因素": "人员因素",
    "Physical_Factor": "物理因素",
    "物理因素": "物理因素",
    "物理/设备因素": "物理因素",
    "设备因素": "物理因素",
    "Environmental_Factor": "环境因素",
    "环境因素": "环境因素",
    "Management_Factor": "管理因素",
    "管理因素": "管理因素",
}
