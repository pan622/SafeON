from __future__ import annotations

from agent.schemas import AnalysisResult


def format_text_report(result_value: AnalysisResult | dict) -> str:
    result = (
        result_value
        if isinstance(result_value, AnalysisResult)
        else AnalysisResult.model_validate(result_value)
    )
    lines = [
        "SafeON施工安全风险智能研判报告",
        "=" * 32,
        f"输入文件：{result.input_file}",
        f"输入类型：{result.input_type}",
        f"使用模型：{result.model}",
        f"生成时间：{result.generated_at}",
        "",
        "总体结论",
        "-" * 16,
        f"识别项目数：{result.summary.project_count}",
        f"识别危险因素数：{result.summary.hazard_count}",
        f"最高风险等级：{result.summary.highest_risk_level}",
        "",
    ]
    for project_index, project in enumerate(result.projects, start=1):
        lines.extend(
            [
                f"{project_index}. 项目：{project.project_name}",
                "-" * 24,
            ]
        )
        for hazard_index, hazard in enumerate(project.hazards, start=1):
            lines.extend(
                [
                    f"{project_index}.{hazard_index} 危险因素：{hazard.cause_name}",
                    f"证据编号：{hazard.evidence_id}",
                    f"因素类型：{'、'.join(hazard.cause_types) or '未明确'}",
                    f"风险等级：{hazard.cause_level}",
                    f"关联项目：{'、'.join(hazard.project_names) or '未明确'}",
                    f"研判说明：{hazard.reasoning or '无'}",
                    f"置信度：{hazard.confidence:.2f}",
                    "依据文献：",
                ]
            )
            if hazard.evidence:
                lines.extend(
                    f"  {source_index}) {source.document_name}，{source.page}"
                    for source_index, source in enumerate(hazard.evidence, start=1)
                )
            else:
                lines.append("  无可追溯文献")
            lines.append("整改措施：")
            lines.extend(
                f"  - {item}" for item in hazard.rectification.corrective_actions
            )
            lines.append("")

    lines.extend(
        [
            "检索信息",
            "-" * 16,
            f"检索查询数：{result.retrieval.query_count}",
            f"向量候选数：{result.retrieval.vector_candidate_count}",
            f"图谱候选数：{result.retrieval.graph_candidate_count}",
            f"RRF融合候选数：{result.retrieval.fused_candidate_count}",
            f"最终采用数：{result.retrieval.selected_candidate_count}",
            f"RRF参数k：{result.retrieval.rrf_k}",
        ]
    )
    if result.warnings:
        lines.extend(["", "处理警告", "-" * 16])
        lines.extend(f"- {warning}" for warning in result.warnings)
    return "\n".join(lines).rstrip() + "\n"
