"""Interactive setup wizard for Hammy (hammy setup)."""

import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import questionary
from prompt_toolkit.styles import Style

from hammy import ui
from hammy.config import load_config, save_config
from hammy.updater import fetch_remote_models, load_bundled_models

# ── questionary style matching Hammy's palette ───────────────────────────────
HAMMY_STYLE = Style([
    ("highlighted",  "fg:#ff87c3 bold"),   # PINK      — focused choice
    ("pointer",      "fg:#c9a0dc bold"),   # LAVENDER  — arrow
    ("selected",     "fg:#ffb7d5"),        # SOFT_PINK — selected item
    ("question",     "fg:#c9a0dc bold"),   # LAVENDER  — question text
    ("answer",       "fg:#ff87c3 bold"),   # PINK      — confirmed answer
    ("instruction",  "fg:#fffdd0 italic"), # CREAM     — hint text
    ("text",         "fg:#ffb7d5"),        # SOFT_PINK — body text
])

_BACK = "__BACK__"   # sentinel: go to previous step


# ── Wizard state ──────────────────────────────────────────────────────────────

class WizardState:
    def __init__(self):
        self.platform: Optional[str] = None
        self.language: Optional[str] = None
        self.transcription_model: Optional[str] = None
        self.transcription_package: Optional[str] = None
        self.llm_backend: Optional[str] = None
        _cfg = load_config()
        _wheel = _cfg.get("wheel_dir")
        self.ollama_model: str = "qwen2.5:7b"
        self.api_key: Optional[str] = None
        self.workspace_path: Path = Path(_wheel).parent if _wheel else Path.home() / "hammy"
        self.update_check_enabled: bool = False


# ── Step functions ────────────────────────────────────────────────────────────

def _ask(fn, *args, **kwargs):
    """Call a questionary prompt; return _BACK if user cancels (Ctrl-C)."""
    result = fn(*args, style=HAMMY_STYLE, **kwargs).ask()
    return _BACK if result is None else result


def step_welcome(state: WizardState):
    ui.print_splash()
    ui.info("Welcome! Let's get Hammy set up for your machine.")
    ui.info("Use arrow keys to navigate, Enter to select, Ctrl-C to cancel.")
    print()
    choice = _ask(
        questionary.select,
        "Ready to begin?",
        choices=["Let's go!", questionary.Choice("Quit", value=_BACK)],
    )
    return _BACK if choice == _BACK else state


def step_platform(state: WizardState):
    print()
    choice = _ask(
        questionary.select,
        "What platform are you running Hammy on?",
        choices=[
            questionary.Choice("Mac with Apple Silicon (M1/M2/M3/M4)",
                               value="mac_silicon"),
            questionary.Choice("PC — NVIDIA GPU",  value="nvidia_gpu"),
            questionary.Choice("PC — AMD GPU",     value="amd_gpu"),
            questionary.Choice("PC — CPU only",    value="cpu"),
            questionary.Separator(),
            questionary.Choice("← Back", value=_BACK),
        ],
        instruction="(arrow keys + Enter)",
    )
    if choice == _BACK:
        return _BACK
    state.platform = choice
    return state


def step_language(state: WizardState):
    print()
    choice = _ask(
        questionary.select,
        "What language(s) will you mostly be transcribing?",
        choices=[
            questionary.Choice(
                "Primarily English  (faster & more accurate English models)",
                value="english",
            ),
            questionary.Choice(
                "Multiple languages / non-English",
                value="multilingual",
            ),
            questionary.Separator(),
            questionary.Choice("← Back", value=_BACK),
        ],
    )
    if choice == _BACK:
        return _BACK
    state.language = choice
    return state


def step_model(state: WizardState):
    """Show recommended model + alternatives for the chosen platform/language."""
    models_data = _load_models()
    platform_data = models_data.get("platforms", {}).get(state.platform, {})
    lang_data      = platform_data.get(state.language, {})
    recommended    = lang_data.get("recommended", {})
    alternatives   = lang_data.get("alternatives", [])

    rec_id   = recommended.get("id", "mlx-community/whisper-large-v3-turbo")
    rec_pkg  = recommended.get("package", "mlx-whisper")
    rec_size = recommended.get("size_gb", "?")
    rec_note = recommended.get("notes", "")

    print()
    ui.info(f"Recommended transcription model for {state.platform} / {state.language}:")
    ui.info(f"  {rec_id}  ({rec_size} GB)  — {rec_note}")
    print()

    choices = [
        questionary.Choice(
            f"Use recommended: {rec_id}",
            value={"id": rec_id, "package": rec_pkg},
        )
    ]
    for alt in alternatives:
        choices.append(questionary.Choice(
            f"{alt['id']}  ({alt.get('size_gb', '?')} GB)"
            + (f"  — {alt['notes']}" if alt.get("notes") else ""),
            value={"id": alt["id"], "package": alt.get("package", rec_pkg)},
        ))
    choices += [questionary.Separator(), questionary.Choice("← Back", value=_BACK)]

    choice = _ask(questionary.select, "Which transcription model?", choices=choices)
    if choice == _BACK:
        return _BACK
    state.transcription_model   = choice["id"]
    state.transcription_package = choice["package"]
    return state


