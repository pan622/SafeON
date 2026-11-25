from __future__ import annotations

import csv
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


class FaissHazardRetriever:
    def __init__(
        self,
        index_path: Path,
        mapping_path: Path,
        model_name: str,
    ) -> None:
        if not index_path.is_file():
            raise FileNotFoundError(f"FAISS索引不存在：{index_path}")
        if not mapping_path.is_file():
            raise FileNotFoundError(f"FAISS映射不存在：{mapping_path}")

        self.index = faiss.read_index(str(index_path))
        self.names = self._load_mapping(mapping_path)
        if self.index.ntotal != len(self.names):
            raise ValueError(
                f"FAISS索引数量({self.index.ntotal})与映射数量({len(self.names)})不一致"
            )
        # 知识库构建阶段已经下载过同一模型；在线推理默认只读本地缓存，
        # 避免无网络环境下的HuggingFace重试阻塞。
        self.model = SentenceTransformer(model_name, local_files_only=True)
        dimension = self.model.get_sentence_embedding_dimension()
        if dimension != self.index.d:
            raise ValueError(
                f"Embedding维度({dimension})与FAISS维度({self.index.d})不一致"
            )

    @staticmethod
    def _load_mapping(path: Path) -> list[str]:
        rows: list[tuple[int, str]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                rows.append((int(row["faiss_id"]), row["Cause_Name"].strip()))
        rows.sort(key=lambda item: item[0])
        expected = list(range(len(rows)))
        actual = [item[0] for item in rows]
        if actual != expected:
            raise ValueError("FAISS映射中的faiss_id不连续")
        return [item[1] for item in rows]

    def search(self, queries: list[str], top_k: int) -> list[list[dict]]:
        cleaned = [query.strip() for query in queries if query and query.strip()]
        if not cleaned:
            return []
        vectors = self.model.encode(
            cleaned,
            batch_size=min(16, len(cleaned)),
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        vectors = np.asarray(vectors, dtype="float32")
        scores, identifiers = self.index.search(vectors, top_k)

        ranked_lists: list[list[dict]] = []
        for query, query_scores, query_ids in zip(cleaned, scores, identifiers):
            results: list[dict] = []
            for rank, (score, identifier) in enumerate(
                zip(query_scores, query_ids), start=1
            ):
                if identifier < 0:
                    continue
                results.append(
                    {
                        "cause_name": self.names[int(identifier)],
                        "rank": rank,
                        "similarity": float(score),
                        "query": query,
                        "source": "vector",
                    }
                )
            ranked_lists.append(results)
        return ranked_lists
