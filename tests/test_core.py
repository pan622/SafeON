from agent.formatters import format_text_report
from agent.retrieval.fusion import fuse_ranked_lists
from agent.retrieval.neo4j_retriever import highest_risk, normalize_page
from agent.schemas import AnalysisResult
from agent.settings import Settings


def test_rrf_fusion_accumulates_multiple_rankings():
    result = fuse_ranked_lists(
        [
            [
                {"cause_name": "A", "rank": 1, "similarity": 0.8, "query": "q1"},
                {"cause_name": "B", "rank": 2, "similarity": 0.9, "query": "q1"},
            ],
            [
                {"cause_name": "A", "rank": 2, "similarity": 0.7, "query": "q2"},
                {"cause_name": "C", "rank": 1, "similarity": 0.6, "query": "q2"},
            ],
        ],
        rrf_k=60,
        limit=3,
    )
    assert result[0]["cause_name"] == "A"
    assert result[0]["max_similarity"] == 0.8


def test_risk_and_page_normalization():
    assert highest_risk(["一般风险", "重大风险", "较大风险"]) == "重大风险"
    assert normalize_page("PP7-P9") == "P7-P9"
    assert normalize_page("7-9") == "P7-P9"


def test_default_retrieval_limits():
    settings = Settings()
    assert settings.vector_top_k == 20
    assert settings.project_top_k == 40
    assert settings.fused_top_k == 30
    assert settings.max_evidence_sources == 3
    assert settings.rrf_k == 60


def test_rrf_fusion_respects_thirty_candidate_limit():
    ranked_lists = [
        [
            {
                "cause_name": f"危险因素{index}",
                "rank": index,
                "similarity": 1.0 / index,
                "query": "测试查询",
            }
            for index in range(1, 41)
        ]
    ]
    result = fuse_ranked_lists(ranked_lists, rrf_k=60, limit=30)
    assert len(result) == 30
    assert result[0]["cause_name"] == "危险因素1"


def test_rectification_schema_and_text_report_are_simplified():
    result = AnalysisResult.model_validate(
        {
            "input_file": "测试.docx",
            "input_type": "docx",
            "model": "test-model",
            "summary": {
                "project_count": 1,
                "hazard_count": 1,
                "highest_risk_level": "一般风险",
            },
            "projects": [
                {
                    "project_name": "高处作业",
                    "hazards": [
                        {
                            "evidence_id": "H001",
                            "cause_name": "临边防护缺失",
                            "cause_types": ["物理因素"],
                            "project_names": ["高处作业"],
                            "cause_level": "一般风险",
                            "confidence": 0.9,
                            "reasoning": "输入明确描述临边未设置防护。",
                            "evidence": [
                                {
                                    "document_name": "建筑施工安全规范",
                                    "page": "页码未记录",
                                }
                            ],
                            "rectification": {
                                "corrective_actions": ["设置符合要求的临边防护设施。"]
                            },
                        }
                    ],
                }
            ],
            "retrieval": {
                "query_count": 1,
                "vector_candidate_count": 20,
                "graph_candidate_count": 40,
                "fused_candidate_count": 30,
                "selected_candidate_count": 1,
                "rrf_k": 60,
            },
        }
    )

    rectification = result.model_dump()["projects"][0]["hazards"][0]["rectification"]
    assert rectification == {"corrective_actions": ["设置符合要求的临边防护设施。"]}
    assert result.projects[0].hazards[0].evidence[0].page == "页码未记录"

    report = format_text_report(result)
    assert "整改措施：" in report
    assert "页码未记录" in report
    assert "立即处置：" not in report
    assert "复查验证：" not in report
