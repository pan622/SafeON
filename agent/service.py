from __future__ import annotations

import json
from pathlib import Path

from agent.formatters import format_text_report
from agent.graph import build_reasoning_graph
from agent.llm import LLMClient
from agent.nodes import WorkflowNodes
from agent.parsers import ParsedDocument, parse_file
from agent.retrieval import FaissHazardRetriever, Neo4jHazardRetriever
from agent.schemas import AnalysisResult
from agent.settings import Settings


class SafeONAnalyzer:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.vector = None
        self.neo4j = None
        self.llm = None
        self.nodes = None
        self.graph = None

    def _ensure_runtime(self) -> None:
        if self.graph is not None:
            return
        self.vector = FaissHazardRetriever(
            self.settings.faiss_index_path,
            self.settings.faiss_mapping_path,
            self.settings.embedding_model,
        )
        self.neo4j = Neo4jHazardRetriever(
            self.settings.neo4j_uri,
            self.settings.neo4j_user,
            self.settings.neo4j_password,
            self.settings.neo4j_database,
        )
        self.llm = LLMClient(
            self.settings.api_key,
            self.settings.base_url,
            self.settings.model,
            self.settings.llm_timeout_seconds,
        )
        self.nodes = WorkflowNodes(self.settings, self.vector, self.neo4j, self.llm)
        self.graph = build_reasoning_graph(self.nodes)

    def close(self) -> None:
        if self.neo4j is not None:
            self.neo4j.close()

    def __enter__(self) -> "SafeONAnalyzer":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def analyze(self, input_path: str | Path, output_dir: str | Path) -> dict:
        parsed = parse_file(input_path)
        return self.analyze_parsed(parsed, output_dir)

    def analyze_parsed(
        self, parsed: ParsedDocument, output_dir: str | Path
    ) -> dict:
        self._ensure_runtime()
        state = self.graph.invoke(
            {
                "input_file": str(parsed.path),
                "input_type": parsed.input_type,
                "extracted_text": parsed.text,
                "warnings": parsed.warnings,
            }
        )
        result = AnalysisResult.model_validate(state["final_result"])

        destination = Path(output_dir).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        stem = parsed.path.stem
        json_path = destination / f"{stem}_analysis.json"
        text_path = destination / f"{stem}_analysis.txt"
        json_path.write_text(
            json.dumps(result.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        text_path.write_text(format_text_report(result), encoding="utf-8")
        return {
            "result": result.model_dump(),
            "json_path": str(json_path),
            "text_path": str(text_path),
        }


def analyze_file(input_path: str | Path, output_dir: str | Path = "output") -> dict:
    with SafeONAnalyzer() as analyzer:
        return analyzer.analyze(input_path, output_dir)
