from __future__ import annotations

import re
from collections import defaultdict

from neo4j import GraphDatabase

from agent.settings import FACTOR_TYPE_MAP, RISK_ORDER


def normalize_page(value: object) -> str:
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return "页码未记录"
    page_numbers = re.findall(r"\d+", text)
    if len(page_numbers) >= 2:
        return f"P{page_numbers[0]}-P{page_numbers[1]}"
    if len(page_numbers) == 1:
        return f"P{page_numbers[0]}"
    return text


def highest_risk(levels: list[str]) -> str:
    valid = [level for level in levels if level in RISK_ORDER]
    return max(valid, key=lambda item: RISK_ORDER[item]) if valid else "未知"


class Neo4jHazardRetriever:
    def __init__(self, uri: str, user: str, password: str, database: str) -> None:
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database
        self.driver.verify_connectivity()

    def close(self) -> None:
        self.driver.close()

    def search_by_projects(self, projects: list[str], limit_per_project: int) -> list[list[dict]]:
        ranked_lists: list[list[dict]] = []
        query = """
        MATCH (p:Project)-[:INCLUDE]->(f)
        WHERE p.Project_Name = $project
        WITH f, count { (f)<-[:INVOLVE]-(:Document) } AS source_count
        RETURN f.Cause_Name AS cause_name, source_count
        ORDER BY source_count DESC, cause_name
        LIMIT $limit
        """
        with self.driver.session(database=self.database) as session:
            for project in projects:
                rows = session.run(
                    query, project=project, limit=limit_per_project
                ).data()
                ranked_lists.append(
                    [
                        {
                            "cause_name": row["cause_name"],
                            "rank": rank,
                            "similarity": 0.0,
                            "query": project,
                            "source": "graph_project",
                        }
                        for rank, row in enumerate(rows, start=1)
                        if row.get("cause_name")
                    ]
                )
        return ranked_lists

    def enrich(self, cause_names: list[str], max_sources: int) -> dict[str, dict]:
        if not cause_names:
            return {}
        query = """
        MATCH (f)
        WHERE f.Cause_Name IN $names
          AND any(label IN labels(f) WHERE label IN
              ['Human_Factor','Physical_Factor','Environmental_Factor','Management_Factor'])
        OPTIONAL MATCH (p:Project)-[:INCLUDE]->(f)
        WITH f, labels(f) AS factor_labels,
             collect(DISTINCT p.Project_Name) AS project_names
        OPTIONAL MATCH (d:Document)-[r:INVOLVE]->(f)
        RETURN f.Cause_Name AS cause_name,
               f.Type AS factor_type,
               factor_labels,
               f.Cause_Level AS cause_level,
               project_names,
               collect(DISTINCT {
                   document_name: d.Document_Name,
                   page: r.Source
               }) AS evidence
        """
        grouped: dict[str, dict] = defaultdict(
            lambda: {
                "cause_types": set(),
                "project_names": set(),
                "source_levels": set(),
                "evidence": set(),
            }
        )
        with self.driver.session(database=self.database) as session:
            rows = session.run(query, names=cause_names).data()

        for row in rows:
            name = row.get("cause_name")
            if not name:
                continue
            item = grouped[name]
            raw_types = [row.get("factor_type"), *(row.get("factor_labels") or [])]
            for raw_type in raw_types:
                mapped = FACTOR_TYPE_MAP.get(str(raw_type or ""))
                if mapped:
                    item["cause_types"].add(mapped)
            item["project_names"].update(
                project for project in row.get("project_names", []) if project
            )
            if row.get("cause_level"):
                item["source_levels"].add(row["cause_level"])
            for evidence in row.get("evidence", []):
                document_name = evidence.get("document_name") if evidence else None
                if document_name:
                    item["evidence"].add(
                        (str(document_name), normalize_page(evidence.get("page")))
                    )

        result: dict[str, dict] = {}
        for name, item in grouped.items():
            levels = sorted(
                item["source_levels"], key=lambda level: RISK_ORDER.get(level, 0), reverse=True
            )
            evidence = sorted(
                item["evidence"],
                key=lambda source: (source[1] == "页码未记录", source[0], source[1]),
            )[:max_sources]
            result[name] = {
                "cause_name": name,
                "cause_types": sorted(item["cause_types"]),
                "project_names": sorted(item["project_names"]),
                "source_levels": levels,
                "cause_level": highest_risk(levels),
                "evidence": [
                    {"document_name": document, "page": page}
                    for document, page in evidence
                ],
            }
        return result
