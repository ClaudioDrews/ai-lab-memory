"""
Chunking adaptativo por tipo de conteúdo.
Token-aware via tiktoken (cl100k_base, compatível com Qwen3).
"""
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
import tiktoken

_enc = tiktoken.get_encoding("cl100k_base")

def _token_len(text: str) -> int:
    return len(_enc.encode(text, disallowed_special=()))

def chunk_markdown(text: str, meta: dict, size: int = 800, overlap: int = 150) -> list[dict]:
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
        strip_headers=False,
    )
    recursive = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        length_function=_token_len,
        separators=["\n\n", "\n", ". ", " "],
    )
    chunks = []
    for hc in header_splitter.split_text(text):
        if _token_len(hc.page_content) <= size:
            m = {**meta, **hc.metadata, "preview": hc.page_content[:200]}
            chunks.append({"text": hc.page_content, "metadata": m})
        else:
            for sub in recursive.split_text(hc.page_content):
                m = {**meta, **hc.metadata, "preview": sub[:200]}
                chunks.append({"text": sub, "metadata": m})
    return chunks

def chunk_code(text: str, meta: dict, size: int = 500, overlap: int = 50) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size, chunk_overlap=overlap,
        length_function=_token_len,
        separators=["\n\nclass ", "\n\ndef ", "\n\n", "\n", " "],
    )
    return [{"text": c, "metadata": {**meta, "preview": c[:200]}}
            for c in splitter.split_text(text)]

def chunk_chat(turns: list[str], meta: dict,
               turns_per_chunk: int = 2, overlap_turns: int = 1,
               max_tokens: int = 1500) -> list[dict]:
    """
    Chunking de chat com limite de tokens.
    Se um chunk exceder max_tokens, divide recursivamente.
    """
    chunks = []
    step = max(1, turns_per_chunk - overlap_turns)
    
    for i in range(0, len(turns), step):
        batch = turns[i:i + turns_per_chunk]
        
        for turn in batch:
            # Processar cada turno individualmente com limite de tokens
            _chunk_single_turn(turn, meta, max_tokens, chunks)
    
    return chunks


def _chunk_single_turn(text: str, meta: dict, max_tokens: int, chunks: list) -> None:
    """Divide um único turno em chunks dentro do limite de tokens."""
    if _token_len(text) <= max_tokens:
        chunks.append({"text": text, "metadata": {**meta, "preview": text[:200]}})
        return
    
    # Turno gigante: dividir por parágrafos
    paragraphs = text.split('\n\n')
    current = ""
    
    for para in paragraphs:
        if not para.strip():
            continue
        
        test = current + "\n\n" + para if current else para
        
        if _token_len(test) > max_tokens:
            # Salvar chunk atual se não estiver vazio
            if current:
                chunks.append({"text": current, "metadata": {**meta, "preview": current[:200]}})
            
            # Se parágrafo único excede limite, dividir por linhas
            if _token_len(para) > max_tokens:
                lines = para.split('\n')
                current = ""
                for line in lines:
                    test_line = current + "\n" + line if current else line
                    if _token_len(test_line) > max_tokens and current:
                        chunks.append({"text": current, "metadata": {**meta, "preview": current[:200]}})
                        current = line
                    else:
                        current = test_line
                if current:
                    chunks.append({"text": current, "metadata": {**meta, "preview": current[:200]}})
            else:
                current = para
        else:
            current = test
    
    if current:
        chunks.append({"text": current, "metadata": {**meta, "preview": current[:200]}})

def chunk_text(text: str, meta: dict, size: int = 600, overlap: int = 120) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size, chunk_overlap=overlap,
        length_function=_token_len,
        separators=["\n\n", "\n", ". ", " "],
    )
    return [{"text": c, "metadata": {**meta, "preview": c[:200]}}
            for c in splitter.split_text(text)]