def step_llm(state: WizardState):
    """LLM backend selection with sub-steps for Ollama model and API keys."""
    import shutil as _shutil

    claude_detected = bool(_shutil.which("claude"))
    codex_detected  = bool(_shutil.which("codex"))

    def _label(base, detected):
        suffix = "  ✓ detected" if detected else ""
        return base + suffix

    print()
    choice = _ask(
        questionary.select,
        "Which LLM backend should Hammy use to structure notes?",
        choices=[
            questionary.Choice(
                "Ollama  (local, private, free)",
                value="ollama",
            ),
            questionary.Choice(
                _label("Claude Code CLI  (Claude subscription)", claude_detected),
                value="claude_code",
            ),
            questionary.Choice(
                _label("OpenAI Codex CLI  (OpenAI/ChatGPT subscription)", codex_detected),
                value="codex_cli",
            ),
            questionary.Choice(
                "Anthropic API  (API key, per-token billing)",
                value="anthropic_api",
            ),
            questionary.Choice(
                "OpenAI API  (API key, per-token billing)",
                value="openai_api",
            ),
            questionary.Choice(
                "Skip — raw transcripts only",
                value="none",
            ),
            questionary.Separator(),
            questionary.Choice("← Back", value=_BACK),
        ],
    )
    if choice == _BACK:
        return _BACK

    state.llm_backend = choice

    # Sub-step: Ollama model picker
    if choice == "ollama":
        models_data = _load_models()
        ollama_data = models_data.get("llm", {}).get("ollama", {})
        rec_model   = ollama_data.get("recommended", "qwen2.5:7b")
        alts        = ollama_data.get("alternatives", [])

        print()
        model_choices = [
            questionary.Choice(f"{rec_model}  (recommended)", value=rec_model)
        ]
        for a in alts:
            model_choices.append(questionary.Choice(a, value=a))
        model_choices += [
            questionary.Separator(),
            questionary.Choice("← Back to LLM selection", value=_BACK),
        ]

        model = _ask(
            questionary.select,
            "Which Ollama model should Hammy use?",
            choices=model_choices,
        )
        if model == _BACK:
            return step_llm(state)   # re-run this step
        state.ollama_model = model

    # Sub-step: API key entry
    elif choice == "anthropic_api":
        print()
        key = _ask(
            questionary.password,
            "Anthropic API key  (starts with sk-ant-):",
            validate=lambda v: len(v.strip()) > 20 or "Key looks too short",
        )
        if key == _BACK:
            return step_llm(state)
        state.api_key = key.strip()

    elif choice == "openai_api":
        print()
        key = _ask(
            questionary.password,
            "OpenAI API key  (starts with sk-):",
            validate=lambda v: v.strip().startswith("sk-") or "OpenAI keys start with sk-",
        )
        if key == _BACK:
            return step_llm(state)
        state.api_key = key.strip()

    return state


def step_workspace(state: WizardState):
    print()
    existing_wheel = load_config().get("wheel_dir")
    if existing_wheel:
        current_workspace = Path(existing_wheel).parent
        ui.info(f"Current workspace: {current_workspace}/")
        print()
        change = _ask(
            questionary.select,
            "Do you want to change your workspace directory?",
            choices=[
                questionary.Choice("No — keep current location", value=False),
                questionary.Choice("Yes — choose a new location", value=True),
                questionary.Separator(),
                questionary.Choice("← Back", value=_BACK),
            ],
        )
        if change == _BACK:
            return _BACK
        if not change:
            state.workspace_path = current_workspace
            return state
        print()
    else:
        ui.info("Hammy needs two folders: one to drop audio files into (thewheel/)")
        ui.info("and one where finished notes land (stash/).")
        print()
    path_str = _ask(
        questionary.text,
        "Workspace directory:",
        default=str(state.workspace_path),
        validate=lambda v: len(v.strip()) > 0 or "Please enter a path",
    )
    if path_str == _BACK:
        return _BACK
    # Strip surrounding quotes — users often paste shell-escaped paths like
    # '/some/path with spaces' and Path() would treat the leading ' as literal.
    path_str = path_str.strip().strip("'\"")
    state.workspace_path = Path(path_str).expanduser()
    return state


