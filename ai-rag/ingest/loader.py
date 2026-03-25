"""
Carregamento de documentos com extração de frontmatter Obsidian.
"""
from pathlib import Path
import frontmatter

def load_markdown(path: str | Path) -> tuple[str, dict]:
    note = frontmatter.load(str(path))
    meta = dict(note.metadata)
    meta.setdefault("origin", str(path))
    meta.setdefault("type", "markdown")
    return note.content, meta

def load_text(path: str | Path) -> tuple[str, dict]:
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    meta = {"origin": str(path), "type": "text"}
    return text, meta
