from __future__ import annotations

from collections import defaultdict


def fuse_ranked_lists(
    ranked_lists: list[list[dict]],
    rrf_k: int,
    limit: int,
) -> list[dict]:
    fused: dict[str, dict] = defaultdict(
        lambda: {
            "rrf_score": 0.0,
            "max_similarity": 0.0,
            "query_hits": set(),
            "retrieval_sources": set(),
        }
    )

    for ranked_list in ranked_lists:
        seen_in_list: set[str] = set()
        for fallback_rank, hit in enumerate(ranked_list, start=1):
            name = str(hit.get("cause_name", "")).strip()
            if not name or name in seen_in_list:
                continue
            seen_in_list.add(name)
            rank = int(hit.get("rank", fallback_rank))
            item = fused[name]
            item["rrf_score"] += 1.0 / (rrf_k + rank)
            item["max_similarity"] = max(
                item["max_similarity"], float(hit.get("similarity", 0.0))
            )
            if hit.get("query"):
                item["query_hits"].add(str(hit["query"]))
            if hit.get("source"):
                item["retrieval_sources"].add(str(hit["source"]))

    ordered = sorted(
        fused.items(),
        key=lambda pair: (
            pair[1]["rrf_score"],
            pair[1]["max_similarity"],
            pair[0],
        ),
        reverse=True,
    )[:limit]
    return [
        {
            "cause_name": name,
            "rrf_score": round(item["rrf_score"], 8),
            "max_similarity": round(item["max_similarity"], 6),
            "query_hits": sorted(item["query_hits"]),
            "retrieval_sources": sorted(item["retrieval_sources"]),
        }
        for name, item in ordered
    ]
