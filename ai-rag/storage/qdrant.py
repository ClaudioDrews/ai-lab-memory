"""
Interface com Qdrant.

Suporte a hybrid search: vetores densos (Qwen3-Embedding) + esparsos (BM25-style).
A fusão usa RRF (Reciprocal Rank Fusion) — combina os dois rankings sem pesos manuais.

Schema da coleção:
  -   "dense"  : VectorParams(size=1024, distance=COSINE)
  - "sparse" : SparseVectorParams()
"""
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseVector,
    PointStruct,
    HnswConfigDiff,
    Filter,
    FieldCondition,
    MatchValue,
    Prefetch,
    FusionQuery,
    Fusion,
)

COLLECTION = "ai_memory"
DIMENSION  = 1024


# ---------------------------------------------------------------------------
# Conexão
# ---------------------------------------------------------------------------

def get_client(host: str = "localhost", port: int = 6333) -> QdrantClient:
    return QdrantClient(host=host, port=port)


# ---------------------------------------------------------------------------
# Gestão da coleção
# ---------------------------------------------------------------------------

def _collection_has_sparse(client: QdrantClient) -> bool:
    """
    Verifica se a coleção existente já tem vetores esparsos configurados.
    Robusto contra variações de schema do qdrant-client 1.17.x.
    """
    try:
        info = client.get_collection(COLLECTION)

        # Tentativa 1: atributo direto (qdrant-client >= 1.9)
        params = info.config.params
        for attr in ("sparse_vectors_config", "sparse_vectors"):
            sparse = getattr(params, attr, None)
            if sparse is not None and len(sparse) > 0:
                return True

        # Tentativa 2: inspecionar via dict (fallback defensivo)
        params_dict = params.__dict__ if hasattr(params, "__dict__") else {}
        for key, val in params_dict.items():
            if "sparse" in key.lower() and val:
                return True

        return False

    except Exception:
        # Em caso de qualquer erro de acesso, assumir schema antigo
        # e deixar o --force resolver
        return False


def ensure_collection(client: QdrantClient, force: bool = False) -> None:
    """
    Garante que a coleção existe com o schema correto (dense + sparse).

    force=True: apaga e recria mesmo se já existir.
    force=False: se existir com schema antigo (sem sparse), levanta RuntimeError
                 com instrução de uso do --force.
    """
    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION in existing:
        if force:
            client.delete_collection(COLLECTION)
            print(f"[qdrant] Coleção '{COLLECTION}' apagada para reindexação completa.")
        elif not _collection_has_sparse(client):
            raise RuntimeError(
                f"\n[qdrant] A coleção '{COLLECTION}' existe com schema antigo "
                "(sem vetores esparsos para hybrid search).\n"
                "Execute com --force para migrar:\n"
                "  python pipeline.py ingest <caminho> --force\n"
                "Atenção: --force apaga todos os pontos existentes e reindexada do zero."
            )
        else:
            return  # Schema OK, nada a fazer

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={"dense": VectorParams(size=DIMENSION, distance=Distance.COSINE)},
        sparse_vectors_config={"sparse": SparseVectorParams()},
        hnsw_config=HnswConfigDiff(m=16, ef_construct=100),
    )
    print(f"[qdrant] Coleção '{COLLECTION}' criada (dense dim={DIMENSION} + sparse BM25)")


# ---------------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------------

def upsert(
    client: QdrantClient,
    chunks: list[dict],
    dense_vectors: list[list[float]],
    sparse_vectors: list[tuple[list[int], list[float]]],
) -> None:
    """
    Insere chunks no Qdrant com vetores densos e esparsos.
    Cada ponto carrega texto e metadados completos no payload.
    """
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector={
                "dense": dense_vec,
                "sparse": SparseVector(indices=sp_indices, values=sp_values),
            },
            payload=chunk["metadata"] | {"text": chunk["text"]},
        )
        for chunk, dense_vec, (sp_indices, sp_values)
        in zip(chunks, dense_vectors, sparse_vectors)
    ]
    client.upsert(collection_name=COLLECTION, points=points)


def delete_by_origin(client: QdrantClient, origin: str) -> None:
    """
    Remove todos os pontos cujo payload.origin corresponde ao caminho do arquivo.
    Usado na reindexação incremental para limpar pontos obsoletos antes de reinserir.
    """
    client.delete(
        collection_name=COLLECTION,
        points_selector=Filter(
            must=[FieldCondition(key="origin", match=MatchValue(value=origin))]
        ),
    )


# ---------------------------------------------------------------------------
# Busca
# ---------------------------------------------------------------------------

def search_collection(
    client: QdrantClient,
    dense_vector: list[float],
    sparse_indices: list[int],
    sparse_values: list[float],
    top_k: int = 5,
    min_score: float = 0.0,
) -> list:
    """
    Hybrid search: combina busca por vetor denso (semântica) e esparso (BM25/termos exatos)
    usando RRF (Reciprocal Rank Fusion).

    RRF não requer calibração manual de pesos — combina os rankings de forma robusta,
    especialmente útil para queries que misturam intenção semântica e termos técnicos exatos.

    Cada busca prefetch recupera top_k * 3 candidatos antes da fusão,
    para dar margem ao RRF re-ranquear sem perder resultados relevantes.
    """
    results = client.query_points(
        collection_name=COLLECTION,
        prefetch=[
            Prefetch(
                query=dense_vector,
                using="dense",
                limit=top_k * 3,
            ),
            Prefetch(
                query=SparseVector(indices=sparse_indices, values=sparse_values),
                using="sparse",
                limit=top_k * 3,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
        with_payload=True,
        score_threshold=min_score if min_score > 0.0 else None,
    )
    return results.points
