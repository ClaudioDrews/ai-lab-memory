"""
Pipeline de consolidação — executado via ai-consolidate (CLI) ou pelo worker automático.

Exporta:
  run_consolidation() -> int    — chamado pelo worker.py (retorna total de chunks ingeridos)
  consolidate (Typer command)   — CLI com --dry-run, --yes, --session-id
"""
import json
import time
import uuid
from pathlib import Path
from typing import Optional

import httpx
import typer
from rich.console import Console
from rich.progress import track

from session import get_turns, list_pending_sessions, mark_consolidated, delete_session
from reasoning import reason
from vram_guard import check_all
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, SparseVector

from bm25 import compute_sparse as _compute_sparse

app = typer.Typer()
console = Console()

COLLECTION  = "ai_memory"
EMBED_URL   = "http://localhost:8081/v1/embeddings"
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
LOG_PATH    = Path("~/ai-stack/logs/setup.log").expanduser()


# ---------------------------------------------------------------------------
# Funções auxiliares internas
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    entry = f"[{time.strftime('%Y-%m-%dT%H:%M:%S%z')}] {msg}"
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(entry + "\n")
    console.print(f"[dim]{entry}[/dim]")


def _embed_server_available() -> bool:
    """Verifica se o embed-server já está respondendo em :8081.
    Isso ocorre quando o ai-mem.service está no ar com o embed-server
    carregado via lifespan — nesse caso não é necessário subir outro
    nem verificar VRAM (o modelo já está alocado).
    """
    try:
        r = httpx.get("http://localhost:8081/v1/models", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


def _embed(texts: list[str], batch_size: int = 6) -> list[list[float]]:
    all_vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        r = httpx.post(
            EMBED_URL,
            json={"input": batch, "model": "qwen3-embedding"},
            timeout=120.0,
        )
        r.raise_for_status()
        all_vectors.extend([item["embedding"] for item in r.json()["data"]])
    return all_vectors


def _upsert_chunks(client: QdrantClient, chunks: list[dict],
                   vectors: list[list[float]]) -> None:
    points = []
    for chunk, vec in zip(chunks, vectors):
        sparse_idx, sparse_val = _compute_sparse(chunk["text"])
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector={
                "dense": vec,
                "sparse": SparseVector(
                    indices=sparse_idx, values=sparse_val
                ),
            },
            payload=chunk["metadata"] | {"text": chunk["text"]},
        ))
    client.upsert(collection_name=COLLECTION, points=points)


def _validate_insight(result: dict) -> bool:
    """Valida que o reasoning engine retornou o schema esperado."""
    return (
        isinstance(result, dict)
        and any(k in result for k in ("insights", "tasks", "context"))
        and isinstance(result.get("insights", []), list)
        and isinstance(result.get("tasks", []), list)
    )


def _build_chunks(sid: str, turns: list[dict], result: dict) -> list[dict]:
    """Monta a lista de chunks a partir do resultado do reasoning engine."""
    chunks = []
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    provider = result.get("provider_used", "unknown")

    base_meta = {
        "session_id": sid,
        "timestamp": timestamp,
        "origin": f"session:{sid}",
        "reasoning_provider": provider,
    }

    for insight in result.get("insights", []):
        chunks.append({
            "text": insight,
            "metadata": {**base_meta, "type": "insight", "preview": insight[:200]},
        })

    for task in result.get("tasks", []):
        chunks.append({
            "text": task,
            "metadata": {**base_meta, "type": "task", "preview": task[:200]},
        })

    for field, items in result.get("context", {}).items():
        for item in (items if isinstance(items, list) else []):
            chunks.append({
                "text": item,
                "metadata": {**base_meta, "type": "insight",
                             "subtype": field, "preview": item[:200]},
            })

    recent_turns = turns[-20:]
    conversation_text = "\n".join(
        f"{t['role'].upper()}: {t['content']}" for t in recent_turns
    )
    chunks.append({
        "text": conversation_text,
        "metadata": {**base_meta, "type": "conversation",
                     "preview": conversation_text[:200]},
    })

    return chunks


# ---------------------------------------------------------------------------
# run_consolidation — chamado pelo worker.py
# ---------------------------------------------------------------------------

def run_consolidation(pending: Optional[list[str]] = None) -> int:
    """
    Processa sessões pendentes. Retorna total de chunks ingeridos.
    Chamado pelo worker automático (sem interação humana).
    """
    if pending is None:
        pending = list_pending_sessions()

    if not pending:
        return 0

    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    total_chunks = 0

    for sid in pending:
        turns = get_turns(sid)
        if not turns:
            continue

        result = reason(turns)
        if result is None:
            _log(f"consolidate: todos os providers falharam para sessão {sid}")
            continue

        if not _validate_insight(result):
            _log(f"consolidate: schema inválido para sessão {sid} — pulando")
            continue

        chunks = _build_chunks(sid, turns, result)
        if not chunks:
            continue

        vectors = _embed([c["text"] for c in chunks])
        _upsert_chunks(client, chunks, vectors)

        mark_consolidated(sid)
        delete_session(sid)
        total_chunks += len(chunks)

        _log(f"consolidate: sessão {sid} — {len(chunks)} chunks ingeridos "
             f"(provider: {result.get('provider_used', 'unknown')})")

    return total_chunks


# ---------------------------------------------------------------------------
# CLI Typer
# ---------------------------------------------------------------------------

@app.command()
def consolidate(
    dry_run: bool = typer.Option(False, help="Mostrar o que seria feito sem executar"),
    session_id: Optional[str] = typer.Option(None, help="Consolidar apenas esta sessão"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Pular confirmação interativa"),
):
    """Consolidar sessões pendentes — extrai insights e ingere no Qdrant."""

    console.rule("[bold]ai-consolidate[/bold]")

    pending = [session_id] if session_id else list_pending_sessions()

    if not pending:
        console.print("[green]Nenhuma sessão pendente.[/green]")
        return

    console.print(f"Sessões pendentes: [bold]{len(pending)}[/bold]")
    for sid in pending:
        turns = get_turns(sid)
        console.print(f"  {sid}: {len(turns)} turnos")

    if dry_run:
        return

    # Human-in-the-loop (boas-praticas-agentes.md)
    if not yes:
        from rich.prompt import Confirm
        if not Confirm.ask("\nConfirmar consolidação?"):
            console.print("[yellow]Cancelado.[/yellow]")
            return

    # Se o embed-server já está no ar (ex: via lifespan do ai-mem.service),
    # não é necessário subir outro nem verificar VRAM — o modelo já está
    # alocado na GPU e a porta :8081 já está respondendo.
    if _embed_server_available():
        console.print("[dim]embed-server disponível em :8081 (ai-mem.service) — pulando VRAM check[/dim]")
    else:
        # Embed-server offline: verificar VRAM antes de tentar subir
        vram_status = check_all()
        if not vram_status.safe:
            console.print(f"[red]VRAM não segura: {vram_status.reason}[/red]")
            console.print("[dim]Dica: se o ai-mem.service estiver no ar, o embed-server já está disponível.[/dim]")
            raise typer.Exit(1)

    total = run_consolidation(pending)

    console.rule()
    console.print(f"[green]Concluído.[/green] {total} chunks ingeridos.")
    _log(f"ai-consolidate: {len(pending)} sessões, {total} chunks total")


if __name__ == "__main__":
    app()
