from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import TypedDict

from agent.llm import LLMClient
from agent.prompts import QUERY_PLAN_PROMPT, REASONING_PROMPT, RECTIFICATION_PROMPT
from agent.retrieval import (
    FaissHazardRetriever,
    Neo4jHazardRetriever,
    fuse_ranked_lists,
)
from agent.schemas import (
    AnalysisResult,
    HazardResult,
    ProjectResult,
    Rectification,
    ResultSummary,
    RetrievalMetadata,
)
from agent.settings import PROJECT_NAMES, RISK_ORDER, Settings


class ReasoningState(TypedDict, total=False):
    input_file: str
    input_type: str
    extracted_text: str
    warnings: list[str]
    query_plan: dict
    fused_evidence: list[dict]
    findings: list[dict]
    retrieval_metadata: dict
    final_result: dict
    final_text: str


def _unique_strings(values: object, limit: int) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _fallback_query_plan(text: str) -> dict:
    project_queries = [name for name in PROJECT_NAMES if name in text]
    keyword_rules = {
        "高处作业": ["楼层", "临边", "洞口", "安全带", "高处"],
        "临时用电": ["线路", "用电", "电工", "电缆", "配电"],
        "模板工程": ["模板", "支撑", "立杆", "预埋件"],
        "起重吊装": ["吊运", "吊装", "起重", "塔吊"],
        "施工机械": ["机械", "设备调试", "移动设备"],
        "运输及材料管理": ["材料运输", "材料堆放"],
    }
    for project, keywords in keyword_rules.items():
        if project not in project_queries and any(keyword in text for keyword in keywords):
            project_queries.append(project)
    if not project_queries:
        project_queries = ["通用安全管理"]

    sentences = [
        item.strip(" \t\r\n。；;：:")
        for item in re.split(r"[。！？；\n]+", text)
        if len(item.strip()) >= 6
    ]
    risk_markers = [
        "未",
        "无",
        "不足",
        "不到位",
        "老化",
        "积水",
        "潮湿",
        "异常",
        "偏大",
        "不严密",
        "不牢",
        "松动",
        "危险",
    ]
    hazard_queries = [
        sentence for sentence in sentences if any(marker in sentence for marker in risk_markers)
    ][:8]
    if not hazard_queries:
        hazard_queries = sentences[:8] or [text[:300]]
    return {
        "project_queries": project_queries[:3],
        "hazard_queries": hazard_queries,
        "keywords": [],
    }


def _fallback_rectification(finding: dict) -> dict:
    cause = finding["cause_name"]
    return {
        "evidence_id": finding["evidence_id"],
        "corrective_actions": [
            f"依据所引文献要求制定“{cause}”专项整改措施，明确责任人与完成期限。"
        ],
    }


