# 🏗️ System Architecture

**Technical document detailing the AI Lab Memory System architecture.**

---

## 1. Overview

AI Lab Memory is a **long-term semantic memory system** for AI agents, based on **RAG (Retrieval-Augmented Generation)** with hybrid search and reranking.

### 1.1 Design Principles

| Principle | Description |
|-----------|-------------|
| **Transparency** | Seamless integration with any OpenAI-compatible client |
| **Modularity** | Independent components (embedding, reranking, storage) |
| **Performance** | Low latency (~150ms without rerank, ~500ms with rerank) |
| **Precision** | Hybrid search (dense + BM25) + semantic reranking |
| **Scalability** | Horizontal via Qdrant cluster, vertical via GPU |

---

## 2. Components

### 2.1 Architectural Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Client (Hermes, OpenClaw, etc.)          │
│              (any OpenAI-compatible client)                  │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ POST /v1/chat/completions
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  ai-mem :8083 (OpenAI Proxy)                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ REQUEST HANDLER (per request)                        │  │
│  │  1. Extracts last user message                       │  │
│  │  2. Calls retrieval (embed + Qdrant + rerank)        │  │
│  │  3. Injects context into system prompt               │  │
│  │  4. Forwards to LLM backend (Ollama, OpenAI, etc.)   │  │
│  │  5. Streams response + accumulates in Redis          │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ CONSOLIDATION WORKER (asyncio, 15min)                │  │
│  │  - Checks Redis (≥3 sessions?)                       │  │
│  │  - Checks VRAM (≥4GB free?)                          │  │
│  │  - Starts embed-server                               │  │
│  │  - Gemini extracts insights from sessions            │  │
│  │  - Qwen3-0.6B vectorizes insights                    │  │
│  │  - Qdrant stores                                     │  │
│  │  - Redis cleans                                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────────┘
                      │
         ┌────────────┼────────────┐
         │            │            │
         ▼            ▼            ▼
┌─────────────┐ ┌──────────┐ ┌──────────┐
│  Embedding  │ │  Qdrant  │ │  Redis   │
│  :8081      │ │  :6333   │ │  :6379   │
│  Qwen3-0.6B │ │  1024d   │ │  Sessions│
│  1024d      │ │  +BM25   │ │  +Cache  │
└─────────────┘ └──────────┘ └──────────┘
         │
         ▼
┌─────────────┐
│  Reranking  │
│  :8084      │
│  Qwen3-0.6B │
│  (optional) │
└─────────────┘
```

---

## 3. Flows

### 3.1 Query Flow (Request Handler)

```
1. User sends message
   ↓
2. ai-mem intercepts (OpenAI proxy :8083)
   ↓
3. Extracts query from last message
   ↓
4. Local embedding (Qwen3-0.6B :8081) → 1024d vector
   ↓
5. Hybrid Search in Qdrant (:6333)
   - Dense: 1024d vector (cosine similarity)
   - Sparse: BM25 with real IDF (4575 tokens)
   - Fusion: RRF k=60 (combines rankings)
   ↓
6. [Optional] Reranking (Qwen3-Reranker-0.6B :8084)
   - Reorders top-k*4 by semantic relevance
   ↓
7. Injects chunks into system prompt
   ↓
8. Forwards to LLM backend (Ollama Cloud, OpenAI, etc.)
   ↓
9. Streams response to user
   ↓
10. Accumulates turn in Redis (TTL 24h)
```

### 3.2 Consolidation Flow (Automatic Worker)

```
Loop every 15 minutes:
  ↓
PHASE 1: Is it worth it?
  - Redis has ≥3 pending sessions?
  - If no: wait for next cycle
  ↓
PHASE 2: Is it safe for VRAM?
  - chat-server running? → DEFER
  - Ollama with local model? → DEFER
  - Free VRAM < 4GB? → DEFER (max 3 retries)
  ↓
PHASE 3: Consolidate
  a) Start embed-server (if not running)
  b) For each pending session:
     - Read turns from Redis
     - Call Gemini 2.5 Flash (reasoning)
     - Extract: insights, tasks, structured context
     - Validate JSON with json-repair
     - Qwen3-Embedding-0.6B vectorizes insights
     - Upsert to Qdrant with metadata
     - DELETE session from Redis
  c) Stop embed-server
  d) Log result
```

---

## 4. Detailed Components

### 4.1 ai-mem (OpenAI Proxy)

**Port:** `:8083`

**Technology:** FastAPI (Python 3.12)

**Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/chat/completions` | POST | Chat with memory (OpenAI-compatible) |
| `/v1/models` | GET | List available models |
| `/health` | GET | Service health check |

**Main files:**

```
ai-lab-memory/ai-mem/
├── server.py          # FastAPI proxy + lifespan + worker
├── worker.py          # Asyncio consolidation loop
├── consolidate.py     # CLI + consolidation logic
├── retrieval.py       # Hybrid search + reranking
├── reasoning.py       # 6 providers + fallback chain
├── session.py         # Atomic Redis pipeline
├── vram_guard.py      # VRAM checks
└── config.yaml        # Central configuration
```

### 4.2 Embedding Server

**Port:** `:8081`

**Model:** `Qwen3-Embedding-0.6B-Q8_0` (610 MB)

**Dimension:** 1024

**VRAM:** ~700 MB

**Technology:** llama.cpp (llama-server)

