import json
import os
import time
from typing import Optional

import httpx
from json_repair import repair_json
from rich.console import Console

console = Console()

PROVIDERS = [
    {
        "name": "gemini",
        "api_key_env": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-2.5-flash",
        "style": "gemini",
        "timeout": 15,
    },
    {
        "name": "groq",
        "api_key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "style": "openai",
        "timeout": 15,
    },
    {
        "name": "nvidia",
        "api_key_env": "NVIDIA_API_KEY",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "meta/llama-3.3-70b-instruct",
        "style": "openai",
        "timeout": 15,
    },
    {
        "name": "mistral",
        "api_key_env": "MISTRAL_API_KEY",
        "base_url": "https://api.mistral.ai/v1",
        "model": "mistral-small-latest",
        "style": "openai",
        "timeout": 15,
    },
    {
        "name": "openrouter",
        "api_key_env": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "google/gemma-3-4b-it:free",
        "style": "openai",
        "timeout": 20,
    },
    {
        "name": "cerebras",
        "api_key_env": "CEREBRAS_API_KEY",
        "base_url": "https://api.cerebras.ai/v1",
        "model": "llama3.1-8b",
        "style": "openai",
        "timeout": 15,
    },
]

REASONING_PROMPT = """Analise os turnos de conversa abaixo e extraia informações estruturadas.
Retorne APENAS um objeto JSON válido, sem markdown, sem texto adicional, com exatamente estes campos:

{
  "insights": ["fato aprendido sobre o usuário ou sistema", ...],
  "tasks": ["tarefa pendente identificada", ...],
  "context": {
    "user_preferences": ["preferência identificada", ...],
    "system_state": ["estado do sistema mencionado", ...],
    "decisions_made": ["decisão tomada", ...]
  }
}

Turnos da conversa:
"""


def _parse_response(text: str) -> Optional[dict]:
    text = text.strip()
    repaired = repair_json(text)
    if not repaired or repaired == "{}":
        return None
    try:
        result = json.loads(repaired)
        if not isinstance(result, dict):
            return None
        if "insights" not in result and "tasks" not in result:
            return None
        return result
    except Exception:
        return None


def _call_openai_style(provider: dict, turns: list[dict]) -> Optional[dict]:
    api_key = os.getenv(provider["api_key_env"], "")
    if not api_key:
        return None

    prompt = REASONING_PROMPT + json.dumps(turns, ensure_ascii=False, indent=2)

    try:
        r = httpx.post(
            f"{provider['base_url']}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": provider["model"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            },
            timeout=provider["timeout"],
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
        return _parse_response(text)
    except Exception as e:
        console.print(f"[yellow]  {provider['name']}: {e}[/yellow]")
        return None


def _call_gemini(provider: dict, turns: list[dict]) -> Optional[dict]:
    api_key = os.getenv(provider["api_key_env"], "")
    if not api_key:
        return None

    prompt = REASONING_PROMPT + json.dumps(turns, ensure_ascii=False, indent=2)

    try:
        r = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{provider['model']}:generateContent?key={api_key}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1},
            },
            timeout=provider["timeout"],
        )
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return _parse_response(text)
    except Exception as e:
        console.print(f"[yellow]  gemini: {e}[/yellow]")
        return None


def reason(turns: list[dict]) -> Optional[dict]:
    for provider in PROVIDERS:
        console.print(f"  Tentando [cyan]{provider['name']}[/cyan]...", end=" ")
        t0 = time.time()

        if provider["style"] == "gemini":
            result = _call_gemini(provider, turns)
        else:
            result = _call_openai_style(provider, turns)

        elapsed = time.time() - t0

        if result is not None:
            elapsed = time.time() - t0
            console.print(f"[green]✓[/green] ({elapsed:.1f}s)")
            result["provider_used"] = provider["name"]
            return result
        else:
            console.print(f"[red]✗[/red] ({elapsed:.1f}s)")

    return None
