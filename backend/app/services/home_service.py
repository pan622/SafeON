from __future__ import annotations

from neo4j import GraphDatabase

from entract.config import NEO4J_DATABASE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER


def get_home_stats() -> dict:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            counts = session.run(
                """
                MATCH (n)
                WITH count(n) AS entity_count
                MATCH ()-[r]->()
                RETURN entity_count, count(r) AS relationship_count
                """
            ).single()
            labels = {
                row["label"]: row["count"]
                for row in session.run(
                    "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS count"
                )
            }
            risk_levels = {
                row["level"]: row["count"]
                for row in session.run(
                    """
                    MATCH (f)
                    WHERE f.Cause_Level IS NOT NULL
                    RETURN f.Cause_Level AS level, count(*) AS count
                    """
                )
            }
        factor_distribution = {
            "人员因素": labels.get("Human_Factor", 0),
            "物理因素": labels.get("Physical_Factor", 0),
            "环境因素": labels.get("Environmental_Factor", 0),
            "管理因素": labels.get("Management_Factor", 0),
        }
        return {
            "document_count": labels.get("Document", 0),
            "entity_count": counts["entity_count"],
            "relationship_count": counts["relationship_count"],
            "project_count": labels.get("Project", 0),
            "factor_count": sum(factor_distribution.values()),
            "factor_distribution": factor_distribution,
            "risk_distribution": risk_levels,
        }
    finally:
        driver.close()
