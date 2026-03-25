"""
Calcula IDF do corpus indexado no Qdrant.
Deve ser executado após ingestão significativa de novos documentos.
Recomendado: quando o corpus crescer ~30%.

Uso:
  memdev
  cd ~/ai-stack/projects/ai-mem
  python3 compute_idf.py
"""
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import typer
from rich.console import Console
from qdrant_client import QdrantClient

app = typer.Typer()
console = Console()

COLLECTION = "ai_memory"
DEFAULT_OUTPUT = Path("~/ai-stack/projects/ai-mem/data/idf.json").expanduser()
BATCH_SIZE = 100


def _tokenize(text: str) -> set[str]:
    """Retorna conjunto de tokens únicos por documento (para IDF)."""
    return set(re.findall(r"\b\w+\b", text.lower()))


@app.command()
def compute(
    output: Path = typer.Option(DEFAULT_OUTPUT, "--output", "-o"),
    min_df: int = typer.Option(2, "--min-df", help="Frequência mínima para incluir token"),
):
    """Calcula IDF do corpus e salva em JSON."""

    client = QdrantClient("localhost", port=6333)
    info = client.get_collection(COLLECTION)
    total_docs = info.points_count

    console.print(f"Corpus: [bold]{total_docs}[/bold] chunks")

    df: dict[str, int] = defaultdict(int)
    offset = None

    with console.status("Varrendo corpus..."):
        while True:
            results, next_offset = client.scroll(
                collection_name=COLLECTION,
                limit=BATCH_SIZE,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            if not results:
                break

            for point in results:
                text = point.payload.get("text", "")
                tokens = _tokenize(text)
                for token in tokens:
                    df[token] += 1

            offset = next_offset
            if offset is None:
                break

    console.print(f"Tokens únicos encontrados: [bold]{len(df)}[/bold]")

    # Calcular IDF suavizado
    idf: dict[str, float] = {}
    for token, freq in df.items():
        if freq < min_df:
            continue
        idf[token] = math.log((total_docs + 1) / (freq + 1)) + 1

    console.print(f"Tokens no IDF (min_df={min_df}): [bold]{len(idf)}[/bold]")

    # Exemplos dos extremos
    sorted_idf = sorted(idf.items(), key=lambda x: x[1])
    console.print("\n[bold]Tokens mais comuns (IDF baixo — penalizados):[/bold]")
    for token, score in sorted_idf[:10]:
        console.print(f"  {token}: {score:.4f}")

    console.print("\n[bold]Tokens mais raros (IDF alto — valorizados):[/bold]")
    for token, score in sorted_idf[-10:]:
        console.print(f"  {token}: {score:.4f}")

    # Salvar
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(idf, f, ensure_ascii=False, indent=2)

    console.print(f"\n[green]IDF salvo em: {output}[/green]")
    console.print(f"Total de documentos: {total_docs}")
    console.print(f"Total de tokens no IDF: {len(idf)}")


if __name__ == "__main__":
    app()
