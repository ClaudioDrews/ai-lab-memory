# 📖 Usage Examples

**Practical examples for using AI Lab Memory System.**

---

## 1. Quick Start

### 1.1 Basic Search

```bash
# Simple semantic search
ai-search "how to compile llama.cpp with CUDA"

# With custom top-k
ai-search "CUDA flags" --top-k 10

# With score threshold
ai-search "cmake build" --min-score 0.5
```

### 1.2 Check System Status

```bash
# View system statistics
ai-stats

# Expected output:
# Qdrant — ai_memory
#   Points  : 1196
#   Status  : green
#   Dense   : 1024d (Qwen3-Embedding-0.6B-Q8_0)
#   Sparse  : 30000d (BM25)
#
# Redis — sessions pending
#   Total : 0
#
# ai-mem :8083  ok
```

---

## 2. Hermes Agent Integration

### 2.1 Configure Hermes

```bash
# Set ai-mem as backend
hermes config set model.base_url "http://localhost:8083/v1"
hermes config set model.provider "auto"
hermes config set model.default "kimi-k2.5:cloud"
```

### 2.2 Chat with Memory

```bash
# Ask a technical question
hermes chat -q "What are the cmake flags for llama.cpp with CUDA?"

# Expected output:
# Based on retrieved memory, the flags are:
# - `-DGGML_CUDA=ON` — Enables CUDA support
# - `-DGGML_CUDA_F16=ON` — Uses FP16 for +performance
# - `-DCMAKE_CUDA_ARCHITECTURES=86` — RTX 30xx architecture
```

### 2.3 Interactive Session

```bash
# Start interactive chat
hermes chat

# Then ask questions:
# > Tell me about the RAG pipeline
# > How does consolidation work?
# > What models are available?
```

---

## 3. Manual Ingestion

### 3.1 Ingest Documents

```bash
# Activate RAG environment
ragdev

# Navigate to pipeline
cd your-project-dir/ai-rag

# Ingest a single file
python3 pipeline.py ingest your-documents-dir/my-note.md

# Ingest a directory
python3 pipeline.py ingest your-documents-dir/

# Force reindex (ignore hash cache)
python3 pipeline.py ingest your-documents-dir/ --force
```

### 3.2 View Statistics

```bash
# View collection stats
python3 pipeline.py stats

# Expected output:
# Collection: ai_memory
# Points  : 1196
# Status  : green
```

### 3.3 Manual Search

```bash
# Search with Python
python3 pipeline.py search "CUDA compilation" --top-k 5

# With score display
python3 pipeline.py search "cmake flags" --show-scores
```

---

## 4. Consolidation Management

### 4.1 Manual Consolidation

```bash
# Consolidate all pending sessions
ai-consolidate --yes

# Dry-run (see what would be done)
ai-consolidate --dry-run

# Consolidate specific session
ai-consolidate --session-id abc123
```

### 4.2 Check Pending Sessions

```bash
# View pending sessions in Redis
docker exec redis redis-cli keys "ai-mem:session:*"

# Count sessions
docker exec redis redis-cli keys "ai-mem:session:*" | wc -l
```

### 4.3 Configure Auto-Consolidation

**Edit `config.yaml`:**

```yaml
consolidation:
  auto: true              # Enable/disable
  check_interval_minutes: 15  # Check every 15 min
  min_sessions: 3         # Minimum sessions to trigger
  vram_threshold_mb: 4096 # Minimum free VRAM (MB)
```

---

## 5. Reranking

### 5.1 Enable/Disable Reranking

**Edit `config.yaml`:**

```yaml
retrieval:
  reranking:
    enabled: true  # Set to false to disable
```

### 5.2 Test Reranking

```bash
# Search without reranking (faster)
ai-search "python docker deployment" --top-k 5 --no-rerank

# Search with reranking (more accurate)
ai-search "python docker deployment" --top-k 5 --rerank
```

### 5.3 Compare Results

```python
# Compare with and without reranking
import requests

query = "compile llama.cpp CUDA"

# Without reranking
r1 = requests.post("http://localhost:8083/v1/chat/completions",
    json={"messages": [{"role": "user", "content": query}]},
    headers={"Authorization": "Bearer sk-local"}
)
print("Without rerank:", r1.json()["choices"][0]["message"]["content"])

# With reranking (configure in config.yaml first)
# ... same query, results will be more relevant
```

---

## 6. Advanced Usage

### 6.1 Custom Backend

**Use OpenAI instead of Ollama:**

```yaml
# config.yaml
proxy:
  backend_url: "https://api.openai.com/v1"
```

```bash
# Set API key
export OPENAI_API_KEY=sk-your-key

# Restart ai-mem
systemctl --user restart ai-mem.service
```

### 6.2 Multiple LLM Backends

**Rotate between providers:**

