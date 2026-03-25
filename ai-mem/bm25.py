"""
BM25 com IDF real — vetorização esparsa para hybrid search.

Substitui a lógica inline em retrieval.py e consolidate.py.
Carrega data/idf.json calculado pelo compute_idf.py.

Se idf.json não existir, cai para TF puro (comportamento anterior).
"""
import hashlib
import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

IDF_PATH = Path("~/ai-stack/projects/ai-mem/data/idf.json").expanduser()
VOCAB_SIZE = 30_000


@lru_cache(maxsize=1)
def _load_idf() -> dict[str, float]:
    """Carrega IDF do disco. Cache em memória."""
    if IDF_PATH.exists():
        with open(IDF_PATH) as f:
            return json.load(f)
    return {}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text.lower())


def _token_index(token: str) -> int:
    return int(hashlib.md5(token.encode()).hexdigest(), 16) % VOCAB_SIZE


def compute_sparse(text: str) -> tuple[list[int], list[float]]:
    """
    Computa vetor esparso BM25-style para um texto.
    Usa IDF se disponível, TF puro caso contrário.
    Retorna (indices, values) para SparseVector do Qdrant.
    """
    tokens = _tokenize(text)
    if not tokens:
        return [], []

    idf = _load_idf()
    counts = Counter(tokens)
    total = len(tokens)

    index_values: dict[int, float] = {}
    for token, count in counts.items():
        tf = count / total
        idf_weight = idf.get(token, 1.0)
        weight = tf * idf_weight
        idx = _token_index(token)
        index_values[idx] = index_values.get(idx, 0.0) + weight

    return list(index_values.keys()), list(index_values.values())


def reload_idf() -> int:
    """Força recarga do IDF do disco. Retorna número de tokens."""
    _load_idf.cache_clear()
    return len(_load_idf())
