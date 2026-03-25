# 📚 Examples

**Practical examples for using AI Lab Memory System.**

---

## Available Examples

| Example | Description | Run |
|---------|-------------|-----|
| **basic-search.py** | Simple semantic search | `python basic-search.py "your query"` |
| **hermes-integration.py** | Hermes Agent integration | `python hermes-integration.py` |
| **streaming-chat.py** | Streaming chat responses | `python streaming-chat.py "your query"` |

---

## Setup

### 1. Install Dependencies

```bash
# Activate virtual environment
cd ~/ai-lab-memory
source venv/bin/activate

# Install OpenAI SDK
pip install openai
```

### 2. Start ai-mem

```bash
# Start ai-mem service
systemctl --user start ai-mem.service

# Verify it's running
curl http://localhost:8083/health
```

### 3. Run Examples

```bash
# Basic search
python examples/basic-search.py "What is RAG?"

# Hermes integration
python examples/hermes-integration.py

# Streaming chat
python examples/streaming-chat.py "Explain hybrid search"
```

---

## Customize

### Change API Key

If you configured a different API key:

```python
# In example files, change:
API_KEY = "sk-local"
# To:
API_KEY = "your-custom-key"
```

### Change Backend URL

If running on a different host:

```python
# In example files, change:
BASE_URL = "http://localhost:8083/v1"
# To:
BASE_URL = "http://your-server:8083/v1"
```

---

## Troubleshooting

### Connection Refused

```bash
# Check if ai-mem is running
systemctl --user status ai-mem.service

# Start if needed
systemctl --user start ai-mem.service
```

### No Results

```bash
# Check if Qdrant has points
curl http://localhost:6333/collections/ai_memory

# If empty, ingest documents
cd ~/ai-stack/projects/ai-rag
python3 pipeline.py ingest ~/Documents/
```

### High Latency

```bash
# Check VRAM usage
nvidia-smi

# Disable reranking for faster responses
# Edit config.yaml: retrieval.reranking.enabled = false
```

---

**Happy coding!** 🎉
