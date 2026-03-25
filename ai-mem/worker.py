"""
Consolidation Worker — background task asyncio.
Roda dentro do lifespan do FastAPI (mem-server).
Controlado por consolidation.auto no config.yaml.

ARQUITETURA v3.1:
- embed-server NÃO sobe no lifespan do server.py
- embed-server é gerenciado APENAS por este worker
- Sobe quando: auto=true + ≥3 sessões + VRAM segura
- Derruba após consolidação (finally block)
- Libera ~3.1GB VRAM quando não em uso

Loop a cada CHECK_INTERVAL_MINUTES minutos:
1. Verifica se auto está habilitado no config.yaml
2. Verifica se há sessões suficientes no Redis
3. Verifica chat-server explícito (PID file)
4. Verifica VRAM geral (ollama local + free MB)
5. Sobe embed-server, aguarda health check, consolida, para embed-server
"""
import asyncio
import subprocess
import time
from pathlib import Path
from typing import Optional
import httpx
from rich.console import Console
from session import list_pending_sessions
from vram_guard import check_all

console = Console()

CHECK_INTERVAL_MINUTES = 15
MIN_SESSIONS = 3
EMBED_SERVER_URL = "http://localhost:8081"
EMBED_SERVER_STARTUP_TIMEOUT_S = 40
MAX_RETRIES_BEFORE_WARN = 3
LOG_PATH = Path("~/ai-stack/logs/setup.log").expanduser()

EMBED_SERVER_CMD = [
    str(Path("~/ai-stack/projects/llama-cpp/build/bin/llama-server").expanduser()),
    "-m", str(Path("~/ai-stack/models/embedding/qwen3-embedding-0.6b-q8_0.gguf").expanduser()),
    "-ngl", "99",
    "--port", "8081",
    "--embedding",
    "--pooling", "last",
    "--ctx-size", "4096",
]

_embed_process: Optional[subprocess.Popen] = None

def _log(msg: str) -> None:
    entry = f"[{time.strftime('%Y-%m-%dT%H:%M:%S%z')}] {msg}"
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(entry + "\n")
    console.print(f"[dim]{entry}[/dim]")

def _chat_server_running() -> bool:
    """Verificação explícita do chat-server via PID file."""
    pid_file = Path("/tmp/chat-server.pid")
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text().strip())
        Path(f"/proc/{pid}").stat()
        return True
    except (ValueError, FileNotFoundError, OSError):
        pid_file.unlink(missing_ok=True)
        return False

async def _wait_for_embed_server() -> bool:
    """
    Health check robusto — aguarda embed-server responder HTTP 200.
    Retorna True se pronto, False se timeout.
    """
    for _ in range(EMBED_SERVER_STARTUP_TIMEOUT_S // 2):
        await asyncio.sleep(2)
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{EMBED_SERVER_URL}/v1/models",
                    timeout=3.0,
                )
                if r.status_code == 200:
                    return True
        except Exception:
            pass
    return False

