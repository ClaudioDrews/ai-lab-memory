# 📡 API Reference

**Complete API reference for AI Lab Memory System.**

---

## 1. Overview

The AI Lab Memory API is **OpenAI-compatible**, allowing seamless integration with any OpenAI client.

**Base URL:** `http://localhost:8083/v1`

**Authentication:** Bearer token (configurable, default: `sk-local`)

---

## 2. Endpoints

### 2.1 Chat Completions

**POST** `/v1/chat/completions`

Chat with memory-augmented AI.

**Request:**

```bash
curl -X POST http://localhost:8083/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-local" \
  -d '{
    "model": "kimi-k2.5:cloud",
    "messages": [
      {"role": "user", "content": "What are the CUDA flags for llama.cpp?"}
    ],
    "stream": false
  }'
```

**Response:**

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1711375200,
  "model": "kimi-k2.5:cloud",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Based on retrieved memory, the flags are:\n- `-DGGML_CUDA=ON`\n- `-DGGML_CUDA_F16=ON`"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 150,
    "completion_tokens": 50,
    "total_tokens": 200
  }
}
```

**Streaming Response:**

```bash
curl -X POST http://localhost:8083/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-local" \
  -d '{
    "model": "kimi-k2.5:cloud",
    "messages": [
      {"role": "user", "content": "Explain RAG"}
    ],
    "stream": true
  }'
```

**Stream Response:**

```
data: {"choices": [{"delta": {"content": "RAG"}}]}
data: {"choices": [{"delta": {"content": " stands"}}]}
data: {"choices": [{"delta": {"content": " for"}}]}
...
data: [DONE]
```

---

### 2.2 List Models

**GET** `/v1/models`

List available models.

**Request:**

```bash
curl -s http://localhost:8083/v1/models \
  -H "Authorization: Bearer sk-local"
```

**Response:**

```json
{
  "object": "list",
  "data": [
    {
      "id": "kimi-k2.5:cloud",
      "object": "model",
      "created": 1711375200,
      "owned_by": "library"
    },
    {
      "id": "nemotron-3-super:cloud",
      "object": "model",
      "created": 1711375200,
      "owned_by": "library"
    }
  ]
}
```

---

### 2.3 Health Check

**GET** `/health`

Check service health.

**Request:**

```bash
curl -s http://localhost:8083/health
```

**Response:**

```json
{
  "status": "ok",
  "service": "ai-mem"
}
```

---

## 3. Python Client

### 3.1 OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8083/v1",
    api_key="sk-local"
)

# Chat
response = client.chat.completions.create(
    model="kimi-k2.5:cloud",
    messages=[
        {"role": "user", "content": "What is hybrid search?"}
    ]
)

print(response.choices[0].message.content)
```

### 3.2 Streaming

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8083/v1",
    api_key="sk-local"
)

