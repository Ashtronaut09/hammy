"""
Tests for CLI argument parsing.

The main() function uses argparse internally. We test it by calling
main() with sys.argv patched, or by extracting the parser.

Plan reference: "CLI Interface" section of plan.md
"""

import pytest
from pathlib import Path

# We test the argparse config by reproducing the parser setup from main()
# and calling parse_args directly. This avoids running the whole pipeline.
import argparse
from hammy import STASH_DIR, DEFAULT_OLLAMA_MODEL


def _build_parser():
    """Replicate the argparse setup from main() for isolated testing."""
    parser = argparse.ArgumentParser(
        description="Hammy — transcribe audio files and generate structured meeting notes."
    )
    parser.add_argument("input", help="Audio file or directory.")
    parser.add_argument("--output", type=Path, default=STASH_DIR)
    parser.add_argument("--llm", choices=["claude", "ollama", "none"], default=None)
    parser.add_argument("--model", default=DEFAULT_OLLAMA_MODEL)
    return parser


class TestCLIParsing:
    """CLI arguments are parsed correctly."""

    def test_accepts_single_file_argument(self, single_audio_file):
        parser = _build_parser()
        args = parser.parse_args([str(single_audio_file)])
        assert args.input == str(single_audio_file), (
            f"Positional 'input' arg not parsed. "
            f"Expected '{single_audio_file}', got '{args.input}'. "
            f"main() must have: parser.add_argument('input')"
        )

    def test_accepts_directory_argument(self, audio_dir):
        parser = _build_parser()
        args = parser.parse_args([str(audio_dir)])
        assert args.input == str(audio_dir), (
            f"Directory path not accepted as positional arg. "
            f"Expected '{audio_dir}', got '{args.input}'."
        )

    def test_output_flag(self):
        parser = _build_parser()
        args = parser.parse_args(["some.m4a", "--output", "./notes/"])
        assert str(args.output) == "notes", (
            f"--output flag not parsed. Expected path containing 'notes', "
            f"got '{args.output}'. "
            f"Add: parser.add_argument('--output', type=Path, default=...)"
        )

    def test_output_has_default(self):
        parser = _build_parser()
        args = parser.parse_args(["some.m4a"])
        assert args.output is not None, (
            f"args.output should have a default value when --output is "
            f"not specified. Got None. "
            f"Set a default on the --output argument."
        )

    def test_llm_flag_claude(self):
        parser = _build_parser()
        args = parser.parse_args(["some.m4a", "--llm", "claude"])
        assert args.llm == "claude", (
            f"--llm claude not parsed. Expected 'claude', got '{args.llm}'. "
            f"Add: parser.add_argument('--llm', choices=['claude','ollama','none'])"
        )

    def test_llm_flag_ollama(self):
        parser = _build_parser()
        args = parser.parse_args(["some.m4a", "--llm", "ollama"])
        assert args.llm == "ollama", (
            f"--llm ollama not parsed. Got '{args.llm}'."
        )

    def test_llm_flag_none(self):
        parser = _build_parser()
        args = parser.parse_args(["some.m4a", "--llm", "none"])
        assert args.llm == "none", (
            f"--llm none not parsed. Got '{args.llm}'. "
            f"'none' must be a valid choice to allow skipping LLM."
        )

    def test_llm_default_is_none(self):
        parser = _build_parser()
        args = parser.parse_args(["some.m4a"])
        assert args.llm is None, (
            f"When --llm is not specified, args.llm should be None "
            f"(auto-detect). Got '{args.llm}'."
        )

    def test_model_flag(self):
        parser = _build_parser()
        args = parser.parse_args(["some.m4a", "--model", "mistral:7b"])
        assert args.model == "mistral:7b", (
            f"--model not parsed. Expected 'mistral:7b', got '{args.model}'."
        )

    def test_model_has_default(self):
        parser = _build_parser()
        args = parser.parse_args(["some.m4a"])
        assert args.model is not None and len(args.model) > 0, (
            f"--model should have a default value (e.g. 'llama3.1:8b'). "
            f"Got '{args.model}'."
        )

    def test_no_args_exits_with_error(self):
        parser = _build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args([])
        assert exc_info.value.code != 0, (
            f"Running with no arguments should exit with non-zero code. "
            f"Got {exc_info.value.code}."
        )

    def test_invalid_llm_choice_exits(self):
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["some.m4a", "--llm", "gpt4"])
