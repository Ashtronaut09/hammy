"""Hammy — transcribe audio files and structure meeting notes."""

# Re-export public API so tests can do `from hammy import process_file` etc.
from hammy.core import (
    process_file,
    main,
    transcribe_audio,
    find_audio_files,
    build_raw_output,
    append_raw_transcript,
    extract_date_from_filename,
    WHEEL_DIR,
    STASH_DIR,
    DEFAULT_OLLAMA_MODEL,
)
from hammy.transcribe import SUPPORTED_EXTENSIONS
from hammy.llm import get_auto_backend as get_llm_backend

__all__ = [
    "process_file",
    "main",
    "transcribe_audio",
    "find_audio_files",
    "build_raw_output",
    "append_raw_transcript",
    "extract_date_from_filename",
    "get_llm_backend",
    "WHEEL_DIR",
    "STASH_DIR",
    "DEFAULT_OLLAMA_MODEL",
    "SUPPORTED_EXTENSIONS",
]
