"""
Pipeline principal de ingestão e busca semântica.

Comandos:
  python pipeline.py ingest <caminho>            — ingestão incremental (pula arquivos sem mudança)
  python pipeline.py ingest <caminho> --force    — apaga coleção e reindexada tudo do zero
  python pipeline.py stats                       — estatísticas da coleção
  python pipeline.py search "<query>"            — busca semântica híbrida (dense + sparse)
  python pipeline.py search "<query>" --prefix   — aplica instruction prefix (queries vagas)
  python pipeline.py search "<query>" -k 10      — top-10 resultados
  python pipeline.py search "<query>" --min-score 0.65 — filtra por score mínimo
"""
import hashlib
import json
import typer
from pathlib import Path
from rich.console import Console
from rich.progress import track

from ingest.loader import load_markdown, load_text
from ingest.detector import detect_type
from chunking.base import chunk_markdown, chunk_code, chunk_text, chunk_chat
from embedding.embedder import embed, compute_sparse
from storage.qdrant import (
    get_client, ensure_collection, upsert, delete_by_origin,
    search_collection, COLLECTION,
)

app = Console()
cli = typer.Typer(help="Pipeline RAG — ingestão, busca semântica híbrida.")

# Arquivo de hashes para ingestão incremental
HASH_FILE = Path("~/ai-stack/projects/ai-rag/data/index_hashes.json").expanduser()

CHUNKERS = {
    "markdown": chunk_markdown,
    "code":     chunk_code,
    "text":     chunk_text,
    # "chat" tratado separadamente — assinatura diferente (turns, não text)
}


# ---------------------------------------------------------------------------
# Helpers — hash incremental
# ---------------------------------------------------------------------------

def _load_hashes() -> dict:
    if HASH_FILE.exists():
        return json.loads(HASH_FILE.read_text())
    return {}


def _save_hashes(hashes: dict) -> None:
    HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
    HASH_FILE.write_text(json.dumps(hashes, indent=2, ensure_ascii=False))


