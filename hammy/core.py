"""Hammy — core processing logic."""

import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from hammy import ui
from hammy.config import load_config
from hammy.transcribe import SUPPORTED_EXTENSIONS, transcribe_audio
from hammy.llm import (
    get_auto_backend,
    ensure_ollama,
    structure_with_claude_code,
    structure_with_codex_cli,
    structure_with_ollama,
    structure_with_anthropic_api,
    structure_with_openai_api,
)
from hammy.updater import background_check, join_background_check

try:
    from importlib.resources import files as _pkg_files
    _BUNDLED_PROMPT = _pkg_files("hammy").joinpath("prompt.txt").read_text(encoding="utf-8")
except Exception:
    _BUNDLED_PROMPT = (
        "Summarize this meeting transcript into structured notes with a summary, "
        "key takeaways, action items, and detailed notes."
    )


def load_prompt(config: dict) -> str:
    """Load prompt: workspace override first, then bundled default."""
    workspace = Path(config["stash_dir"]).parent
    user_prompt = workspace / "prompt.txt"
    if user_prompt.exists():
        return user_prompt.read_text(encoding="utf-8").strip()
    return _BUNDLED_PROMPT.strip()


def extract_date_from_filename(stem: str) -> str:
    """Extract recording date from audio filename. Falls back to today if not found."""
    m = re.search(r'\b(\d{1,2})-(\d{1,2})-((?:19|20)\d{2})\b', stem)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year}-{month:02d}-{day:02d}"

    m = re.search(r'\b((?:19|20)\d{2})-(\d{1,2})-(\d{1,2})\b', stem)
    if m:
        year, a, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a > 12 and b <= 12:
            return f"{year}-{b:02d}-{a:02d}"
        elif 1 <= a <= 12:
            return f"{year}-{a:02d}-{b:02d}"

    m = re.search(r'\b((?:19|20)\d{2})\s*[-–]?\s*(\d{1,2})[\s-](\d{1,2})\b', stem)
    if m:
        year, a, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= a <= 12 and 0 <= b <= 31:
            return f"{year}-{a:02d}-{b if b != 0 else 1:02d}"

    m = re.search(r'\b(\d{2})\.(\d{2})(\d{2})\b', stem)
    if m:
        year, month, day = int(m.group(1)) + 2000, int(m.group(2)), int(m.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year}-{month:02d}-{day:02d}"

    m = re.search(r'\b((?:19|20)\d{2})\b', stem)
    if m:
        return m.group(1)

    return datetime.now().strftime("%Y-%m-%d")


def find_audio_files(path: str) -> list[Path]:
    """Return a list of audio file paths from a file or directory."""
    p = Path(path)
    if p.is_file():
        if p.suffix.lower() in SUPPORTED_EXTENSIONS:
            return [p]
        ui.warn(f"Unsupported file type: {p.suffix}")
        return []
    elif p.is_dir():
        files = sorted(
            f for f in p.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
        )
        if not files:
            ui.warn(f"No supported audio files found in {p}")
        return files
    else:
        ui.err(f"Path not found: {p}")
        return []


def build_raw_output(transcript: str, source_name: str,
                     duration: str, date_str: str) -> str:
    return (
        f"# Transcript: {source_name}\n\n"
        f"**Date:** {date_str}\n"
        f"**Source:** {source_name}\n"
        f"**Duration:** {duration}\n\n"
        f"---\n\n"
        f"## Raw Transcript\n\n"
        f"{transcript}\n"
    )


def append_raw_transcript(structured_notes: str, transcript: str) -> str:
    return f"{structured_notes}\n\n---\n\n## Raw Transcript\n\n{transcript}\n"


def _run_llm(backend: str, transcript: str, source_name: str,
             duration: str, date_str: str, config: dict) -> str | None:
    """Dispatch to the correct LLM backend."""
    prompt = load_prompt(config)
    kwargs = dict(
        transcript=transcript, source_name=source_name,
        duration=duration, date_str=date_str, prompt=prompt,
    )
    if backend == "claude_code":
        return structure_with_claude_code(**kwargs)
    if backend == "codex_cli":
        return structure_with_codex_cli(**kwargs)
    if backend == "ollama":
        return structure_with_ollama(**kwargs, model=config.get("ollama_model", "llama3.2:3b"))
    if backend == "anthropic_api":
        key = config.get("anthropic_api_key") or ""
        if not key:
            ui.warn("No Anthropic API key configured. Run `hammy setup`.")
            return None
        return structure_with_anthropic_api(**kwargs, api_key=key)
    if backend == "openai_api":
        key = config.get("openai_api_key") or ""
        if not key:
            ui.warn("No OpenAI API key configured. Run `hammy setup`.")
            return None
        return structure_with_openai_api(**kwargs, api_key=key)
    return None