async def _start_embed_server() -> bool:
    """
    Sobe o embed-server e aguarda health check robusto.
    Verifica VRAM antes de subir (vram_guard).
    Retorna True se pronto, False se VRAM insuficiente ou timeout.
    """
    global _embed_process
    
    # Verificação de VRAM antes de tentar subir
    from vram_guard import check_all
    status = check_all()
    if not status.safe:
        _log(f"worker: embed-server não subiu — {status.reason}")
        return False
    
    _embed_process = subprocess.Popen(
        EMBED_SERVER_CMD,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    Path("/tmp/embed-server.pid").write_text(str(_embed_process.pid))
    
    ready = await _wait_for_embed_server()
    if not ready:
        _log("worker: embed-server não respondeu HTTP 200 no timeout — abortando")
        await _stop_embed_server()
        return False
    
    _log("worker: embed-server pronto em :8081")
    return True

async def _stop_embed_server() -> None:
    """Para o embed-server e limpa o PID file."""
    global _embed_process
    if _embed_process is not None:
        _embed_process.terminate()
        try:
            _embed_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _embed_process.kill()
        _embed_process = None
    Path("/tmp/embed-server.pid").unlink(missing_ok=True)
    _log("worker: embed-server parado")

async def _run_consolidation() -> int:
    """Executa a consolidação em thread separada (não bloqueia o event loop)."""
    from consolidate import run_consolidation
    return await asyncio.to_thread(run_consolidation)

async def consolidation_worker() -> None:
    """
    Loop principal. Roda indefinidamente até ser cancelado.
    
    Fluxo por iteração:
    1. Verifica config.yaml (auto: true/false)
    2. Conta sessões pendentes no Redis (mínimo: MIN_SESSIONS)
    3. Verifica chat-server via PID file (proteção OOM)
    4. Verifica VRAM geral via vram_guard
    5. Se tudo OK: sobe embed-server → consolida → para embed-server
    6. Aguarda CHECK_INTERVAL_MINUTES e repete
    """
    _log("worker: iniciado — consolidação automática habilitada")
    retries = 0
    
    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)

            # FASE 0: Verificar se automação está habilitada
            config_path = Path("~/ai-stack/projects/ai-mem/config.yaml").expanduser()
            if config_path.exists():
                if "auto: false" in config_path.read_text():
                    console.print("[dim]worker: auto=false no config — inativo[/dim]")
                    continue

            # FASE 1: Sessões suficientes?
            pending = list_pending_sessions()
            if len(pending) < MIN_SESSIONS:
                console.print(
                    f"[dim]worker: {len(pending)} sessões pendentes "
                    f"(mínimo: {MIN_SESSIONS}) — aguardando[/dim]"
                )
                retries = 0
                continue

            # FASE 2: chat-server explícito (proteção OOM RTX 3060)
            if _chat_server_running():
                retries += 1
                console.print(
                    f"[yellow]worker: chat-server detectado — "
                    f"adiando consolidação (tentativa {retries})[/yellow]"
                )
                if retries >= MAX_RETRIES_BEFORE_WARN:
                    _log(
                        f"worker: AVISO — consolidação adiada há "
                        f"{retries * CHECK_INTERVAL_MINUTES} min. "
                        f"chat-server ocupando VRAM."
                    )
                continue

            # FASE 3: Verificações gerais de VRAM
            vram_status = check_all()
            if not vram_status.safe:
                retries += 1
                console.print(
                    f"[yellow]worker: VRAM não segura "
                    f"({vram_status.reason}) — "
                    f"tentativa {retries}/{MAX_RETRIES_BEFORE_WARN}[/yellow]"
                )
                if retries >= MAX_RETRIES_BEFORE_WARN:
                    _log(
                        f"worker: AVISO — consolidação adiada há "
                        f"{retries * CHECK_INTERVAL_MINUTES} min. "
                        f"Motivo: {vram_status.reason}"
                    )
                continue

            retries = 0

            # FASE 4: Consolidar
            _log(f"worker: iniciando consolidação — {len(pending)} sessões pendentes")

            started = await _start_embed_server()
            if not started:
                continue

            try:
                chunks_total = await _run_consolidation()
                _log(
                    f"worker: consolidação concluída — "
                    f"{len(pending)} sessões, {chunks_total} chunks ingeridos"
                )
            finally:
                # GARANTIA: embed-server sempre é parado após consolidação
                await _stop_embed_server()

        except asyncio.CancelledError:
            _log("worker: encerrado — cleanup final")
            # Cleanup garantido mesmo se cancelado durante consolidação
            await _stop_embed_server()
            return
        except Exception as e:
            _log(f"worker: erro inesperado — {e}")
            # Cleanup em caso de erro inesperado
            await _stop_embed_server()
            # Re-raise para logging do systemd (opcional)
            raise