stream = client.chat.completions.create(
    model="kimi-k2.5:cloud",
    messages=[
        {"role": "user", "content": "Explain consolidation"}
    ],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### 3.3 Async Client

```python
import asyncio
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="http://localhost:8083/v1",
    api_key="sk-local"
)

async def chat():
    response = await client.chat.completions.create(
        model="kimi-k2.5:cloud",
        messages=[
            {"role": "user", "content": "Hello!"}
        ]
    )
    print(response.choices[0].message.content)

asyncio.run(chat())
```

---

## 4. Request Parameters

### 4.1 Chat Completions

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | string | — | Model to use (e.g., `kimi-k2.5:cloud`) |
| `messages` | array | — | Array of message objects |
| `stream` | boolean | `false` | Enable streaming response |
| `temperature` | number | `1.0` | Sampling temperature |
| `top_p` | number | `1.0` | Nucleus sampling |
| `max_tokens` | integer | `null` | Maximum tokens to generate |
| `stop` | array/string | `null` | Stop sequences |

### 4.2 Message Object

| Parameter | Type | Description |
|-----------|------|-------------|
| `role` | string | `system`, `user`, or `assistant` |
| `content` | string | Message content |

**Example:**

```json
{
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is RAG?"}
  ]
}
```

---

## 5. Response Format

### 5.1 Chat Completion Response

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1711375200,
  "model": "kimi-k2.5:cloud",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "RAG stands for Retrieval-Augmented Generation."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 50,
    "completion_tokens": 30,
    "total_tokens": 80
  }
}
```

### 5.2 Error Response

```json
{
  "error": {
    "code": 401,
    "message": "Invalid API key",
    "type": "authentication_error"
  }
}
```

---

## 6. Error Codes

| Code | Type | Description |
|------|------|-------------|
| `400` | `invalid_request_error` | Invalid request parameters |
| `401` | `authentication_error` | Invalid or missing API key |
| `404` | `not_found_error` | Resource not found |
| `429` | `rate_limit_error` | Rate limit exceeded |
| `500` | `server_error` | Internal server error |
| `503` | `service_unavailable` | Service temporarily unavailable |

---

## 7. Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/v1/chat/completions` | 100 requests/minute |
| `/v1/models` | 1000 requests/minute |
| `/health` | Unlimited |

**Headers:**

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1711375260
```

---

## 8. Internal APIs

### 8.1 Embedding Server

**Port:** `:8081`

**Endpoint:** `POST /v1/embeddings`

```bash
curl -X POST http://localhost:8081/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "input": ["Hello world"],
    "model": "qwen3-embedding"
  }'
```

**Response:**

```json
{
  "model": "qwen3-embedding",
  "object": "list",
  "data": [
    {
      "index": 0,
      "embedding": [0.123, -0.456, ...],
      "object": "embedding"
    }
  ],
  "usage": {
    "prompt_tokens": 2,
    "total_tokens": 2
  }
}
```

### 8.2 Reranking Server

**Port:** `:8084`

**Endpoint:** `POST /v1/rerank`

```bash
curl -X POST http://localhost:8084/v1/rerank \
  -H "Content-Type: application/json" \
  -d '{
    "query": "CUDA flags",
    "documents": [
      "GGML_CUDA=ON enables CUDA",
      "Python is a language"
    ]
  }'
```

**Response:**

```json
{
  "model": "qwen3-reranker-0.6b-q8_0.gguf",
  "object": "list",
  "results": [
    {
      "index": 0,
      "relevance_score": 0.989
    },
    {
      "index": 1,
      "relevance_score": 0.00003
    }
  ]
}
```

---

## 9. Qdrant API

**Port:** `:6333`

### 9.1 Collection Info

```bash
curl -s http://localhost:6333/collections/ai_memory
```

### 9.2 Query Points

```bash
curl -X POST http://localhost:6333/collections/ai_memory/points/query \
  -H "Content-Type: application/json" \
  -d '{
    "prefetch": [
      {"query": [0.1, 0.2, ...], "using": "dense", "limit": 20}
    ],
    "limit": 5
  }'
```

---

## 10. Examples

### 10.1 Full Conversation

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8083/v1",
    api_key="sk-local"
)

messages = [
    {"role": "user", "content": "What is RAG?"}
]

# First message
response = client.chat.completions.create(
    model="kimi-k2.5:cloud",
    messages=messages
)
assistant_message = response.choices[0].message.content
messages.append({"role": "assistant", "content": assistant_message})

# Follow-up
messages.append({"role": "user", "content": "How does it work?"})
response = client.chat.completions.create(
    model="kimi-k2.5:cloud",
    messages=messages
)
print(response.choices[0].message.content)
```

### 10.2 Error Handling

```python
from openai import OpenAI, APIError

client = OpenAI(
    base_url="http://localhost:8083/v1",
    api_key="sk-local"
)

try:
    response = client.chat.completions.create(
        model="kimi-k2.5:cloud",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    print(response.choices[0].message.content)
except APIError as e:
    print(f"API Error: {e.code} - {e.message}")
```

---