```yaml
# config.yaml
reasoning:
  providers:
    - name: "gemini"
      model: "gemini-2.5-flash"
      api_key_env: "GEMINI_API_KEY"
    - name: "groq"
      model: "llama-3.3-70b-versatile"
      api_key_env: "GROQ_API_KEY"
    - name: "openrouter"
      model: "google/gemma-3-4b-it:free"
      api_key_env: "OPENROUTER_API_KEY"
```

### 6.3 Filter by Type

```bash
# Search only code chunks
ai-search "docker compose" --filter-type code

# Search only insights
ai-search "CUDA optimization" --filter-type insight

# Multiple types
ai-search "build flags" --filter-type code,doc
```

---

## 7. Monitoring and Debugging

### 7.1 View Logs

```bash
# ai-mem logs
journalctl --user -u ai-mem.service -n 50

# Follow logs in real-time
journalctl --user -u ai-mem.service -f

# Consolidation logs
tail -f logs/setup.log
```

### 7.2 Health Checks

```bash
# ai-mem health
curl -s http://localhost:8083/health | python3 -m json.tool

# Embedding server
curl -s http://localhost:8081/v1/models

# Reranking server
curl -s http://localhost:8084/v1/models

# Qdrant
curl -s http://localhost:6333/collections/ai_memory

# Redis
docker exec redis redis-cli ping
```

### 7.3 Monitor VRAM

```bash
# Check GPU usage
nvidia-smi

# Monitor in real-time
watch -n 1 nvidia-smi

# Check specific processes
nvidia-smi --query-compute-apps=pid,process_name,used_memory
```

---

## 8. Backup and Restore

### 8.1 Backup Qdrant

```bash
# Stop Qdrant
docker stop qdrant

# Backup storage
tar czf qdrant-backup-$(date +%Y%m%d).tar.gz \
    ~/ai-services/qdrant/storage/

# Restart Qdrant
docker start qdrant
```

### 8.2 Restore Qdrant

```bash
# Stop Qdrant
docker stop qdrant

# Restore storage
tar xzf qdrant-backup-20260325.tar.gz \
    -C ~/ai-services/qdrant/

# Restart Qdrant
docker start qdrant
```

### 8.3 Export Sessions

```bash
# Export Redis sessions
docker exec redis redis-cli KEYS "ai-mem:session:*" > sessions-backup.txt

# Export specific session
docker exec redis redis-cli LRANGE ai-mem:session:abc123 0 -1 > session-abc123.json
```

---

## 9. Performance Optimization

### 9.1 Tune Batch Size

**Reduce if VRAM is tight:**

```yaml
# config.yaml
embedding:
  batch_size: 4  # Default: 6
```

### 9.2 Adjust Retrieval

**Retrieve more candidates, rerank better:**

```yaml
retrieval:
  top_k: 5
  reranking:
    retrieve_multiplier: 4  # Retrieve 20, rerank to 5
```

### 9.3 Cache Embeddings (Future)

```bash
# Enable embedding cache in Redis
# (Not yet implemented)
```

---

## 10. Common Use Cases

### 10.1 Code Search

```bash
# Search for code snippets
ai-search "docker compose python flask" --filter-type code

# Search for specific function
ai-search "def embed_query" --filter-type code
```

### 10.2 Documentation Search

```bash
# Search documentation
ai-search "how to install CUDA" --filter-type doc

# Search with context
ai-search "llama.cpp build instructions" --top-k 10
```

### 10.3 Conversation History

```bash
# Search past conversations
ai-search "previous discussion about RAG" --filter-type conversation

# Find specific insight
ai-search "insight about hybrid search" --filter-type insight
```

---

## 11. API Usage

### 11.1 Direct API Call

```bash
# Chat with memory
curl -X POST http://localhost:8083/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-local" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is hybrid search?"}
    ]
  }'
```

### 11.2 Python Client

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8083/v1",
    api_key="sk-local"
)

response = client.chat.completions.create(
    model="kimi-k2.5:cloud",
    messages=[
        {"role": "user", "content": "Explain RAG pipeline"}
    ]
)

print(response.choices[0].message.content)
```

---

## 12. Troubleshooting

### 12.1 Common Issues

**Issue:** No results from search

```bash
# Check if Qdrant has points
ai-stats

# If 0 points, ingest documents
ragdev
cd your-project-dir/ai-rag
python3 pipeline.py ingest your-documents-dir/
```

**Issue:** Slow response times

```bash
# Check VRAM usage
nvidia-smi

# Disable reranking for faster response
# Edit config.yaml: retrieval.reranking.enabled = false
```

**Issue:** Consolidation not running

```bash
# Check if auto is enabled
cat your-project-dir/ai-mem/config.yaml | grep -A 5 "consolidation:"

# Check pending sessions
docker exec redis redis-cli keys "ai-mem:session:*"

# Manually trigger
ai-consolidate --yes
```

---

**Happy searching!**
