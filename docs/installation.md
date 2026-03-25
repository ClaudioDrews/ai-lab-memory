# 📦 Installation Guide

**Step-by-step guide to install AI Lab Memory System.**

---

## 1. Prerequisites

### 1.1 Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **RAM** | 8 GB | 16 GB |
| **VRAM** | 4 GB | 6+ GB (RTX 3060+) |
| **Storage** | 10 GB | 50+ GB SSD |
| **GPU** | NVIDIA (CUDA 12+) | RTX 3060 or better |

### 1.2 Software Requirements

- **OS:** Linux (Ubuntu 24.04 / Linux Mint 22+)
- **Python:** 3.12+
- **Docker:** 24+ (for Qdrant + Redis)
- **NVIDIA Driver:** 550+ (for GPU acceleration)
- **Git:** 2.40+

### 1.3 Verify Prerequisites

```bash
# Check Python version
python3 --version  # Should be 3.12+

# Check Docker
docker --version   # Should be 24+

# Check NVIDIA driver
nvidia-smi         # Should show GPU and driver version

# Check Git
git --version      # Should be 2.40+
```

---

## 2. Clone Repository

```bash
# Clone the repository
git clone https://github.com/ClaudioDrews/ai-lab-memory.git
cd ai-lab-memory
```

---

## 3. Install System Dependencies

### 3.1 Ubuntu/Debian

```bash
# Update package list
sudo apt update

# Install required packages
sudo apt install -y \
    python3.12 \
    python3.12-venv \
    python3-pip \
    docker.io \
    docker-compose \
    git \
    curl \
    wget \
    build-essential \
    cmake \
    llama-server
```

### 3.2 Enable Docker for Non-Root User

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Apply group changes (or logout/login)
newgrp docker

# Verify
docker ps  # Should work without sudo
```

---

## 4. Install Python Dependencies

### 4.1 Create Virtual Environment

```bash
# For ai-mem
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### 4.2 Install Requirements

```bash
# Install ai-mem dependencies
pip install -r ai-mem/requirements.txt

# Install RAG pipeline dependencies
pip install -r ai-rag/requirements.txt
```

---

## 5. Install Docker Services

### 5.1 Start Qdrant and Redis

```bash
# Create data directories
mkdir -p data/qdrant data/redis

# Start services with Docker Compose
docker-compose up -d qdrant redis

# Verify services
docker ps  # Should show qdrant and redis running
```

### 5.2 Verify Services

```bash
# Check Qdrant
curl -s http://localhost:6333/collections | python3 -m json.tool

# Check Redis
docker exec redis redis-cli ping  # Should return PONG
```

---

## 6. Download Models

### 6.1 Embedding Model

```bash
# Download Qwen3-Embedding-0.6B-Q8_0
python3 -c "
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id='Gideon531/Qwen3-Embedding-0.6B-Q8_0-GGUF',
    filename='qwen3-embedding-0.6b-q8_0.gguf',
    local_dir='models/embedding'
)
"
```

### 6.2 Reranking Model (Optional)

```bash
# Download Qwen3-Reranker-0.6B-Q8_0
python3 -c "
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id='ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF',
    filename='qwen3-reranker-0.6b-q8_0.gguf',
    local_dir='models/reranker'
)
"
```

---

## 7. Configure Environment

### 7.1 Create .env File

```bash
# Copy example environment file
cp .env.example .env

# Edit with your API keys
nano .env
```

### 7.2 Required Variables

```bash
# === LLM Providers ===
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
OPENROUTER_API_KEY=your_openrouter_key

# === HuggingFace ===
HF_TOKEN=your_hf_token

# === ai-mem ===
AI_MEM_API_KEY=sk-local
AI_MEM_BACKEND=http://localhost:11434
```

---

## 8. Initialize Qdrant Collection

```bash
# Create ai_memory collection
curl -X PUT http://localhost:6333/collections/ai_memory \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "dense": {"size": 1024, "distance": "Cosine"},
      "sparse": {"bm25": {}}
    }
  }'
```

---

## 9. Start ai-mem Service

### 9.1 Start Embedding Server

```bash
# Start embed-server in background
llama-server \
    -m models/embedding/qwen3-embedding-0.6b-q8_0.gguf \
    -ngl 99 \
    --port 8081 \
    --embedding \
    --pooling last &

echo $! > /tmp/embed-server.pid
```

### 9.2 Start Rerank Server (Optional)

```bash
# Start rerank-server in background
llama-server \
    -m models/reranker/qwen3-reranker-0.6b-q8_0.gguf \
    -ngl 99 \
    --port 8084 \
    --reranking &

echo $! > /tmp/rerank-server.pid
```

### 9.3 Start ai-mem Proxy

```bash
# Activate virtual environment
source venv/bin/activate

# Start ai-mem
cd ai-mem
python3 -m uvicorn server:app --host 0.0.0.0 --port 8083
```

---

## 10. Verify Installation

### 10.1 Health Checks

```bash
# Check ai-mem
curl -s http://localhost:8083/health | python3 -m json.tool
# Expected: {"status": "ok", "service": "ai-mem"}

# Check embedding
curl -s http://localhost:8081/v1/models | python3 -m json.tool

# Check reranking (if installed)
curl -s http://localhost:8084/v1/models | python3 -m json.tool

# Check Qdrant
curl -s http://localhost:6333/collections/ai_memory | python3 -m json.tool
```

### 10.2 Test Search

```bash
# Test semantic search
ai-search "how to compile llama.cpp with CUDA" --top-k 3

# Expected: Relevant chunks about CUDA compilation
```

---

## 11. Install Shell Functions

```bash
# Add shell functions to your bashrc
cat >> your-shell-config << 'EOF'

# AI Lab Memory Functions
ai-up() {
    source .env
    systemctl --user is-active ai-mem.service >/dev/null 2>&1 || \
        systemctl --user start ai-mem.service
    echo "✅ ai-mem active on :8083"
}

ai-down() {
    echo "ℹ️  ai-mem.service is a permanent stack."
    echo "    To stop: systemctl --user stop ai-mem.service"
}

ai-stats() {
    source .env
    memdev
    cd your-project-dir/projects/ai-mem
    python3 search.py stats
    deactivate
}

ai-search() {
    source .env
    memdev
    cd your-project-dir/projects/ai-mem
    python3 search.py search "$@"
    deactivate
}

ai-reindex-idf() {
    memdev && cd your-project-dir/projects/ai-mem && python3 compute_idf.py && deactivate
}
EOF

# Reload bashrc
source your-shell-config
```

---

## 12. Troubleshooting

### 12.1 Common Issues

**Issue:** `docker: permission denied`

```bash
# Solution: Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

**Issue:** `CUDA out of memory`

```bash
# Solution: Reduce batch size in config.yaml
embedding:
  batch_size: 4  # Reduce from 6 to 4
```

**Issue:** `Connection refused to Qdrant`

```bash
# Solution: Check if Qdrant is running
docker ps | grep qdrant

# Restart if needed
docker-compose restart qdrant
```

### 12.2 Get Help

```bash
# Check logs
journalctl --user -u ai-mem.service -n 50

# Check Docker logs
docker logs qdrant --tail 50
docker logs redis --tail 50
```

---

## 13. Next Steps

After installation:

1. **Configure** — See [Configuration Guide](configuration.md)
2. **Usage** — See [Usage Examples](usage.md)
3. **Integrate Hermes** — Configure Hermes Agent integration

---

**Installation complete!**
