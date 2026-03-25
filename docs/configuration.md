# ⚙️ Configuration Guide

**Detailed configuration for all AI Lab Memory components.**

---

## 1. Overview

The AI Lab Memory System consists of several components, each with its own configuration:

| Component | Config File | Location |
|-----------|-------------|----------|
| **ai-mem** | `config.yaml` | `ai-lab-memory/ai-mem/` |
| **ai-rag** | `config.yaml` | `ai-lab-memory/ai-rag/` |
| **Environment** | `.env` | `~/.config/ai-lab/` |
| **Shell** | `aliases.sh`, `functions.sh` | `your-shell-config/` |

---

## 2. ai-mem Configuration

### 2.1 config.yaml Structure

```yaml
# ai-lab-memory/ai-mem/config.yaml

proxy:
  host: "0.0.0.0"
  port: 8083
  backend_url: "http://localhost:11434"  # LLM backend (Ollama, etc.)

retrieval:
  collection: "ai_memory"
  top_k: 5
  score_threshold: 0.0
  inject_types: ["doc", "code", "insight", "task", "conversation"]
  reranking:
    enabled: true
    server_url: "http://localhost:8084/v1/rerank"
    retrieve_multiplier: 4  # Retrieve top_k*4, rerank to top_k

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
  embed_server_url: "http://localhost:8081"
  embed_server_startup_timeout_s: 40
  max_retries_before_warn: 3
  log_path: "ai-lab-memory/logs/setup.log"

reasoning:
  providers:
    - name: "gemini"
      model: "gemini-2.5-flash"
      api_key_env: "GEMINI_API_KEY"
      base_url: "https://generativelanguage.googleapis.com/v1beta"
      timeout_s: 20
    - name: "groq"
      model: "llama-3.3-70b-versatile"
      api_key_env: "GROQ_API_KEY"
      base_url: "https://api.groq.com/openai/v1"
      timeout_s: 15
    # ... more providers

embedding:
  model_path: ai-lab-memory/models/embedding/qwen3-embedding-0.6b-q8_0.gguf
  dimension: 1024
  batch_size: 6
```

### 2.2 Key Parameters

#### Proxy

| Parameter | Default | Description |
|-----------|---------|-------------|
| `host` | `0.0.0.0` | Bind address (0.0.0.0 = all interfaces) |
| `port` | `8083` | Port for OpenAI-compatible API |
| `backend_url` | `http://localhost:11434` | LLM backend URL (Ollama, OpenAI, etc.) |

#### Retrieval

| Parameter | Default | Description |
|-----------|---------|-------------|
| `collection` | `ai_memory` | Qdrant collection name |
| `top_k` | `5` | Number of chunks to retrieve |
| `score_threshold` | `0.0` | Minimum score threshold |
| `reranking.enabled` | `true` | Enable/disable reranking |
| `reranking.retrieve_multiplier` | `4` | Retrieve `top_k * 4`, rerank to `top_k` |

#### Session

| Parameter | Default | Description |
|-----------|---------|-------------|
| `redis_host` | `localhost` | Redis server host |
| `redis_port` | `6379` | Redis server port |
| `ttl_hours` | `24` | Session TTL in hours |
| `max_turns_per_session` | `200` | Maximum turns per session |

#### Consolidation

| Parameter | Default | Description |
|-----------|---------|-------------|
| `auto` | `true` | Enable automatic consolidation |
| `check_interval_minutes` | `15` | Check interval in minutes |
| `min_sessions` | `3` | Minimum sessions to trigger consolidation |
| `vram_threshold_mb` | `4096` | Minimum free VRAM (MB) to consolidate |

---

## 3. Environment Variables

### 3.1 .env File

**Location:** `.env (or your secure location)`

**Permissions:** `600` (owner read-only)

```bash
# === LLM Providers ===
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
OPENROUTER_API_KEY=your_openrouter_key
MISTRAL_API_KEY=your_mistral_key
CEREBRAS_API_KEY=your_cerebras_key

# === HuggingFace ===
HF_TOKEN=your_hf_token

# === GitHub ===
GITHUB_TOKEN=your-github-token-here

# === ai-mem ===
AI_MEM_API_KEY=your-api-key-here
AI_MEM_BACKEND=http://localhost:11434
AI_MEM_TOP_K=5

# === Ollama ===
OLLAMA_HOST="http://localhost:11434"
OLLAMA_API_KEY=your_ollama_key
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CLOUD_HOST=https://ollama.com

# === Other Services ===
QDRANT_URI=http://localhost:6333
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 3.2 Load Environment

```bash
# Load in current shell
source .env (or your secure location)

# Auto-load in bashrc (add to ~/.bashrc)
source .env (or your secure location)
```

---

## 4. Shell Configuration

### 4.1 Aliases

**Location:** `your-shell-config/aliases.sh`

```bash
# Embedding Server
alias embed-server='llama-server \
    -m ai-lab-memory/models/embedding/qwen3-embedding-0.6b-q8_0.gguf \
    -ngl 99 \
    --port 8081 \
    --embedding \
    --pooling last & echo $! > /tmp/embed-server.pid'

alias embed-server-stop='kill $(cat /tmp/embed-server.pid) 2>/dev/null && rm -f /tmp/embed-server.pid'

