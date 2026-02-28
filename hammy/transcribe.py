"""Transcription backend dispatcher for Hammy."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from hammy import ui

SUPPORTED_EXTENSIONS = {
    ".m4a", ".mp3", ".wav", ".ogg", ".flac",
    ".webm", ".aiff", ".aifc", ".mp4", ".aac",
}
NEEDS_CONVERSION = {".aac", ".mp4", ".aifc", ".aiff", ".webm"}


def transcribe_audio(audio_path: Path, config: dict) -> tuple[str, str]:
    """Transcribe audio, routing to the correct backend based on config.

    Returns (timestamped_transcript, duration_str).
    """
    platform = config.get("platform") or "mac_silicon"
    package  = config.get("transcription_package") or "mlx-whisper"
    model_id = config.get("transcription_model") or "mlx-community/whisper-large-v3-turbo"

    if platform == "mac_silicon":
        if package == "parakeet-mlx":
            return _transcribe_parakeet_mlx(audio_path, model_id)
        return _transcribe_mlx_whisper(audio_path, model_id)
    else:
        if package == "parakeet-nemo":
            return _transcribe_parakeet_nemo(audio_path, model_id)
        return _transcribe_faster_whisper(audio_path, model_id)


# ── mlx-whisper (Apple Silicon default) ──────────────────────────────────────

def _transcribe_mlx_whisper(audio_path: Path, model_id: str) -> tuple[str, str]:
    import mlx_whisper

    transcribe_path = audio_path
    tmp_wav = None
    if audio_path.suffix.lower() in NEEDS_CONVERSION:
        tmp_wav = _convert_to_wav(audio_path)
        if tmp_wav:
            transcribe_path = tmp_wav

    try:
        result = mlx_whisper.transcribe(
            str(transcribe_path),
            path_or_hf_repo=model_id,
            verbose=False,
        )
    finally:
        if tmp_wav and tmp_wav.exists():
            tmp_wav.unlink()

    return _format_segments(result.get("segments", []))


# ── parakeet-mlx (Apple Silicon, English-optimised) ──────────────────────────

def _transcribe_parakeet_mlx(audio_path: Path, model_id: str) -> tuple[str, str]:
    try:
        import parakeet_mlx
    except ImportError:
        ui.warn("parakeet-mlx not installed — falling back to mlx-whisper.")
        return _transcribe_mlx_whisper(
            audio_path, "mlx-community/whisper-large-v3-turbo"
        )

    transcribe_path = audio_path
    tmp_wav = None
    if audio_path.suffix.lower() in NEEDS_CONVERSION:
        tmp_wav = _convert_to_wav(audio_path)
        if tmp_wav:
            transcribe_path = tmp_wav

    try:
        result = parakeet_mlx.transcribe(str(transcribe_path), model=model_id)
    finally:
        if tmp_wav and tmp_wav.exists():
            tmp_wav.unlink()

    # parakeet-mlx returns same segment format as mlx-whisper
    segments = result.get("segments", []) if isinstance(result, dict) else []
    return _format_segments(segments)


# ── faster-whisper (NVIDIA / AMD / CPU) ──────────────────────────────────────

def _transcribe_faster_whisper(audio_path: Path, model_id: str) -> tuple[str, str]:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError(
            "faster-whisper not installed. Run: pipx inject hammy faster-whisper"
        )

    transcribe_path = audio_path
    tmp_wav = None
    if audio_path.suffix.lower() in NEEDS_CONVERSION:
        tmp_wav = _convert_to_wav(audio_path)
        if tmp_wav:
            transcribe_path = tmp_wav

    try:
        model = WhisperModel(model_id)
        segments_iter, info = model.transcribe(str(transcribe_path))
        segments = list(segments_iter)
    finally:
        if tmp_wav and tmp_wav.exists():
            tmp_wav.unlink()

    lines = []
    last_end = 0.0
    for seg in segments:
        start = seg.start
        timestamp = f"[{int(start // 60):02d}:{int(start % 60):02d}]"
        lines.append(f"{timestamp} {seg.text.strip()}")
        last_end = seg.end

    transcript = "\n".join(lines)
    duration_str = f"{int(last_end // 60)}:{int(last_end % 60):02d}"
    return transcript, duration_str


# ── parakeet-nemo (NVIDIA GPU) ────────────────────────────────────────────────

def _transcribe_parakeet_nemo(audio_path: Path, model_id: str) -> tuple[str, str]:
    import logging as _logging
    for _name in ("nemo_logger", "nemo", "nemo.core", "pytorch_lightning"):
        _logging.getLogger(_name).setLevel(_logging.ERROR)

    try:
        import nemo.collections.asr as nemo_asr
    except ImportError:
        raise RuntimeError(
            "nemo-toolkit not installed. Run: pipx inject hammy 'nemo-toolkit[asr]'"
        )

    transcribe_path = audio_path
    tmp_wav = None
    if audio_path.suffix.lower() in NEEDS_CONVERSION:
        tmp_wav = _convert_to_wav(audio_path)
        if tmp_wav:
            transcribe_path = tmp_wav

    try:
        import torch
        asr_model = nemo_asr.models.ASRModel.from_pretrained(model_name=model_id)
        asr_model = asr_model.to("cuda" if torch.cuda.is_available() else "cpu")
        outputs = asr_model.transcribe([str(transcribe_path)], timestamps=True)
    finally:
        if tmp_wav and tmp_wav.exists():
            tmp_wav.unlink()

    result = outputs[0]
    segments = []
    if hasattr(result, "timestamp") and isinstance(result.timestamp, dict):
        segments = result.timestamp.get("segment", [])

    if segments:
        lines = []
        for seg in segments:
            start = seg["start"]
            timestamp = f"[{int(start // 60):02d}:{int(start % 60):02d}]"
            lines.append(f"{timestamp} {seg['segment'].strip()}")
        last_end = segments[-1]["end"]
        duration_str = f"{int(last_end // 60)}:{int(last_end % 60):02d}"
        return "\n".join(lines), duration_str

    text = result.text if hasattr(result, "text") else str(result)
    return text.strip(), "unknown"


# ── Audio conversion ──────────────────────────────────────────────────────────

def _convert_to_wav(audio_path: Path) -> Optional[Path]:
    """Convert audio to 16kHz mono WAV using ffmpeg. Returns temp path or None."""
    if not shutil.which("ffmpeg"):
        ui.warn("ffmpeg not found, skipping conversion.")
        return None
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()

    commands = [
        ["ffmpeg", "-y", "-c:a", "aac_at", "-i", str(audio_path),
         "-ar", "16000", "-ac", "1", tmp.name],
        ["ffmpeg", "-y", "-err_detect", "ignore_err", "-i", str(audio_path),
         "-ar", "16000", "-ac", "1", tmp.name],
    ]

    for cmd in commands:
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            tmp_path = Path(tmp.name)
            if tmp_path.exists() and tmp_path.stat().st_size > 1000:
                ui.info("Converting audio to hamster-readable format...")
                return tmp_path
        except Exception:
            continue

    ui.warn("Audio conversion failed.")
    if os.path.exists(tmp.name):
        os.unlink(tmp.name)
    return None


# ── Shared formatter ──────────────────────────────────────────────────────────

def _format_segments(segments: list) -> tuple[str, str]:
    """Format mlx-style segment list into (transcript, duration_str)."""
    if not segments:
        return "", "0:00"
    lines = []
    for seg in segments:
        start = seg["start"]
        timestamp = f"[{int(start // 60):02d}:{int(start % 60):02d}]"
        lines.append(f"{timestamp} {seg['text'].strip()}")
    last_end = segments[-1]["end"]
    duration_str = f"{int(last_end // 60)}:{int(last_end % 60):02d}"
    return "\n".join(lines), duration_str
