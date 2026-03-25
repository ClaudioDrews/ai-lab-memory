# 🧠 AI Lab Memory System

**Semantic memory system for AI agents with RAG, reranking, and Hermes Agent integration.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Hermes Agent](https://img.shields.io/badge/Hermes-Agent-orange)](https://hermes-agent.nousresearch.com)

---

## 🎯 Overview

**AI Lab Memory** is a complete long-term memory system for AI agents, designed for:

- ✅ **Precise semantic retrieval** — Hybrid search (dense + BM25) with reranking
- ✅ **Seamless integration** — OpenAI-compatible proxy, works with any client
- ✅ **Persistent memory** — Automatic consolidation of conversations into vector memory
- ✅ **Low latency** — Local embedding (Qwen3-0.6B) with optional cache
- ✅ **Production-ready** — Monitoring, logging, and flexible configuration

---

## 🚀 Quick Start

### 1. Installation

```bash
# Clone repository
git clone https://github.com/ClaudioDrews/ai-lab-memory.git
cd ai-lab-memory

# Run installation script
./scripts/install.sh
```

### 2. Configuration

```bash
# Configure environment variables
cp .env.example .env
# Edit .env with your API keys

# Initialize services
./scripts/configure.sh
```

### 3. Usage

```bash
# Test semantic search
ai-search "how to compile llama.cpp with CUDA" --top-k 5

# Check system status
ai-stats

# Integrate with Hermes Agent
hermes config set model.base_url "http://localhost:8083/v1"
hermes config set model.provider "auto"
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Client (Hermes, OpenClaw, etc.)          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  ai-mem :8083 (OpenAI Proxy)                │
│  • Intercepts requests                                      │
│  • Injects memory context                                   │
│  • Forwards to LLM backend                                  │
└─────────────────────┬───────────────────────────────────────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
┌─────────────┐ ┌──────────┐ ┌──────────┐
│  Embedding  │ │  Qdrant  │ │  Redis   │
│  :8081      │ │  :6333   │ │  :6379   │
│  Qwen3-0.6B │ │  1024d   │ │  Cache   │
└─────────────┘ └──────────┘ └──────────┘
```

---

## 📦 Components

| Component | Description | Port |
|-----------|-------------|-------|
| **ai-mem** | OpenAI-compatible proxy with RAG | :8083 |
| **embed-server** | Qwen3-Embedding-0.6B local | :8081 |
| **rerank-server** | Qwen3-Reranker-0.6B (optional) | :8084 |
| **Qdrant** | Vector DB (hybrid search) | :6333 |
| **Redis** | Session and embedding cache | :6379 |

---

## 🔧 Features

### ✅ Implemented

- [x] **Hybrid Search** — Dense (Qwen3-0.6B) + BM25 with IDF
- [x] **Reranking** — Qwen3-Reranker-0.6B (+10-20% precision)
- [x] **Automatic Consolidation** — Asyncio worker (15 min)
- [x] **Hermes Agent Integration** — Transparent configuration
- [x] **Shell Functions** — `ai-search`, `ai-stats`, `ai-reindex-idf`
- [x] **Monitoring** — Logs, health checks, metrics

### 🔜 In Development

- [ ] Embedding cache in Redis
- [ ] Observability dashboard
- [ ] REST API for administration
- [ ] Automatic Qdrant backup

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | Detailed system architecture |
| [Installation](docs/installation.md) | Step-by-step installation guide |
| [Configuration](docs/configuration.md) | Component configuration details |
| [API Reference](docs/api.md) | ai-mem API and endpoints |
| [Usage Examples](docs/usage.md) | Practical usage examples |

---

## 🧪 Validation

### Retrieval Test

```bash
# Search with hybrid search
ai-search "flags cmake CUDA llama.cpp" --top-k 5

# With reranking enabled
ai-search "flags cmake CUDA llama.cpp" --top-k 5 --rerank
```

### Hermes Integration

```bash
# Configure Hermes to use ai-mem
hermes config set model.base_url "http://localhost:8083/v1"
hermes config set model.provider "auto"

# Test
hermes chat -q "What are the flags to compile llama.cpp with CUDA?"
```

**Expected output:**

```
Based on retrieved memory, the flags are:
- `-DGGML_CUDA=ON` — Enables CUDA support
- `-DGGML_CUDA_F16=ON` — Uses FP16 for +performance
```

---

## 🛠️ Requirements

### Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **RAM** | 8 GB | 16 GB |
| **VRAM** | 4 GB | 6+ GB (RTX 3060+) |
| **Storage** | 10 GB | 50+ GB SSD |

### Software

- Linux (Ubuntu 24.04 / Linux Mint 22+)
- Python 3.12+
- Docker (for Qdrant + Redis)
- llama.cpp (for embedding/reranking)

---

## 📊 Metrics

| Metric | Value |
|--------|-------|
| **Latency (no rerank)** | ~150ms |
| **Latency (with rerank)** | ~300-500ms |
| **Precision (hybrid)** | Base |
| **Precision (+rerank)** | +10-20% |
| **VRAM (embedding)** | ~700 MB |
| **VRAM (reranking)** | ~700 MB |

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [Nous Research](https://nousresearch.com) — Hermes Agent
- [Qwen](https://qwenlm.github.io) — Embedding and reranking models
- [Qdrant](https://qdrant.tech) — Vector DB
- [llama.cpp](https://github.com/ggerganov/llama.cpp) — Local inference

---

**Made with ❤️ by [Claudio Drews](https://github.com/ClaudioDrews)**