# Reranking Server (optional)
alias rerank-server='llama-server \
    -m ai-lab-memory/models/reranker/qwen3-reranker-0.6b-q8_0.gguf \
    -ngl 99 \
    --port 8084 \
    --reranking & echo $! > /tmp/rerank-server.pid'

alias rerank-server-stop='kill $(cat /tmp/rerank-server.pid) 2>/dev/null && rm -f /tmp/rerank-server.pid'
```

### 4.2 Functions

**Location:** `your-shell-config/functions.sh`

```bash
# Virtual environment shortcuts
aidev()  { source your-project-dir/venv/bin/activate; }
ragdev() { source ~/ai-rag/venv/bin/activate; }
svcdev() { source ~/ai-svc/venv/bin/activate; }
memdev() { source ~/ai-mem/venv/bin/activate; }

# ai-mem control
ai-up() {
    source .env (or your secure location)
    systemctl --user is-active ai-mem.service >/dev/null 2>&1 || \
        systemctl --user start ai-mem.service
    echo "✅ ai-mem active on :8083"
}

ai-down() {
    echo "ℹ️  ai-mem.service is a permanent stack."
    echo "    To stop: systemctl --user stop ai-mem.service"
}

# Search and stats
ai-search() {
    source .env (or your secure location)
    memdev
    cd ai-lab-memory/projects/ai-mem
    python3 search.py search "$@"
    deactivate
}

ai-stats() {
    memdev
    cd ai-lab-memory/projects/ai-mem
    python3 search.py stats
    deactivate
}

ai-reindex-idf() {
    memdev && cd ai-lab-memory/projects/ai-mem && python3 compute_idf.py && deactivate
}
```

---

## 5. Docker Configuration

### 5.1 docker-compose.yml

**Location:** `your-docker-compose-dir/docker-compose.yml`

```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:1.17.0
    container_name: qdrant
    restart: unless-stopped
    ports:
      - "6333:6333"  # REST API
      - "6334:6334"  # gRPC
    volumes:
      - ./qdrant/storage:/qdrant/storage
    environment:
      - QDRANT__SERVICE__GRPC_PORT=6334

  redis:
    image: redis:7-alpine
    container_name: redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - ./redis/data:/data
```

### 5.2 Start Services

```bash
# Start all services
cd ~/ai-services
docker-compose up -d

# Check status
docker ps

# View logs
docker logs qdrant --tail 50
docker logs redis --tail 50
```

---

## 6. Hermes Agent Integration

### 6.1 Configure Hermes

```bash
# Set ai-mem as backend
hermes config set model.base_url "http://localhost:8083/v1"
hermes config set model.provider "auto"
hermes config set model.default "kimi-k2.5:cloud"

# Add to Hermes .env
echo 'AI_MEM_API_KEY=sk-local' >> ~/.hermes/.env
echo 'OPENAI_BASE_URL=http://localhost:8083/v1' >> ~/.hermes/.env
echo 'OPENAI_API_KEY=sk-local' >> ~/.hermes/.env
```

### 6.2 Verify Integration

```bash
# Test with Hermes
hermes chat -q "What are the flags to compile llama.cpp with CUDA?"

# Expected: Response with memory context
```

---

## 7. Performance Tuning

### 7.1 Embedding Batch Size

**Trade-off:** Larger batch = faster but more VRAM

```yaml
embedding:
  batch_size: 6  # Default
  # batch_size: 4  # Reduce if VRAM is tight
  # batch_size: 8  # Increase if VRAM available
```

### 7.2 Reranking Toggle

**Enable for precision, disable for speed:**

```yaml
retrieval:
  reranking:
    enabled: true   # Set to false to disable reranking
```

### 7.3 Consolidation Frequency

**Adjust based on usage:**

```yaml
consolidation:
  check_interval_minutes: 15  # Check every 15 min
  min_sessions: 3             # Minimum 3 sessions to consolidate
```

---

## 8. Security Best Practices

### 8.1 File Permissions

```bash
# Secrets file
chmod 600 .env (or your secure location)

# Config files
chmod 644 ai-lab-memory/ai-mem/config.yaml
```

### 8.2 Network Binding

**Bind to localhost only (default):**

```yaml
proxy:
  host: "127.0.0.1"  # More secure
  # host: "0.0.0.0"  # All interfaces (less secure)
```

### 8.3 API Keys

- Never commit `.env` to Git
- Use environment variables for secrets
- Rotate keys periodically

---

## 9. Backup and Restore

### 9.1 Backup Qdrant Data

```bash
# Stop Qdrant
docker stop qdrant

# Backup storage
tar czf qdrant-backup-$(date +%Y%m%d).tar.gz your-docker-compose-dir/qdrant/storage/

# Restart Qdrant
docker start qdrant
```

### 9.2 Backup Redis Data

```bash
# Backup Redis AOF file
cp your-docker-compose-dir/redis/data/appendonly.aof \
   ~/backups/redis-appendonly.aof.$(date +%Y%m%d)
```

---

## 10. Troubleshooting Configuration

### 10.1 Validate YAML

```bash
# Check YAML syntax
python3 -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

### 10.2 Test Endpoints

```bash
# Test ai-mem
curl -s http://localhost:8083/health

# Test embedding
curl -s http://localhost:8081/v1/models

# Test reranking
curl -s http://localhost:8084/v1/models

# Test Qdrant
curl -s http://localhost:6333/collections
```

---

**Configuration complete!**
