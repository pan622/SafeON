from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["低风险", "一般风险", "较大风险", "重大风险", "未知"]


class EvidenceSource(BaseModel):
    document_name: str
    page: str = "页码未记录"


class Rectification(BaseModel):
    corrective_actions: list[str] = Field(default_factory=list)


class HazardResult(BaseModel):
    evidence_id: str
    cause_name: str
    cause_types: list[str] = Field(default_factory=list)
    project_names: list[str] = Field(default_factory=list)
    cause_level: RiskLevel = "未知"
    source_levels: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = ""
    evidence: list[EvidenceSource] = Field(default_factory=list)
    rectification: Rectification = Field(default_factory=Rectification)


class ProjectResult(BaseModel):
    project_name: str
    hazards: list[HazardResult] = Field(default_factory=list)


class ResultSummary(BaseModel):
    project_count: int
    hazard_count: int
    highest_risk_level: RiskLevel


class RetrievalMetadata(BaseModel):
    query_count: int = 0
    vector_candidate_count: int = 0
    graph_candidate_count: int = 0
    fused_candidate_count: int = 0
    selected_candidate_count: int = 0
    rrf_k: int = 60


class AnalysisResult(BaseModel):
    input_file: str
    input_type: str
    model: str
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    summary: ResultSummary
    projects: list[ProjectResult] = Field(default_factory=list)
    retrieval: RetrievalMetadata
    warnings: list[str] = Field(default_factory=list)