**Command:**

```bash
llama-server \
    -m models/embedding/qwen3-embedding-0.6b-q8_0.gguf \
    -ngl 99 \
    --port 8081 \
    --embedding \
    --pooling last
```

### 4.3 Reranking Server

**Port:** `:8084`

**Model:** `Qwen3-Reranker-0.6B-Q8_0` (610 MB)

**VRAM:** ~700 MB

**Technology:** llama.cpp (llama-server --reranking)

**Command:**

```bash
llama-server \
    -m models/reranker/qwen3-reranker-0.6b-q8_0.gguf \
    -ngl 99 \
    --port 8084 \
    --reranking
```

**Endpoint:**

```bash
curl -X POST http://localhost:8084/v1/rerank \
  -H "Content-Type: application/json" \
  -d '{"query": "your query", "documents": ["doc1", "doc2"]}'
```

### 4.4 Qdrant (Vector DB)

**Port:** `:6333`

**Technology:** Qdrant 1.17.0 (Docker)

**Collection:** `ai_memory`

**Configuration:**

```yaml
vectors:
  dense:
    size: 1024
    distance: Cosine
  sparse:
    bm25: {}
```

**Hybrid Search:**

```python
client.query_points(
    collection_name="ai_memory",
    prefetch=[
        Prefetch(query=dense_vector, using="dense", limit=top_k*3),
        Prefetch(query=sparse_vector, using="sparse", limit=top_k*3),
    ],
    query=FusionQuery(fusion=Fusion.RRF),
    limit=top_k,
)
```

### 4.5 Redis (Cache + Sessions)

**Port:** `:6379`

**Technology:** Redis 7 (Docker)

**Usage:**

| Key | Value | TTL |
|-----|-------|-----|
| `ai-mem:session:<id>` | Conversation turns (list) | 24h |
| `ai-mem:embed:<hash>` | Cached embedding | 1h (future) |

---

## 5. Configuration

### 5.1 config.yaml

```yaml
proxy:
  host: "0.0.0.0"
  port: 8083
  backend_url: "http://localhost:11434"  # LLM backend

retrieval:
  collection: "ai_memory"
  top_k: 5
  score_threshold: 0.0
  inject_types: ["doc", "code", "insight", "task", "conversation"]
  reranking:
    enabled: true
    server_url: "http://localhost:8084/v1/rerank"
    retrieve_multiplier: 4

session:
  redis_host: "localhost"
  redis_port: 6379
  ttl_hours: 24
  max_turns_per_session: 200

consolidation:
  auto: true
  check_interval_minutes: 15
  min_sessions: 3
  vram_threshold_mb: 4096
```

---

## 6. Security

### 6.1 Secrets Management

**File:** `.env` (or `~/.config/ai-lab/secrets.env` for system-wide)

**Permissions:** `600` (owner read-only)

**Variables:**

```bash
# LLM Providers
GEMINI_API_KEY=...
GROQ_API_KEY=...
OPENROUTER_API_KEY=...

# HuggingFace
HF_TOKEN=...

# GitHub
GITHUB_TOKEN=...
```

### 6.2 API Keys

**ai-mem:** `AI_MEM_API_KEY` (configurable, default: `sk-local`)

**Usage:**

```bash
curl -X POST http://localhost:8083/v1/chat/completions \
  -H "Authorization: Bearer sk-local" \
  -H "Content-Type: application/json" \
  -d '{"messages": [...]}'
```

---

## 7. Monitoring

### 7.1 Logs

**Location:** `logs/setup.log`

**Format:**

```
[2026-03-25T13:30:00-0300] worker: started — auto consolidation enabled
[2026-03-25T13:45:00-0300] consolidate: session abc123 — 10 chunks ingested
```

### 7.2 Health Checks

```bash
# ai-mem
curl -s http://localhost:8083/health

# Embedding
curl -s http://localhost:8081/v1/models

# Reranking
curl -s http://localhost:8084/v1/models

# Qdrant
curl -s http://localhost:6333/collections/ai_memory

# Redis
docker exec redis redis-cli ping
```

### 7.3 Metrics

| Metric | Command |
|--------|---------|
| **Qdrant points** | `ai-stats` |
| **Redis sessions** | `docker exec redis redis-cli keys "ai-mem:session:*"` |
| **VRAM usage** | `nvidia-smi --query-compute-apps=pid,process_name,used_memory` |
| **GPU temperature** | `nvidia-smi --query-gpu=temperature.gpu` |

---

## 8. Scalability

### 8.1 Vertical (GPU)

| GPU | VRAM | Simultaneous Models |
|-----|------|---------------------|
| RTX 3060 | 6 GB | Embedding + Reranking |
| RTX 4090 | 24 GB | Embedding + Reranking + Local chat |
| A100 | 40-80 GB | Multiple models + large batch |

### 8.2 Horizontal (Qdrant)

```yaml
# Qdrant Cluster (future)
qdrant:
  image: qdrant/qdrant:latest
  deploy:
    replicas: 3
  volumes:
    - qdrant_storage:/qdrant/storage
```

---

## 9. References

- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [llama.cpp GitHub](https://github.com/ggerganov/llama.cpp)
- [Qwen3 Models](https://huggingface.co/Qwen)
- [Hermes Agent](https://hermes-agent.nousresearch.com)

---

**Last updated:** 2026-03-25
