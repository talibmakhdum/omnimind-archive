"""Hybrid retrieval with Reciprocal Rank Fusion."""

from __future__ import annotations

from typing import Any


class RRFRetriever:
    def __init__(
        self,
        alpha_vector: float = 1.5,
        alpha_bm25: float = 1.0,
        rrf_k: int = 60,
        final_top_k: int = 10,
    ):
        self.alpha_vector = alpha_vector
        self.alpha_bm25 = alpha_bm25
        self.rrf_k = rrf_k
        self.final_top_k = final_top_k

    def fuse_results(
        self,
        bm25_results: list[dict[str, Any]],
        vector_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        bm25_map = {
            (r["message_id"], r.get("chunk_index", 0)): (i, r)
            for i, r in enumerate(bm25_results)
        }
        vector_map = {
            (r["message_id"], r.get("chunk_index", 0)): (i, r)
            for i, r in enumerate(vector_results)
        }
        all_keys = set(bm25_map) | set(vector_map)
        fused: list[dict[str, Any]] = []
        for key in all_keys:
            bm25_rank = bm25_map[key][0] if key in bm25_map else None
            vector_rank = vector_map[key][0] if key in vector_map else None
            base = bm25_map[key][1] if key in bm25_map else vector_map[key][1]
            combined = 0.0
            if vector_rank is not None:
                combined += self.alpha_vector / (self.rrf_k + vector_rank + 1)
            if bm25_rank is not None:
                combined += self.alpha_bm25 / (self.rrf_k + bm25_rank + 1)
            method = (
                "fusion"
                if bm25_rank is not None and vector_rank is not None
                else ("bm25" if bm25_rank is not None else "vector")
            )
            fused.append(
                {
                    **base,
                    "combined_score": combined,
                    "bm25_rank": bm25_rank,
                    "vector_rank": vector_rank,
                    "retrieval_method": method,
                    "relevance_score": combined,
                }
            )
        fused.sort(key=lambda x: x["combined_score"], reverse=True)
        return fused[: self.final_top_k]