def _file_hash(path: Path) -> str:
    """SHA-256 do conteúdo do arquivo. Determinístico entre runs."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _split_chat_turns(text: str) -> list[str]:
    """
    Divide texto de chat em turnos.
    Tenta separadores comuns; fallback para parágrafos duplos.
    """
    for sep in ["\n---\n", "\n***\n", "\n---"]:
        parts = [t.strip() for t in text.split(sep) if t.strip()]
        if len(parts) > 1:
            return parts
    # Fallback: parágrafos duplos
    return [t.strip() for t in text.split("\n\n") if t.strip()]


# ---------------------------------------------------------------------------
# Comando: ingest
# ---------------------------------------------------------------------------

@cli.command()
def ingest(
    path: str,
    force: bool = typer.Option(
        False, "--force",
        help="Apaga a coleção existente e reindexada tudo do zero. "
             "Necessário ao migrar para hybrid search ou após mudanças de schema."
    ),
):
    """
    Ingere documentos de um arquivo ou diretório.

    Ingestão incremental por padrão: arquivos sem mudança de conteúdo são ignorados.
    Arquivos modificados têm seus pontos antigos removidos antes de reinserir.
    Use --force para reindexar tudo independente de mudanças.
    """
    p = Path(path).expanduser()
    files = (
        list(p.rglob("*.md")) + list(p.rglob("*.py")) + list(p.rglob("*.txt"))
        if p.is_dir() else [p]
    )

    client = get_client()

    # ensure_collection lança RuntimeError se schema antigo e force=False
    ensure_collection(client, force=force)

    # Se force, limpar hashes salvos também
    hashes = {} if force else _load_hashes()

    changed = 0
    skipped = 0

    for f in track(files, description="Ingerindo..."):
        fkey  = str(f)
        fhash = _file_hash(f)

        # Pular se conteúdo não mudou (e não é força-total)
        if not force and hashes.get(fkey) == fhash:
            skipped += 1
            continue

        try:
            # Carregar conteúdo
            if f.suffix == ".md":
                text, meta = load_markdown(f)
            else:
                text, meta = load_text(f)

            # Detectar tipo e chunkar
            dtype = detect_type(text, meta)

            if dtype == "chat":
                turns  = _split_chat_turns(text)
                chunks = chunk_chat(turns, meta)
            else:
                chunker = CHUNKERS.get(dtype, chunk_text)
                chunks  = chunker(text, meta)

            if not chunks:
                skipped += 1
                continue

            # Computar vetores
            texts         = [c["text"] for c in chunks]
            dense_vectors = embed(texts)
            sparse_vecs   = [compute_sparse(t) for t in texts]

            # Se arquivo já estava indexado, remover pontos antigos antes de inserir
            if fkey in hashes:
                delete_by_origin(client, fkey)

            upsert(client, chunks, dense_vectors, sparse_vecs)

            hashes[fkey] = fhash
            changed += 1

        except Exception as e:
            app.print(f"[red]Erro em {f}: {e}[/red]")

    _save_hashes(hashes)

    app.print(
        f"[green]Ingestão concluída.[/green] "
        f"{changed} arquivo(s) processado(s), "
        f"{skipped} ignorado(s) (sem mudanças)."
    )


# ---------------------------------------------------------------------------
# Comando: stats
# ---------------------------------------------------------------------------

@cli.command()
def stats():
    """Mostra estatísticas da coleção ai_memory."""
    client = get_client()
    info   = client.get_collection(COLLECTION)
    app.print(f"[bold]Coleção:[/bold] {COLLECTION}")
    app.print(f"[bold]Pontos:[/bold]  {info.points_count}")
    app.print(f"[bold]Status:[/bold]  {info.status}")


# ---------------------------------------------------------------------------
# Comando: search
# ---------------------------------------------------------------------------

@cli.command()
def search(
    query: str,
    top_k: int = typer.Option(5, "--top-k", "-k",
                               help="Número de resultados retornados."),
    with_prefix: bool = typer.Option(
        False, "--prefix",
        help="Aplica instruction prefix à query. "
             "Útil para queries curtas ou vagas (ex: 'venv', 'cuda', 'docker')."
    ),
    min_score: float = typer.Option(
        0.0, "--min-score",
        help="Score mínimo para incluir resultado. "
             "Scores RRF não são comparáveis a scores cosseno — use com cautela."
    ),
):
    """
    Busca semântica híbrida (dense + sparse BM25) nos documentos indexados.

    O hybrid search melhora a recuperação de termos técnicos exatos
    (hostnames, nomes de comandos, variáveis, flags) que o vetor denso
    sozinho pode não capturar.

    Exemplos:
      python pipeline.py search "como configurar venv"
      python pipeline.py search "pkill embed-server" --prefix
      python pipeline.py search "nvme0n1" -k 3
    """
    # Instruction prefix — melhora queries vagas/curtas com o Qwen3-Embedding
    if with_prefix:
        query_text = (
            "Instruct: Recupere documentos técnicos relevantes para a query\n"
            f"Query: {query}"
        )
    else:
        query_text = query

    app.print(f"\n[bold]Query:[/bold] {query}")
    if with_prefix:
        app.print("[dim]Instruction prefix ativo[/dim]")
    app.print("[dim]Modo: hybrid search (dense + sparse BM25, fusão RRF)[/dim]\n")

    # Vetorizar a query
    try:
        dense_vectors           = embed([query_text])
        sp_indices, sp_values   = compute_sparse(query_text)
    except Exception as e:
        app.print(f"[red]Erro ao conectar no embed-server: {e}[/red]")
        app.print("[yellow]Dica: rode 'embed-server' antes de buscar.[/yellow]")
        raise typer.Exit(1)

    dense_vector = dense_vectors[0]

    # Buscar no Qdrant
    client  = get_client()
    results = search_collection(
        client,
        dense_vector=dense_vector,
        sparse_indices=sp_indices,
        sparse_values=sp_values,
        top_k=top_k,
        min_score=min_score,
    )

    if not results:
        app.print("[yellow]Nenhum resultado encontrado.[/yellow]")
        return

    app.print(f"[bold]Top {len(results)} resultados:[/bold]\n")

    for i, hit in enumerate(results, 1):
        score   = hit.score
        payload = hit.payload

        # Scores RRF têm range diferente de cosseno — ajustar thresholds
        if score > 0.02:
            score_str = f"[green]{score:.4f}[/green]"
        elif score > 0.01:
            score_str = f"[yellow]{score:.4f}[/yellow]"
        else:
            score_str = f"[red]{score:.4f}[/red]"

        origin   = payload.get("origin", "desconhecido")
        filename = origin.split("/")[-1] if "/" in origin else origin
        section  = payload.get("h1", "") or payload.get("h2", "") or payload.get("h3", "")
        preview  = payload.get("preview", payload.get("text", "")[:200])

        app.print(f"[bold cyan]#{i}[/bold cyan] Score: {score_str}  |  [dim]{filename}[/dim]")
        if section:
            app.print(f"   [dim]Seção: {section}[/dim]")
        app.print(f"   {preview[:200]}")
        app.print("")


if __name__ == "__main__":
    cli()
