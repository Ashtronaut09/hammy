"""Entry point for `hammy` command and `python -m hammy`."""

import sys


def main() -> None:
    from hammy import ui

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "setup":
            from hammy.setup_wizard import run_wizard
            run_wizard()
            return

        if cmd == "check":
            from hammy.updater import run_check_command
            run_check_command()
            return

        if cmd in ("-h", "--help"):
            _print_help()
            return

    # Normal transcription run — require setup first
    from hammy.config import is_setup_complete
    if not is_setup_complete():
        ui.print_splash()
        ui.warn("Hammy isn't configured yet.")
        ui.info("Run `hammy setup` to get started.")
        sys.exit(1)

    from hammy.core import main as run_main
    run_main()


def _print_help() -> None:
    from hammy import ui
    ui.print_splash()
    print("Usage:")
    print("  hammy setup          — interactive first-time setup wizard")
    print("  hammy check          — check for new model recommendations")
    print("  hammy [INPUT]        — transcribe audio (default: thewheel/ dir)")
    print()
    print("Options:")
    print("  --output DIR         — output directory (default: stash/ from config)")
    print("  --llm BACKEND        — force LLM backend:")
    print("                         claude_code | codex_cli | ollama |")
    print("                         anthropic_api | openai_api | none")
    print("  --model NAME         — Ollama model (overrides config)")
    print()


if __name__ == "__main__":
    main()