def step_updates(state: WizardState):
    print()
    choice = _ask(
        questionary.select,
        "Check for new model recommendations once a week?",
        choices=[
            questionary.Choice(
                "No thanks  (you can always run `hammy check` manually)",
                value=False,
            ),
            questionary.Choice(
                "Yes — show a one-line notice after runs when updates are available",
                value=True,
            ),
            questionary.Separator(),
            questionary.Choice("← Back", value=_BACK),
        ],
    )
    if choice == _BACK:
        return _BACK
    state.update_check_enabled = choice
    return state


def step_confirm(state: WizardState):
    """Show summary and ask to proceed."""
    print()
    ui.section("Setup Summary")
    ui.info(f"  Platform:      {state.platform}")
    ui.info(f"  Language:      {state.language}")
    ui.info(f"  Transcription: {state.transcription_model}")
    ui.info(f"  LLM backend:   {state.llm_backend}")
    if state.llm_backend == "ollama":
        ui.info(f"  Ollama model:  {state.ollama_model}")
    ui.info(f"  Workspace:     {state.workspace_path}/")
    ui.info(f"  Auto-updates:  {'yes' if state.update_check_enabled else 'no'}")
    print()

    choice = _ask(
        questionary.select,
        "Apply this configuration?",
        choices=[
            questionary.Choice("Confirm and set up", value="confirm"),
            questionary.Choice("← Back",             value=_BACK),
            questionary.Choice("Quit without saving", value="quit"),
        ],
    )
    if choice == "quit":
        ui.info("No changes made.")
        sys.exit(0)
    return _BACK if choice == _BACK else state


# ── Main wizard loop ──────────────────────────────────────────────────────────

STEPS = [
    step_welcome,
    step_platform,
    step_language,
    step_model,
    step_llm,
    step_workspace,
    step_updates,
    step_confirm,
]


def run_wizard() -> None:
    """Run the full setup wizard, supporting back navigation."""
    state = WizardState()
    current = 0

    while current < len(STEPS):
        result = STEPS[current](state)

        if result is None or result == _BACK:
            if current > 0:
                current -= 1
            continue

        state = result
        current += 1

    _apply_wizard_results(state)


def _apply_wizard_results(state: WizardState) -> None:
    """Write wizard choices to config, create workspace dirs, pull Ollama model."""
    config = load_config()
    config["platform"]               = state.platform
    config["language"]               = state.language
    config["transcription_model"]    = state.transcription_model
    config["transcription_package"]  = state.transcription_package
    config["llm_backend"]            = state.llm_backend
    config["ollama_model"]           = state.ollama_model
    config["wheel_dir"]              = str(state.workspace_path / "thewheel")
    config["stash_dir"]              = str(state.workspace_path / "stash")
    config["update_check_enabled"]   = state.update_check_enabled

    if state.api_key:
        if state.llm_backend == "anthropic_api":
            config["anthropic_api_key"] = state.api_key
        elif state.llm_backend == "openai_api":
            config["openai_api_key"] = state.api_key

    save_config(config)

    # Create workspace directories
    (state.workspace_path / "thewheel").mkdir(parents=True, exist_ok=True)
    (state.workspace_path / "stash").mkdir(parents=True, exist_ok=True)

    print()
    ui.ok(f"Config saved to ~/.config/hammy/config.json")
    ui.ok(f"Workspace created at {state.workspace_path}/")

    # Pull Ollama model if selected
    if state.llm_backend == "ollama":
        ui.info(f"Pulling {state.ollama_model} via Ollama...")
        try:
            with ui.wheel_status(f"Downloading {state.ollama_model}..."):
                subprocess.run(
                    ["ollama", "pull", state.ollama_model],
                    check=True, capture_output=True,
                )
            ui.ok(f"{state.ollama_model} ready.")
        except FileNotFoundError:
            ui.warn("Ollama not found. Install it from https://ollama.com then run:")
            ui.warn(f"  ollama pull {state.ollama_model}")
        except subprocess.CalledProcessError as e:
            ui.warn(f"Could not pull model: {e}")

    print()
    wheel = state.workspace_path / "thewheel"
    ui.ok(f"All set!  Drop audio files into {wheel}/ and run `hammy`.")
    print()


# ── Model data helper ─────────────────────────────────────────────────────────

