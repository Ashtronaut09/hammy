"""Read and write ~/.config/hammy/config.json."""

import json
from datetime import date
from pathlib import Path
from typing import Any

CONFIG_DIR  = Path.home() / ".config" / "hammy"
CONFIG_PATH = CONFIG_DIR / "config.json"

_DEFAULTS: dict[str, Any] = {
    # Workspace paths (set during hammy setup)
    "wheel_dir": str(Path.home() / "hammy" / "thewheel"),
    "stash_dir": str(Path.home() / "hammy" / "stash"),

    # Platform: "mac_silicon" | "nvidia_gpu" | "amd_gpu" | "cpu"
    "platform": None,

    # Language: "english" | "multilingual"
    "language": "english",

    # Transcription model (overrides models.yaml recommended)
    "transcription_model": None,
    "transcription_package": None,

    # LLM backend: "claude_code" | "codex_cli" | "ollama" |
    #              "anthropic_api" | "openai_api" | "none" | null (auto-detect)
    "llm_backend": None,

    # LLM-specific settings
    "ollama_model": "qwen2.5:7b",
    "anthropic_api_key": None,
    "openai_api_key": None,

    # Model update tracking
    "last_update_check": None,
    "update_check_enabled": False,   # opt-in during setup
    "update_check_interval_days": 7,
    "known_models_version": None,
}


def load_config() -> dict[str, Any]:
    """Load config from disk, merging with defaults.

    Missing keys are filled from _DEFAULTS so callers never see KeyError.
    """
    if not CONFIG_PATH.exists():
        return dict(_DEFAULTS)
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            on_disk = json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)
    return {**_DEFAULTS, **on_disk}


def save_config(config: dict[str, Any]) -> None:
    """Write config to disk atomically."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, default=str)
        f.write("\n")
    tmp.replace(CONFIG_PATH)


def get(key: str) -> Any:
    return load_config()[key]


def set_value(key: str, value: Any) -> None:
    config = load_config()
    config[key] = value
    save_config(config)


def is_setup_complete() -> bool:
    """Return True if hammy setup has been run (platform is configured)."""
    return load_config().get("platform") is not None
