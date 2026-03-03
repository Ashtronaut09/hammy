"""LLM backend dispatcher for Hammy."""

import json
import shutil
import subprocess
from typing import Optional

import requests

from hammy import ui


def get_auto_backend() -> Optional[str]:
    """Detect available LLM backend. Returns backend key or None."""
    if shutil.which("claude"):
        return "claude_code"
    if shutil.which("codex"):
        return "codex_cli"
    try:
        requests.get("http://localhost:11434", timeout=2)
        return "ollama"
    except Exception:
        return None


def _ollama_running() -> bool:
    try:
        requests.get("http://localhost:11434", timeout=2)
        return True
    except Exception:
        return False


def _start_ollama() -> subprocess.Popen:
    import time
    proc = subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        time.sleep(0.5)
        if _ollama_running():
            return proc
    return proc


def _stop_ollama(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def ensure_ollama() -> tuple[bool, Optional[subprocess.Popen]]:
    """Start Ollama if needed. Returns (is_ready, proc_or_None)."""
    if _ollama_running():
        return True, None
    if not shutil.which("ollama"):
        ui.warn("Ollama is not installed.")
        return False, None
    with ui.wheel_status("Waking up Ollama..."):
        proc = _start_ollama()
    if _ollama_running():
        ui.ok("Ollama is ready.")
        return True, proc
    ui.warn("Ollama didn't start in time — saving raw transcript only.")
    return False, None


def structure_with_claude_code(transcript: str, source_name: str,
                                duration: str, date_str: str,
                                prompt: str) -> Optional[str]:
    """Invoke Claude Code CLI via subprocess."""
    full_prompt = _build_prompt(prompt, source_name, duration, date_str, transcript)
    try:
        result = subprocess.run(
            ["claude", "-p", full_prompt],
            capture_output=True, text=True, timeout=300,
        )
    except Exception as e:
        ui.warn(f"Claude Code CLI failed: {e}")
        return None
    if result.returncode != 0:
        ui.warn(f"Claude Code CLI failed: {result.stderr.strip()}")
        return None
    output = result.stdout.strip()
    if not output:
        ui.warn("Claude Code CLI returned empty output.")
        return None
    return output


def structure_with_codex_cli(transcript: str, source_name: str,
                              duration: str, date_str: str,
                              prompt: str) -> Optional[str]:
    """Invoke OpenAI Codex CLI via subprocess."""
    full_prompt = _build_prompt(prompt, source_name, duration, date_str, transcript)
    try:
        result = subprocess.run(
            ["codex", "exec", "--quiet", full_prompt],
            capture_output=True, text=True, timeout=300,
        )
    except Exception as e:
        ui.warn(f"OpenAI Codex CLI failed: {e}")
        return None
    if result.returncode != 0:
        ui.warn(f"OpenAI Codex CLI failed: {result.stderr.strip()}")
        return None
    output = result.stdout.strip()
    if not output:
        ui.warn("OpenAI Codex CLI returned empty output.")
        return None
    return output


def structure_with_ollama(transcript: str, source_name: str,
                           duration: str, date_str: str,
                           prompt: str, model: str) -> Optional[str]:
    """Invoke Ollama HTTP API."""
    user_content = (
        f"Metadata:\n"
        f"- Date: {date_str}\n"
        f"- Source: {source_name}\n"
        f"- Duration: {duration}\n\n"
        f"Raw Transcript:\n{transcript}"
    )
    try:
        resp = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ],
                "options": {"num_ctx": 32768, "num_predict": 4096},
                "stream": True,
            },
            stream=True,
            timeout=600,
        )
        resp.raise_for_status()
        parts = []
        for raw in resp.iter_lines():
            if not raw:
                continue
            data = json.loads(raw)
            parts.append(data.get("message", {}).get("content", ""))
            if data.get("done"):
                break
        output = "".join(parts).strip()
        if not output:
            ui.warn("Ollama returned empty output.")
            return None
        return output
    except Exception as e:
        ui.warn(f"Ollama failed: {e}")
        return None


def structure_with_anthropic_api(transcript: str, source_name: str,
                                  duration: str, date_str: str,
                                  prompt: str, api_key: str) -> Optional[str]:
    """Invoke Anthropic API directly."""
    try:
        import anthropic
    except ImportError:
        ui.warn("anthropic package not installed. Run: pip install anthropic")
        return None
    full_prompt = _build_prompt(prompt, source_name, duration, date_str, transcript)
    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": full_prompt}],
        )
        return message.content[0].text.strip()
    except Exception as e:
        ui.warn(f"Anthropic API failed: {e}")
        return None


def structure_with_openai_api(transcript: str, source_name: str,
                               duration: str, date_str: str,
                               prompt: str, api_key: str) -> Optional[str]:
    """Invoke OpenAI API directly."""
    try:
        import openai
    except ImportError:
        ui.warn("openai package not installed. Run: pip install openai")
        return None
    full_prompt = _build_prompt(prompt, source_name, duration, date_str, transcript)
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": full_prompt}],
            max_tokens=4096,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        ui.warn(f"OpenAI API failed: {e}")
        return None


def _build_prompt(prompt: str, source_name: str, duration: str,
                  date_str: str, transcript: str) -> str:
    return (
        f"{prompt}\n\n"
        f"Metadata:\n"
        f"- Date: {date_str}\n"
        f"- Source: {source_name}\n"
        f"- Duration: {duration}\n\n"
        f"Raw Transcript:\n{transcript}"
    )