def _load_models() -> dict[str, Any]:
    """Load models.yaml: use whichever of remote/bundled is newer."""
    from hammy.updater import fetch_remote_models, load_bundled_models as _bundled
    bundled = _bundled()
    remote = fetch_remote_models()
    if remote is None:
        return bundled
    try:
        from datetime import datetime
        remote_ver  = datetime.strptime(str(remote.get("version",  "2000-01-01")), "%Y-%m-%d").date()
        bundled_ver = datetime.strptime(str(bundled.get("version", "2000-01-01")), "%Y-%m-%d").date()
        return remote if remote_ver > bundled_ver else bundled
    except ValueError:
        return remote


# ── hammy models command ───────────────────────────────────────────────────────

def run_models_command() -> None:
    """Interactive LLM backend / Ollama model switcher — `hammy models`."""
    import shutil as _shutil
    import subprocess as _sub

    cfg             = load_config()
    current_backend = cfg.get("llm_backend") or "none"
    current_model   = cfg.get("ollama_model", "qwen2.5:7b")

    ui.print_splash()
    ui.section("Switch Model / Backend")
    print()
    ui.info(f"  Current backend:  {current_backend}")
    if current_backend == "ollama":
        ui.info(f"  Current model:    {current_model}")
    print()

    claude_detected = bool(_shutil.which("claude"))
    codex_detected  = bool(_shutil.which("codex"))

    def _label(base, detected):
        return base + ("  ✓ detected" if detected else "")

    backend = _ask(
        questionary.select,
        "Which LLM backend?",
        choices=[
            questionary.Choice("Ollama  (local, private, free)",                               value="ollama"),
            questionary.Choice(_label("Claude Code CLI  (Claude subscription)", claude_detected), value="claude_code"),
            questionary.Choice(_label("OpenAI Codex CLI  (OpenAI subscription)", codex_detected), value="codex_cli"),
            questionary.Choice("Anthropic API  (API key, per-token billing)",                  value="anthropic_api"),
            questionary.Choice("OpenAI API  (API key, per-token billing)",                     value="openai_api"),
            questionary.Choice("None — raw transcripts only",                                  value="none"),
            questionary.Separator(),
            questionary.Choice("Cancel — no changes",                                          value=_BACK),
        ],
    )
    if backend == _BACK:
        ui.info("No changes made.")
        return

    ollama_model = current_model

    if backend == "ollama":
        models_data = _load_models()
        ollama_cfg  = models_data.get("llm", {}).get("ollama", {})
        rec         = ollama_cfg.get("recommended", "qwen2.5:7b")
        alts        = ollama_cfg.get("alternatives", [])

        print()

        def _mlabel(name: str) -> str:
            tags = []
            if name == rec:
                tags.append("recommended")
            if name == current_model:
                tags.append("current")
            return name + (f"  ({', '.join(tags)})" if tags else "")

        model_choices = [questionary.Choice(_mlabel(rec), value=rec)]
        for a in alts:
            model_choices.append(questionary.Choice(_mlabel(a), value=a))
        model_choices += [questionary.Separator(), questionary.Choice("← Back", value=_BACK)]

        model = _ask(questionary.select, "Which Ollama model?", choices=model_choices)
        if model == _BACK:
            ui.info("No changes made.")
            return
        ollama_model = model

        # Offer to pull if not already downloaded
        try:
            result      = _sub.run(["ollama", "list"], capture_output=True, text=True)
            already_pulled = ollama_model in result.stdout
        except Exception:
            already_pulled = False

        if not already_pulled:
            print()
            pull = _ask(
                questionary.select,
                f"{ollama_model} isn't downloaded yet. Pull it now?",
                choices=[
                    questionary.Choice("Yes — download now",              value=True),
                    questionary.Choice("No — I'll run `ollama pull` manually", value=False),
                ],
            )
            if pull is True:
                try:
                    with ui.wheel_status(f"Downloading {ollama_model}..."):
                        _sub.run(["ollama", "pull", ollama_model],
                                 check=True, capture_output=True)
                    ui.ok(f"{ollama_model} ready.")
                except FileNotFoundError:
                    ui.warn("Ollama not found. Install from https://ollama.com")
                except _sub.CalledProcessError as e:
                    ui.warn(f"Pull failed: {e}")

    cfg["llm_backend"] = backend
    cfg["ollama_model"] = ollama_model
    save_config(cfg)

    print()
    ui.ok(f"Backend → {backend}")
    if backend == "ollama":
        ui.ok(f"Model   → {ollama_model}")
    print()
