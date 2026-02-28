"""
Integration tests — full pipeline with mocked dependencies.

These tests exercise process_file() and main() end-to-end, mocking only
mlx_whisper and the LLM backends.

Plan reference: entire plan.md
"""

import re
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from subprocess import CompletedProcess

from hammy import process_file, main

FAKE_WHISPER_RESULT = {
    "segments": [
        {"start": 0.0, "end": 5.0, "text": " Hey everyone, let's get started."},
        {"start": 5.0, "end": 12.0, "text": " I finished the auth module refactor."},
        {"start": 12.0, "end": 20.0, "text": " Database migration is in progress."},
    ]
}

FAKE_STRUCTURED = (
    "# Standup\n\n"
    "## Summary\nBrief standup.\n\n"
    "## Key Takeaways\n- Auth done.\n\n"
    "## Action Items\n- [ ] Review.\n\n"
    "## Detailed Notes\n### Auth\nDone.\n"
)

FAKE_CLAUDE_RESULT = CompletedProcess(
    args=["claude", "-p", "..."],
    returncode=0,
    stdout=FAKE_STRUCTURED,
    stderr="",
)

FAKE_CONFIG = {
    "platform": "mac_silicon",
    "transcription_package": "mlx-whisper",
    "transcription_model": "mlx-community/whisper-large-v3-turbo",
    "ollama_model": "llama3.1:8b",
    "stash_dir": "/tmp/hammy_stash",
}


def _mock_whisper(return_value=None):
    mock_module = MagicMock()
    mock_module.transcribe.return_value = return_value or FAKE_WHISPER_RESULT
    return patch.dict(sys.modules, {"mlx_whisper": mock_module})


class TestProcessFileSingleFile:
    """process_file() end-to-end with a single audio file."""

    def test_produces_output_file(self, tmp_path):
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "output"

        with _mock_whisper():
            with patch("hammy.core.subprocess.run", return_value=FAKE_CLAUDE_RESULT):
                process_file(audio, output_dir, "claude_code", FAKE_CONFIG)

        outputs = list(output_dir.glob("*.md"))
        assert len(outputs) == 1, (
            f"Expected 1 output .md file, found {len(outputs)}: "
            f"{[f.name for f in outputs]}."
        )

    def test_output_filename_format(self, tmp_path):
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "output"

        with _mock_whisper():
            with patch("hammy.core.subprocess.run", return_value=FAKE_CLAUDE_RESULT):
                process_file(audio, output_dir, "claude_code", FAKE_CONFIG)

        filename = list(output_dir.glob("*.md"))[0].name
        assert re.match(r"\d{4}-\d{2}-\d{2}_standup\.md$", filename), (
            f"Filename '{filename}' doesn't match 'YYYY-MM-DD_standup.md'."
        )

    def test_output_has_raw_transcript(self, tmp_path):
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "output"

        with _mock_whisper():
            with patch("hammy.core.subprocess.run", return_value=FAKE_CLAUDE_RESULT):
                process_file(audio, output_dir, "claude_code", FAKE_CONFIG)

        content = list(output_dir.glob("*.md"))[0].read_text()
        assert "## Raw Transcript" in content, (
            f"Output must include '## Raw Transcript' section. "
            f"append_raw_transcript should be called after LLM structuring."
        )
        assert "auth module refactor" in content, (
            f"Raw transcript text missing from output."
        )

    def test_creates_output_dir(self, tmp_path):
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "new_output"
        assert not output_dir.exists()

        with _mock_whisper():
            process_file(audio, output_dir, None, FAKE_CONFIG)

        assert output_dir.exists(), (
            f"Output directory should be auto-created. "
            f"Add: output_dir.mkdir(parents=True, exist_ok=True)"
        )


class TestMainWithDirectory:
    """main() processes a directory of audio files."""

    def test_processes_multiple_files(self, tmp_path):
        audio_dir = tmp_path / "recordings"
        audio_dir.mkdir()
        (audio_dir / "meeting1.m4a").touch()
        (audio_dir / "meeting2.mp3").touch()
        (audio_dir / "notes.txt").touch()  # should be ignored
        output_dir = tmp_path / "output"

        with _mock_whisper():
            with patch("hammy.core.subprocess.run", return_value=FAKE_CLAUDE_RESULT):
                with patch("hammy.llm.shutil.which", return_value="/usr/local/bin/claude"):
                    with patch("sys.argv", ["hammy", str(audio_dir),
                                            "--output", str(output_dir), "--llm", "claude_code"]):
                        main()

        outputs = list(output_dir.glob("*.md"))
        assert len(outputs) == 2, (
            f"Expected 2 output files (one per audio file), got "
            f"{len(outputs)}: {[f.name for f in outputs]}. "
            f"The .txt file should be skipped."
        )


class TestMainNoLLM:
    """main() with --llm none produces raw-only output."""

    def test_raw_only_output(self, tmp_path):
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "output"

        with _mock_whisper():
            with patch("sys.argv", ["hammy", str(audio),
                                    "--output", str(output_dir), "--llm", "none"]):
                main()

        outputs = list(output_dir.glob("*.md"))
        assert len(outputs) == 1, (
            f"Even with --llm none, an output file should be created."
        )
        content = outputs[0].read_text()
        assert "## Raw Transcript" in content, (
            f"Raw-only output must have '## Raw Transcript'."
        )


class TestMainLLMFallback:
    """main() with LLM failure still produces output."""

    def test_claude_failure_still_writes_file(self, tmp_path):
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "output"

        failed = CompletedProcess(args=[], returncode=1, stdout="", stderr="err")
        with _mock_whisper():
            with patch("hammy.core.subprocess.run", return_value=failed):
                with patch("hammy.llm.shutil.which", return_value="/usr/local/bin/claude"):
                    with patch("sys.argv", ["hammy", str(audio),
                                            "--output", str(output_dir), "--llm", "claude_code"]):
                        main()

        outputs = list(output_dir.glob("*.md"))
        assert len(outputs) == 1, (
            f"Even when LLM fails, output should be written with raw transcript."
        )
        content = outputs[0].read_text()
        assert "## Raw Transcript" in content, (
            f"Fallback output must contain raw transcript."
        )
