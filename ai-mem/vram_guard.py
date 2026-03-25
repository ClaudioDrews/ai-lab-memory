"""
VRAM Guard — verificações de segurança antes de subir o embed-server.

Exporta:
  check_all() -> VramStatus         — resultado agregado (safe: bool)
  check_all_verbose() -> list[tuple] — resultado por verificação para debug
"""
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class VramStatus:
    safe: bool
    reason: Optional[str] = None


VRAM_THRESHOLD_MB = 4096


def _check_chat_server() -> VramStatus:
    """chat-server via PID file — ocupa 4.6GB, inviabiliza embed-server."""
    pid_file = Path("/tmp/chat-server.pid")
    if not pid_file.exists():
        return VramStatus(safe=True)
    try:
        pid = int(pid_file.read_text().strip())
        Path(f"/proc/{pid}").stat()
        return VramStatus(safe=False, reason="chat-server rodando (PID file ativo)")
    except (ValueError, FileNotFoundError, OSError):
        pid_file.unlink(missing_ok=True)
        return VramStatus(safe=True)


def _check_ollama_local() -> VramStatus:
    """
    Verifica se Ollama tem modelo local carregado na VRAM.
    Modelos :cloud não consomem VRAM local — são ignorados.
    """
    try:
        result = subprocess.run(
            ["ollama", "ps"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = result.stdout.strip().splitlines()
        # Linha 0 é o header; linhas seguintes são modelos carregados
        for line in lines[1:]:
            if line.strip() and ":cloud" not in line:
                return VramStatus(
                    safe=False,
                    reason=f"Ollama com modelo local na VRAM: {line.split()[0]}"
                )
        return VramStatus(safe=True)
    except Exception as e:
        # Se ollama não responder, assume seguro (não bloqueia por falha de ferramenta)
        return VramStatus(safe=True)


def _check_free_vram() -> VramStatus:
    """Verifica VRAM livre via nvidia-smi. Requer >= VRAM_THRESHOLD_MB livres."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        free_mb = int(result.stdout.strip())
        if free_mb < VRAM_THRESHOLD_MB:
            return VramStatus(
                safe=False,
                reason=f"VRAM livre insuficiente: {free_mb}MB (mínimo: {VRAM_THRESHOLD_MB}MB)"
            )
        return VramStatus(safe=True)
    except Exception as e:
        return VramStatus(safe=False, reason=f"nvidia-smi falhou: {e}")


# Mapa de verificações em ordem de prioridade
_CHECKS = [
    ("chat-server",    _check_chat_server),
    ("ollama-local",   _check_ollama_local),
    ("free-vram",      _check_free_vram),
]


def check_all() -> VramStatus:
    """
    Executa todas as verificações em casconata.
    Retorna o primeiro problema encontrado, ou VramStatus(safe=True).
    """
    for _, fn in _CHECKS:
        status = fn()
        if not status.safe:
            return status
    return VramStatus(safe=True)


def check_all_verbose() -> list[tuple[str, VramStatus]]:
    """Executa todas as verificações e retorna resultado por check (para debug)."""
    return [(name, fn()) for name, fn in _CHECKS]