class WorkflowNodes:
    def __init__(
        self,
        settings: Settings,
        vector_retriever: FaissHazardRetriever,
        graph_retriever: Neo4jHazardRetriever,
        llm: LLMClient,
    ) -> None:
        self.settings = settings
        self.vector = vector_retriever
        self.graph = graph_retriever
        self.llm = llm

    def retrieve_and_reason(self, state: ReasoningState) -> ReasoningState:
        warnings = list(state.get("warnings", []))
        input_text = state["extracted_text"]
        prompt_text = input_text[: self.settings.max_input_chars]
        if len(input_text) > len(prompt_text):
            warnings.append(
                f"输入文本超过{self.settings.max_input_chars}字符，检索规划使用截断文本"
            )

        try:
            if self.settings.offline_mode:
                raise ConnectionError("离线测试模式未调用外部大模型")
            print(f"[节点1] 正在生成检索计划：{Path(state['input_file']).name}", flush=True)
            raw_plan = self.llm.complete_json(QUERY_PLAN_PROMPT, prompt_text)
            query_plan = {
                "project_queries": [
                    project
                    for project in _unique_strings(raw_plan.get("project_queries"), 3)
                    if project in PROJECT_NAMES
                ],
                "hazard_queries": _unique_strings(raw_plan.get("hazard_queries"), 8),
                "keywords": _unique_strings(raw_plan.get("keywords"), 12),
            }
            if not query_plan["hazard_queries"]:
                raise ValueError("大模型未返回有效危险因素查询")
        except Exception as error:
            if not self.settings.allow_degraded:
                raise
            query_plan = _fallback_query_plan(prompt_text)
            warnings.append(f"检索计划使用规则降级：{error}")

        vector_lists = self.vector.search(
            query_plan["hazard_queries"], self.settings.vector_top_k
        )
        print(
            f"[节点1] 向量检索完成：{len(query_plan['hazard_queries'])}条查询",
            flush=True,
        )
        project_lists = self.graph.search_by_projects(
            query_plan["project_queries"], self.settings.project_top_k
        )
        fused = fuse_ranked_lists(
            [*vector_lists, *project_lists],
            rrf_k=self.settings.rrf_k,
            limit=self.settings.fused_top_k,
        )
        graph_data = self.graph.enrich(
            [item["cause_name"] for item in fused],
            max_sources=self.settings.max_evidence_sources,
        )

        candidates: list[dict] = []
        for item in fused:
            knowledge = graph_data.get(item["cause_name"])
            if not knowledge:
                continue
            candidate = {**item, **knowledge}
            candidate["evidence_id"] = f"H{len(candidates) + 1:03d}"
            candidates.append(candidate)

        reasoning_payload = {
            "input_text": prompt_text,
            "candidates": candidates,
        }
        selected: list[dict] = []
        try:
            if self.settings.offline_mode:
                raise ConnectionError("离线测试模式未调用外部大模型")
            print(
                f"[节点1] 正在基于{len(candidates)}条RRF候选进行知识推理",
                flush=True,
            )
            raw_reasoning = self.llm.complete_json(
                REASONING_PROMPT,
                json.dumps(reasoning_payload, ensure_ascii=False),
            )
            by_id = {item["evidence_id"]: item for item in candidates}
            seen: set[str] = set()
            for choice in raw_reasoning.get("selected", []):
                evidence_id = str(choice.get("evidence_id", "")).strip()
                if evidence_id not in by_id or evidence_id in seen:
                    continue
                seen.add(evidence_id)
                finding = deepcopy(by_id[evidence_id])
                finding["reasoning"] = str(choice.get("reasoning", "")).strip()
                try:
                    confidence = float(choice.get("confidence", 0.0))
                except (TypeError, ValueError):
                    confidence = 0.0
                finding["confidence"] = min(1.0, max(0.0, confidence))
                selected.append(finding)
        except Exception as error:
            if not self.settings.allow_degraded:
                raise
            warnings.append(f"风险研判使用检索结果降级：{error}")
            for candidate in candidates:
                if candidate["max_similarity"] < 0.60 or not candidate["evidence"]:
                    continue
                finding = deepcopy(candidate)
                finding["reasoning"] = "输入描述与该知识库危险因素语义相似。"
                finding["confidence"] = min(0.85, max(0.5, candidate["max_similarity"]))
                selected.append(finding)
                if len(selected) >= 8:
                    break

        metadata = {
            "query_count": len(query_plan["hazard_queries"]),
            "vector_candidate_count": len(
                {hit["cause_name"] for ranked in vector_lists for hit in ranked}
            ),
            "graph_candidate_count": len(
                {hit["cause_name"] for ranked in project_lists for hit in ranked}
            ),
            "fused_candidate_count": len(candidates),
            "selected_candidate_count": len(selected),
            "rrf_k": self.settings.rrf_k,
        }
        return {
            **state,
            "warnings": warnings,
            "query_plan": query_plan,
            "fused_evidence": candidates,
            "findings": selected,
            "retrieval_metadata": metadata,
        }

    def generate_report(self, state: ReasoningState) -> ReasoningState:
        warnings = list(state.get("warnings", []))
        findings = deepcopy(state.get("findings", []))
        rectification_by_id: dict[str, dict] = {}

        if findings:
            payload = [
                {
                    key: finding[key]
                    for key in (
                        "evidence_id",
                        "cause_name",
                        "cause_types",
                        "project_names",
                        "cause_level",
                        "reasoning",
                        "evidence",
                    )
                }
                for finding in findings
            ]
            try:
                if self.settings.offline_mode:
                    raise ConnectionError("离线测试模式未调用外部大模型")
                print(
                    f"[节点2] 正在为{len(findings)}条危险因素生成整改意见",
                    flush=True,
                )
                response = self.llm.complete_json(
                    RECTIFICATION_PROMPT,
                    json.dumps(payload, ensure_ascii=False),
                )
                for item in response.get("rectifications", []):
                    evidence_id = str(item.get("evidence_id", "")).strip()
                    if evidence_id:
                        rectification_by_id[evidence_id] = item
            except Exception as error:
                if not self.settings.allow_degraded:
                    raise
                warnings.append(f"整改意见使用规则降级：{error}")

        hazards: list[HazardResult] = []
        for finding in findings:
            rectification_data = rectification_by_id.get(finding["evidence_id"])
            if rectification_data is None:
                rectification_data = _fallback_rectification(finding)
            rectification = Rectification(
                corrective_actions=_unique_strings(
                    rectification_data.get("corrective_actions"), 3
                ),
            )
            hazards.append(
                HazardResult(
                    evidence_id=finding["evidence_id"],
                    cause_name=finding["cause_name"],
                    cause_types=finding.get("cause_types", []),
                    project_names=finding.get("project_names", []),
                    cause_level=finding.get("cause_level", "未知"),
                    source_levels=finding.get("source_levels", []),
                    confidence=finding.get("confidence", 0.0),
                    reasoning=finding.get("reasoning", ""),
                    evidence=finding.get("evidence", []),
                    rectification=rectification,
                )
            )

        project_map: dict[str, list[HazardResult]] = {}
        for hazard in hazards:
            projects = hazard.project_names or ["未明确项目"]
            for project in projects:
                project_map.setdefault(project, []).append(hazard)
        projects = [
            ProjectResult(project_name=name, hazards=items)
            for name, items in sorted(project_map.items())
        ]
        highest = (
            max(
                (hazard.cause_level for hazard in hazards),
                key=lambda level: RISK_ORDER.get(level, 0),
            )
            if hazards
            else "未知"
        )
        result = AnalysisResult(
            input_file=Path(state["input_file"]).name,
            input_type=state["input_type"],
            model=self.settings.model,
            summary=ResultSummary(
                project_count=len(projects),
                hazard_count=len(hazards),
                highest_risk_level=highest,
            ),
            projects=projects,
            retrieval=RetrievalMetadata(**state["retrieval_metadata"]),
            warnings=warnings,
        )
        return {**state, "warnings": warnings, "final_result": result.model_dump()}
