"""
Detecção de tipo de conteúdo.
Prioridade: extensão do arquivo > metadados > nome do arquivo > heurística de conteúdo.
"""

CODE_EXTENSIONS = {".py", ".sh", ".js", ".ts", ".go", ".rs", ".c", ".cpp", ".h"}

# Palavras no nome do arquivo que indicam conteúdo de chat/conversa
CHAT_FILENAME_KEYWORDS = {
    "chat", "conversa", "conversation", "dialogue",
    "dialogo", "roleplay", "sessao", "session",
}


def detect_type(text: str, metadata: dict) -> str:
    path = metadata.get("origin", "")
    filename = path.split("/")[-1].lower() if "/" in path else path.lower()
    # Remove extensão para análise do nome
    filename_stem = filename.rsplit(".", 1)[0] if "." in filename else filename

    # 1. Por extensão (mais confiável)
    for ext in CODE_EXTENSIONS:
        if path.endswith(ext):
            return "code"

    if path.endswith(".md"):
        # 2a. Metadado explícito tem prioridade sobre nome do arquivo
        if metadata.get("source") == "chat" or metadata.get("type") == "chat":
            return "chat"

        # 2b. Palavras-chave no nome do arquivo
        for kw in CHAT_FILENAME_KEYWORDS:
            if kw in filename_stem:
                return "chat"

        return "markdown"

    # 2. Por metadado explícito (para extensões não-md)
    if metadata.get("source") == "chat" or metadata.get("type") == "chat":
        return "chat"

    # 3. Heurística de conteúdo (fallback ~80% dos casos)
    if "def " in text or "class " in text:
        return "code"
    if "# " in text or "## " in text:
        return "markdown"
    if len(text.splitlines()) > 200 and "ERROR" in text:
        return "log"

    return "text"
