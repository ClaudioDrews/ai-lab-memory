import re
from typing import Optional

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Prefetch, FusionQuery, Fusion, SparseVector,
    Filter, FieldCondition, MatchAny,
)

from bm25 import compute_sparse

COLLECTION = "ai_memory"
EMBED_URL  = "http://localhost:8081/v1/embeddings"
RERANK_URL = "http://localhost:8084/v1/rerank"

_qdrant: Optional[QdrantClient] = None


def get_qdrant(host: str = "localhost", port: int = 6333) -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(host=host, port=port)
    return _qdrant


def embed_query(text: str) -> list[float]:
    response = httpx.post(
        EMBED_URL,
        json={"input": [text], "model": "qwen3-embedding"},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


def retrieve_context(
    query: str,
    top_k: int = 5,
    score_threshold: float = 0.0,
    filter_types: Optional[list[str]] = None,
    use_reranking: bool = True,
) -> list[dict]:
    """
    Recupera chunks do Qdrant com hybrid search (dense + BM25).
    Opcionalmente aplica reranking com Qwen3-Reranker-0.6B.
    
    use_reranking: True → busca top_k*4, rerankeia, retorna top_k
                    False → busca top_k direto (mais rápido)
    """
    client = get_qdrant()

    dense_vector = embed_query(query)
    sparse_indices, sparse_values = compute_sparse(query)

    query_filter = None
    if filter_types:
        query_filter = Filter(
            must=[FieldCondition(key="type", match=MatchAny(any=filter_types))]
        )

    # Se usar reranking, buscar mais candidatos
    retrieve_limit = top_k * 4 if use_reranking else top_k

    results = client.query_points(
        collection_name=COLLECTION,
        prefetch=[
            Prefetch(query=dense_vector, using="dense", limit=retrieve_limit),
            Prefetch(
                query=SparseVector(indices=sparse_indices, values=sparse_values),
                using="sparse",
                limit=retrieve_limit,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=retrieve_limit,
        with_payload=True,
        query_filter=query_filter,
    )

    chunks = []
    for point in results.points:
        score = getattr(point, "score", 1.0)
        if score >= score_threshold:
            chunks.append({
                "text": point.payload.get("text", ""),
                "type": point.payload.get("type", ""),
                "origin": point.payload.get("origin", ""),
                "score": score,
            })

    # Aplicar reranking se habilitado e se houver chunks
    if use_reranking and chunks:
        chunks = rerank_chunks(query, chunks, top_k)

    return chunks


def rerank_chunks(query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    """
    Rerankeia chunks usando Qwen3-Reranker-0.6B.
    
    O reranker lê query + cada chunk e atribui score de relevância semântica.
    Muito mais preciso que similaridade de vetores sozinha.
    """
    try:
        documents = [c["text"] for c in chunks]
        
        # API do llama-server rerank usa "documents" não "passages"
        response = httpx.post(
            RERANK_URL,
            json={"query": query, "documents": documents},
            timeout=30.0,
        )
        response.raise_for_status()
        scores = response.json()["scores"]
        
        # Associar scores aos chunks
        for chunk, score in zip(chunks, scores):
            chunk["rerank_score"] = score
        
        # Ordenar por score do reranker e retornar top_k
        ranked = sorted(chunks, key=lambda x: x.get("rerank_score", 0), reverse=True)
        return ranked[:top_k]
        
    except Exception as e:
        # Fallback: retornar chunks originais se reranker falhar
        print(f"[WARNING] Reranking falhou: {e}. Usando hybrid search puro.")
        return chunks[:top_k]


def format_context_block(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    lines = ["[MEMÓRIA RECUPERADA]"]
    for i, c in enumerate(chunks, 1):
        score_info = f"score={c.get('score', 0):.3f}"
        if "rerank_score" in c:
            score_info += f" rerank={c['rerank_score']:.3f}"
        lines.append(f"\n[{i}] tipo={c['type']} origem={c['origin']} {score_info}")
        lines.append(c["text"])
    lines.append("[/MEMÓRIA RECUPERADA]")
    return "\n".join(lines)
