"""Models.yaml fetch, version check, and auto-update notification."""

import threading
from datetime import date, datetime
from typing import Any, Optional

import requests
import yaml

from hammy import ui

MODELS_URL = (
    "https://raw.githubusercontent.com/ashtronaut09/hammy/main/hammy/models.yaml"
)
FETCH_TIMEOUT = 5  # seconds — must not block a normal run

# Module-level state for background check
_pending_update_notice: Optional[dict] = None
_background_thread: Optional[threading.Thread] = None


def load_bundled_models() -> dict[str, Any]:
    """Load the models.yaml bundled inside the installed package."""
    try:
        from importlib.resources import files as _pkg_files
        text = _pkg_files("hammy").joinpath("models.yaml").read_text(encoding="utf-8")
    except Exception:
        # Fallback for editable installs / dev environments
        import os
        yaml_path = os.path.join(os.path.dirname(__file__), "models.yaml")
        with open(yaml_path, encoding="utf-8") as f:
            text = f.read()
    return yaml.safe_load(text)


def fetch_remote_models() -> Optional[dict[str, Any]]:
    """Fetch the latest models.yaml from GitHub. Returns None on any error."""
    try:
        resp = requests.get(MODELS_URL, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        return yaml.safe_load(resp.text)
    except Exception:
        return None


def _parse_version(version_str: str) -> date:
    return datetime.strptime(str(version_str), "%Y-%m-%d").date()


def check_for_updates(verbose: bool = False) -> Optional[dict]:
    """Compare bundled models.yaml against GitHub version.

    Returns update info dict if newer version exists, else None.
    """
    remote = fetch_remote_models()
    if remote is None:
        if verbose:
            ui.warn("Could not reach GitHub to check for model updates.")
        return None

    bundled = load_bundled_models()
    current_ver = str(bundled.get("version", "2000-01-01"))
    remote_ver  = str(remote.get("version", "2000-01-01"))

    try:
        if _parse_version(remote_ver) <= _parse_version(current_ver):
            return None
    except ValueError:
        return None

    # Build diff summary
    summary_lines = [f"models.yaml updated: {current_ver} → {remote_ver}"]
    for platform, langs in remote.get("platforms", {}).items():
        bundled_platform = bundled.get("platforms", {}).get(platform, {})
        for lang, specs in langs.items():
            remote_rec  = specs.get("recommended", {}).get("id", "")
            bundled_rec = bundled_platform.get(lang, {}).get("recommended", {}).get("id", "")
            if remote_rec != bundled_rec:
                summary_lines.append(
                    f"  {platform}/{lang}: {bundled_rec or 'none'} → {remote_rec}"
                )

    return {
        "current_version": current_ver,
        "remote_version": remote_ver,
        "remote_data": remote,
        "summary": "\n".join(summary_lines),
    }


def _should_check_today(config: dict) -> bool:
    if not config.get("update_check_enabled", False):
        return False
    last_check = config.get("last_update_check")
    if last_check is None:
        return True
    try:
        last_date = datetime.strptime(last_check, "%Y-%m-%d").date()
        interval  = config.get("update_check_interval_days", 7)
        return (date.today() - last_date).days >= interval
    except ValueError:
        return True


def background_check(config: dict) -> None:
    """Start a non-blocking background update check (daemon thread).

    Results are stored module-level and printed by join_background_check()
    after processing is complete.
    """
    global _background_thread, _pending_update_notice
    if not _should_check_today(config):
        return

    def _check():
        global _pending_update_notice
        from hammy.config import load_config, save_config
        result = check_for_updates()
        cfg = load_config()
        cfg["last_update_check"] = date.today().isoformat()
        save_config(cfg)
        if result:
            _pending_update_notice = result

    _background_thread = threading.Thread(target=_check, daemon=True)
    _background_thread.start()


def join_background_check() -> None:
    """Wait (briefly) for background check, print notice if update found."""
    global _background_thread, _pending_update_notice
    if _background_thread is not None:
        _background_thread.join(timeout=1.0)
        _background_thread = None
    if _pending_update_notice is not None:
        notice = _pending_update_notice
        _pending_update_notice = None
        print()
        ui.info(
            f"[update] New model recommendations available "
            f"({notice['current_version']} → {notice['remote_version']}). "
            f"Run `hammy check` to see details."
        )


def run_check_command() -> None:
    """Implementation of `hammy check` subcommand."""
    ui.info("Checking for model updates...")
    result = check_for_updates(verbose=True)
    if result is None:
        ui.ok("Models are up to date.")
        return
    print()
    ui.warn(
        f"New models available! "
        f"({result['current_version']} → {result['remote_version']})"
    )
    print()
    for line in result["summary"].split("\n"):
        ui.info(line)
    print()
    ui.info("Run `hammy setup` to reconfigure with the new recommended models.")