def process_file(audio_path: Path, output_dir: Path,
                 llm_backend: str | None, config: dict) -> None:
    """Process a single audio file: transcribe and optionally structure."""
    date_str = extract_date_from_filename(audio_path.stem)
    source_name = audio_path.name
    output_filename = f"{date_str}_{audio_path.stem}.md"
    output_path = output_dir / output_filename

    ui.section(audio_path.name)

    if output_path.exists():
        ui.info("↷ Already stashed — skipping.")
        return

    try:
        with ui.wheel_status("Hammy is running on the wheel..."):
            transcript, duration = transcribe_audio(audio_path, config)
    except Exception as e:
        ui.err(f"Error transcribing {audio_path.name}: {e}")
        return

    if not transcript:
        ui.warn("No transcript produced — skipping.")
        return

    ui.ok(f"Transcribed — {duration}")

    structured = None
    if llm_backend and llm_backend != "none":
        spinner_msg = {
            "claude_code": "Sorting the seeds of wisdom with Claude...",
            "codex_cli":   "Asking Codex to chew through the transcript...",
            "ollama":      "Hammy is chewing through the transcript...",
            "anthropic_api": "Calling the Anthropic API...",
            "openai_api":  "Calling the OpenAI API...",
        }.get(llm_backend, "Structuring notes...")
        with ui.wheel_status(spinner_msg):
            structured = _run_llm(
                llm_backend, transcript, source_name, duration, date_str, config
            )

    if structured:
        final_output = append_raw_transcript(structured, transcript)
    else:
        if llm_backend and llm_backend != "none":
            ui.warn("LLM structuring failed — saving raw transcript only.")
        final_output = build_raw_output(transcript, source_name, duration, date_str)

    output_dir.mkdir(parents=True, exist_ok=True)
    partial_path = output_path.with_suffix(".md.partial")
    partial_path.write_text(final_output, encoding="utf-8")
    partial_path.rename(output_path)
    ui.ok(f"Notes stashed: {output_path.name}")

    dest = output_dir / audio_path.name
    try:
        shutil.move(str(audio_path), str(dest))
        ui.ok("Audio tucked into the stash.")
    except (PermissionError, OSError):
        ui.warn("Couldn't move audio (Dropbox may have it locked) — notes saved, audio stays put.")


def main() -> None:
    config = load_config()
    background_check(config)

    ui.print_splash()

    wheel_dir = Path(config["wheel_dir"])
    stash_dir = Path(config["stash_dir"])

    parser = argparse.ArgumentParser(
        description="Hammy — transcribe audio files and generate structured meeting notes."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=str(wheel_dir),
        help=f"Audio file or directory (default: {wheel_dir})",
    )
    parser.add_argument(
        "--output", type=Path, default=stash_dir,
        help=f"Output directory (default: {stash_dir})",
    )
    parser.add_argument(
        "--llm", choices=["claude_code", "codex_cli", "ollama",
                          "anthropic_api", "openai_api", "none"],
        default=None,
        help="Force a specific LLM backend (default: auto-detect).",
    )
    parser.add_argument(
        "--model", default=None,
        help="Ollama model to use (overrides config).",
    )
    args = parser.parse_args()

    if args.model:
        config["ollama_model"] = args.model

    # ── Determine LLM backend ─────────────────────────────────────────────────
    ollama_proc = None

    if args.llm == "none":
        llm_backend = None
        ui.info("LLM disabled — raw transcript only.")
    elif args.llm:
        llm_backend = args.llm
        if llm_backend == "ollama":
            ready, ollama_proc = ensure_ollama()
            llm_backend = "ollama" if ready else None
        ui.info(f"LLM: {llm_backend} (forced)")
    else:
        # Check config first, then auto-detect
        cfg_backend = config.get("llm_backend")
        if cfg_backend and cfg_backend != "none":
            llm_backend = cfg_backend
            if llm_backend == "ollama":
                ready, ollama_proc = ensure_ollama()
                if not ready:
                    llm_backend = None
            ui.info(f"LLM: {llm_backend} (from config)")
        else:
            llm_backend = get_auto_backend()
            if llm_backend == "ollama":
                ready, ollama_proc = ensure_ollama()
                if not ready:
                    llm_backend = None
            if llm_backend:
                ui.info(f"LLM: {llm_backend} (auto-detected)")
            else:
                ui.warn("No LLM found — saving raw transcript only.")

    # ── Process files ─────────────────────────────────────────────────────────
    try:
        audio_files = find_audio_files(args.input)
        if not audio_files:
            sys.exit(1)

        ui.info(f"Found {len(audio_files)} audio file(s) to process.")

        for audio_path in audio_files:
            process_file(audio_path, args.output, llm_backend, config)

        print()
        ui.ok(f"All done! Notes are in the stash: {args.output}")

    finally:
        if ollama_proc is not None:
            with ui.wheel_status("Tucking Ollama away..."):
                from hammy.llm import _stop_ollama
                _stop_ollama(ollama_proc)
            ui.ok("Ollama stopped.")
        join_background_check()


# ── Module-level constants for backward compat with tests ────────────────────
_cfg = load_config()
WHEEL_DIR           = Path(_cfg["wheel_dir"])
STASH_DIR           = Path(_cfg["stash_dir"])
DEFAULT_OLLAMA_MODEL = _cfg.get("ollama_model", "llama3.2:3b")
