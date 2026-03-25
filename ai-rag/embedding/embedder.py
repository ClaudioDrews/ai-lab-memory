"""
Cliente para o llama-server em modo embedding (vetores densos)
e computação de vetores esparsos BM25-style para hybrid search.

O llama-server deve estar rodando em localhost:8081 antes de chamar embed().
compute_sparse() opera localmente, sem servidor.
"""
import re
import hashlib
from collections import Counter
from typing import List

import httpx

# --- Configuração ---
EMBED_URL   = "http://localhost:8081/v1/embeddings"
SPARSE_DIM  = 30_000   # Tamanho do vocabulário virtual (hashing trick)
                        # 30k minimiza colisões para vocabulário técnico típico


# ---------------------------------------------------------------------------
# Vetores densos — llama-server
# ---------------------------------------------------------------------------

def embed(texts: List[str], batch_size: int = 6) -> List[List[float]]:
    """
    Envia textos para o llama-server e retorna vetores densos de 2560 dimensões.
    Processa em batches para evitar timeout em listas longas.
    """
    all_vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = httpx.post(
            EMBED_URL,
            json={"input": batch, "model": "qwen3-embedding"},
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()
        all_vectors.extend([item["embedding"] for item in data["data"]])
    return all_vectors


# ---------------------------------------------------------------------------
# Vetores esparsos — BM25-style com hashing trick (sem dependências externas)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """
    Tokenização simples: lowercase, apenas palavras alfanuméricas.
    Remove stopwords de alta frequência que não contribuem para busca técnica.
    """
    stopwords = {
        "a", "o", "e", "é", "de", "do", "da", "em", "um", "uma",
        "para", "com", "por", "que", "se", "não", "na", "no", "os",
        "as", "ao", "às", "dos", "das", "the", "is", "in", "of",
        "to", "and", "or", "a", "an",
    }
    tokens = re.findall(r'\b\w+\b', text.lower())
    return [t for t in tokens if t not in stopwords and len(t) > 1]


def _token_index(token: str) -> int:
    """
    Converte token em índice determinístico usando MD5.
    hash() do Python não é determinístico entre runs (hash randomization).
    MD5 é determinístico e rápido o suficiente para este uso.
    """
    return int(hashlib.md5(token.encode()).hexdigest(), 16) % SPARSE_DIM


def compute_sparse(text: str) -> tuple[list[int], list[float]]:
    """
    Computa vetor esparso BM25-style para um texto.
    Retorna (indices, values) prontos para qdrant_client.models.SparseVector.

    Aproximação TF com normalização pelo comprimento do documento.
    Não usa IDF (sem corpus global disponível em tempo de indexação),
    mas captura frequência relativa de termos — suficiente para boosting
    de termos exatos (hostnames, comandos, variáveis).

    Colisões de hash são tratadas acumulando os valores no mesmo índice.
    """
    tokens = _tokenize(text)
    if not tokens:
        return [], []

    total = len(tokens)
    counts = Counter(tokens)

    # Acumular TF por índice (colisões somam)
    index_values: dict[int, float] = {}
    for token, count in counts.items():
        idx = _token_index(token)
        tf = count / total
        index_values[idx] = index_values.get(idx, 0.0) + tf

    indices = list(index_values.keys())
    values  = list(index_values.values())
    return indices, values
