import asyncio
import json
import os
import subprocess
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from session import append_turn
from retrieval import retrieve_context, format_context_block
from worker import consolidation_worker

BACKEND_URL     = os.getenv("AI_MEM_BACKEND", "http://localhost:11434")
TOP_K           = int(os.getenv("AI_MEM_TOP_K", "5"))
EMBED_SERVER_CMD = [
    str(Path("~/ai-stack/projects/llama-cpp/build/bin/llama-server").expanduser()),
    "-m", str(Path("~/ai-stack/models/embedding/qwen3-embedding-0.6b-q8_0.gguf").expanduser()),
    "-ngl", "99",
    "--port", "8081",
    "--embedding",
    "--pooling", "last",
    "--ctx-size", "4096",
]

_embed_proc = None

async def _start_embed_server() -> bool:
    """Sobe embed-server se VRAM disponível. Retorna True se OK."""
    global _embed_proc
    from vram_guard import check_all
    status = check_all()
    if not status.safe:
        print(f"[lifespan] embed-server não subiu: {status.reason}")
        return False
    _embed_proc = subprocess.Popen(
        EMBED_SERVER_CMD,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    Path("/tmp/embed-server.pid").write_text(str(_embed_proc.pid))
    for _ in range(20):
        await asyncio.sleep(2)
        try:
            r = await asyncio.to_thread(
                httpx.get, "http://localhost:8081/v1/models", timeout=2.0
            )
            if r.status_code == 200:
                print("[lifespan] embed-server pronto")
                return True
        except Exception:
            pass
    print("[lifespan] embed-server timeout — continuando sem contexto")
    return False

async def _stop_embed_server() -> None:
    global _embed_proc
    if _embed_proc is not None:
        _embed_proc.terminate()
        try:
            await asyncio.to_thread(_embed_proc.wait, 10)
        except Exception:
            _embed_proc.kill()
        _embed_proc = None
    Path("/tmp/embed-server.pid").unlink(missing_ok=True)
    print("[lifespan] embed-server parado")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"ai-mem proxy iniciado — backend: {BACKEND_URL}")
    # Sobe embed-server no lifespan (modelo 0.6B — ~700 MiB VRAM)
    await _start_embed_server()
    task = asyncio.create_task(consolidation_worker())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await _stop_embed_server()

app = FastAPI(title="ai-mem", lifespan=lifespan)

def _extract_session_id(request: Request) -> str:
    return (
        request.headers.get("x-session-id")
        or request.headers.get("x-request-id")
        or str(uuid.uuid4())
    )

def _get_last_user_message(messages: list[dict]) -> Optional[str]:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return None

def _inject_context(messages: list[dict], context_block: str) -> list[dict]:
    if not context_block:
        return messages
    result = list(messages)
    if result and result[0].get("role") == "system":
        result[0] = {
            **result[0],
            "content": result[0]["content"] + "\n\n" + context_block,
        }
    else:
        result.insert(0, {"role": "system", "content": context_block})
    return result

@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai-mem"}

@app.get("/v1/models")
async def list_models():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BACKEND_URL}/v1/models", timeout=10.0)
        return JSONResponse(content=r.json(), status_code=r.status_code)

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    session_id = _extract_session_id(request)
    messages = body.get("messages", [])
    stream = body.get("stream", False)
    
    last_user_msg = _get_last_user_message(messages)
    context_block = ""
    
    if last_user_msg:
        try:
            chunks = retrieve_context(last_user_msg, top_k=TOP_K)
            context_block = format_context_block(chunks)
        except Exception as e:
            print(f"[retrieval] erro: {e} — continuando sem contexto")
    
    enriched_messages = _inject_context(messages, context_block)
    enriched_body = {**body, "messages": enriched_messages}
    
    if last_user_msg:
        append_turn(session_id, "user", last_user_msg)
    
    if stream:
        return await _stream_response(enriched_body, session_id)
    else:
        return await _sync_response(enriched_body, session_id)

async def _sync_response(body: dict, session_id: str) -> JSONResponse:
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{BACKEND_URL}/v1/chat/completions",
            json=body,
        )
        data = r.json()
        try:
            assistant_content = data["choices"][0]["message"]["content"]
            append_turn(session_id, "assistant", assistant_content)
        except (KeyError, IndexError):
            pass
        return JSONResponse(content=data, status_code=r.status_code)

async def _stream_response(body: dict, session_id: str) -> StreamingResponse:
    accumulated: list[str] = []
    
    async def event_stream() -> AsyncGenerator[bytes, None]:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{BACKEND_URL}/v1/chat/completions",
                    json=body,
                ) as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk
                        try:
                            text = chunk.decode("utf-8")
                            for line in text.split("\n"):
                                if line.startswith("data: ") and line != "data: [DONE]":
                                    data = json.loads(line[6:])
                                    delta = data["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        accumulated.append(content)
                        except Exception:
                            pass
        finally:
            full_response = " ".join(accumulated)
            if full_response:
                append_turn(session_id, "assistant", full_response)
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8083)
