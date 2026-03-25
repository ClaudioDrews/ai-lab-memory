"""
CLI de busca direta na memória do Qdrant.

Se o embed-server não estiver no ar, sobe automaticamente,
executa a busca e derruba em seguida.

Uso:
  python3 search.py search "query"
  python3 search.py search "query" --top-k 10
  python3 search.py search "query" --type insight
  python3 search.py search "query" --show-scores
  python3 search.py stats
"""
import subprocess
import time
from pathlib import Path
from typing import Optional

import httpx
import typer
from rich import box
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()

VALID_TYPES = ["doc", "code", "insight", "task", "conversation"]

EMBED_SERVER_URL = "http://localhost:8081"
EMBED_SERVER_STARTUP_TIMEOUT_S = 40
EMBED_SERVER_CMD = [
    str(Path("~/ai-stack/projects/llama-cpp/build/bin/llama-server").expanduser()),
    "-m", str(Path("~/ai-stack/models/embedding/Qwen3-Embedding-4B-Q6_K.gguf").expanduser()),
    "-ngl", "99",
    "--port", "8081",
    "--embedding",
    "--pooling", "last",
]


def _embed_server_running() -> bool:
    """Verifica se o embed-server já está no ar via HTTP."""
    try:
        r = httpx.get(f"{EMBED_SERVER_URL}/v1/models", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def _wait_for_embed_server() -> bool:
    """Poll até embed-server responder HTTP 200. Retorna True se pronto."""
    for _ in range(EMBED_SERVER_STARTUP_TIMEOUT_S // 2):
        time.sleep(2)
        try:
            r = httpx.get(f"{EMBED_SERVER_URL}/v1/models", timeout=2.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
    return False


def _start_embed_server() -> Optional[subprocess.Popen]:
    """Sobe embed-server. Retorna o processo ou None se falhou."""
    console.print("[dim]Subindo embed-server...[/dim]", end=" ")
    proc = subprocess.Popen(
        EMBED_SERVER_CMD,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    Path("/tmp/embed-server.pid").write_text(str(proc.pid))
    ready = _wait_for_embed_server()
    if ready:
        console.print("[green]pronto[/green]")
        return proc
    else:
        console.print("[red]timeout[/red]")
        proc.terminate()
        Path("/tmp/embed-server.pid").unlink(missing_ok=True)
        return None


def _stop_embed_server(proc: subprocess.Popen) -> None:
    """Para o embed-server e limpa o PID file."""
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    Path("/tmp/embed-server.pid").unlink(missing_ok=True)
    console.print("[dim]embed-server parado[/dim]")


@app.command()
def search(
    query: str = typer.Argument(..., help="Texto para buscar na memória"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Número de resultados"),
    filter_type: Optional[str] = typer.Option(
        None, "--type", "-t",
        help=f"Filtrar por tipo: {', '.join(VALID_TYPES)}"
    ),
    show_scores: bool = typer.Option(False, "--show-scores", "-s"),
    min_score: float = typer.Option(0.0, "--min-score", help="Score mínimo (0.0–1.0)"),
):
    """Busca semântica híbrida na coleção ai_memory do Qdrant."""

    if filter_type and filter_type not in VALID_TYPES:
        console.print(f"[red]Tipo inválido: {filter_type}[/red]")
        console.print(f"Tipos válidos: {', '.join(VALID_TYPES)}")
        raise typer.Exit(1)

    # Gerenciar embed-server automaticamente
    managed_proc = None
    if not _embed_server_running():
        managed_proc = _start_embed_server()
        if managed_proc is None:
            console.print("[red]Não foi possível subir o embed-server.[/red]")
            raise typer.Exit(1)

    try:
        from retrieval import retrieve_context

        console.print(f"\n[bold]Query:[/bold] {query}")
        if filter_type:
            console.print(f"[bold]Filtro:[/bold] type={filter_type}")
        console.print()

        filter_types = [filter_type] if filter_type else None
        chunks = retrieve_context(
            query=query,
            top_k=top_k,
            score_threshold=min_score,
            filter_types=filter_types,
        )

        if not chunks:
            console.print("[yellow]Nenhum resultado encontrado.[/yellow]")
            return

        table = Table(
            box=box.ROUNDED,
            show_lines=True,
            expand=True,
        )

        if show_scores:
            table.add_column("Score", style="cyan", width=7, justify="right")
        table.add_column("Tipo", style="green", width=14)
        table.add_column("Origem", style="dim", width=38)
        table.add_column("Conteúdo", ratio=1)

        for chunk in chunks:
            content = chunk["text"]
            if len(content) > 300:
                content = content[:297] + "..."

            row = []
            if show_scores:
                score = chunk.get("score", 0.0)
                row.append(f"{score:.4f}")
            row.extend([
                chunk.get("type", "—"),
                chunk.get("origin", "—"),
                content,
            ])
            table.add_row(*row)

        console.print(table)
        console.print(f"\n[dim]{len(chunks)} resultado(s) encontrado(s)[/dim]")

    finally:
        # Derrubar embed-server apenas se foi subido por este comando
        if managed_proc is not None:
            _stop_embed_server(managed_proc)


@app.command()
def stats():
    """Mostra estatísticas da coleção ai_memory e sessões Redis pendentes."""
    from qdrant_client import QdrantClient
    from session import list_pending_sessions

    # Qdrant
    client = QdrantClient("localhost", port=6333)
    info = client.get_collection("ai_memory")

    console.print("\n[bold]Qdrant — ai_memory[/bold]")
    console.print(f"  Pontos  : {info.points_count}")
    console.print(f"  Status  : {info.status}")
    console.print(f"  Dense   : 1024d (Qwen3-Embedding-0.6B-Q8_0)")
    console.print(f"  Sparse  : 30000d (BM25)")

    # Redis
    pending = list_pending_sessions()
    console.print(f"\n[bold]Redis — sessões pendentes[/bold]")
    console.print(f"  Total : {len(pending)}")
    for sid in pending:
        console.print(f"  - {sid}")

    # ai-mem health
    try:
        r = httpx.get("http://localhost:8083/health", timeout=2.0)
        status = r.json().get("status", "?")
        console.print(f"\n[bold]ai-mem :8083[/bold]  {status}")
    except Exception:
        console.print(f"\n[bold]ai-mem :8083[/bold]  [red]não responde[/red]")

    console.print()


if __name__ == "__main__":
    app()
