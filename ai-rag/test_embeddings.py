"""
Diagnóstico de qualidade dos embeddings via similaridade cosseno.
Requer embed-server rodando em localhost:8081.
"""
import httpx
import math

EMBED_URL = "http://localhost:8081/v1/embeddings"

def embed(texts: list[str]) -> list[list[float]]:
    r = httpx.post(
        EMBED_URL,
        json={"input": texts, "model": "qwen3-embedding"},
        timeout=60.0,
    )
    r.raise_for_status()
    return [item["embedding"] for item in r.json()["data"]]

def cosine(a: list[float], b: list[float]) -> float:
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    return dot / (mag_a * mag_b)

def score_label(s: float) -> str:
    if s > 0.90: return "🟢 excelente"
    if s > 0.75: return "🟡 bom"
    if s > 0.55: return "🟠 fraco"
    return "🔴 sem relação"

# --- Pares de teste ---
# Cada par: (texto_a, texto_b, expectativa)
pairs = [
    # Devem ser muito similares
    (
        "Como instalar o PyTorch com suporte a CUDA no Linux?",
        "Instalação do PyTorch com GPU NVIDIA no Ubuntu.",
        "🔵 esperado alto  (mesma pergunta, palavras diferentes)"
    ),
    # Mesmo domínio, conceitos distintos
    (
        "O que é um virtual environment Python?",
        "Como funciona o Qdrant como banco de dados vetorial?",
        "🔵 esperado médio (AI/dev, mas tópicos distintos)"
    ),
    # Sem relação
    (
        "Receita de bolo de cenoura com cobertura de chocolate.",
        "Configuração do NVIDIA Container Toolkit no Docker.",
        "🔵 esperado baixo (domínios completamente diferentes)"
    ),
    # Seus próprios documentos — frases reais do projeto
    (
        "nunca pip install fora de um venv",
        "nunca ativar dois ambientes Python simultaneamente",
        "🔵 esperado alto  (mesma regra, mesma fonte)"
    ),
    (
        "Qdrant rodando em :6333 com restart: unless-stopped",
        "Redis 7 AOF persistente em :6379 via docker-compose",
        "🔵 esperado médio (mesma infra, serviços distintos)"
    ),
# Teste de identidade (score deve ser ~1.0)
    (
        "NVIDIA GeForce RTX 3060 Mobile com 6GB de VRAM.",
        "NVIDIA GeForce RTX 3060 Mobile com 6GB de VRAM.",
        "🔵 esperado ~1.0  (texto idêntico)"
    ),
    (
    "Instruct: Recupere documentos técnicos relevantes para a query\nQuery: Como instalar PyTorch com CUDA?",
    "PyTorch 2.9.1 instalado com CUDA 12.6. Comando: pip install torch==2.9.1 torchvision==0.24.1 torchaudio==2.9.1 --index-url https://download.pytorch.org/whl/cu126. CUDA disponível: True. GPU detectada: NVIDIA GeForce RTX 3060 Laptop GPU.",
    "🔵 com instruction prefix (esperado alto)"
    ),
]

print("=" * 65)
print("  DIAGNÓSTICO DE QUALIDADE — Qwen3-Embedding-4B-Q6_K")
print("=" * 65)

all_texts = [t for a, b, _ in pairs for t in (a, b)]
all_vecs  = embed(all_texts)

for i, (a, b, expectativa) in enumerate(pairs):
    vec_a = all_vecs[i * 2]
    vec_b = all_vecs[i * 2 + 1]
    score = cosine(vec_a, vec_b)
    print(f"\n{expectativa}")
    print(f"  A: {a[:60]}")
    print(f"  B: {b[:60]}")
    print(f"  Similaridade: {score:.4f}  {score_label(score)}")

print("\n" + "=" * 65)
print("  Dimensão dos vetores:", len(all_vecs[0]))
print("=" * 65)
