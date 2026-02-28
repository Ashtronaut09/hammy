"""
Tests for error handling and graceful fallbacks.

Key behaviors:
- Whisper failure on one file should not crash the whole run.
- LLM failure should fall back to saving raw transcript.
- Errors should be printed, not silently swallowed.

Plan reference: "Error Handling (Minimal)" section of plan.md
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from subprocess import CompletedProcess

from hammy import (
    process_file,
)
from hammy.llm import structure_with_claude_code, structure_with_ollama

FAKE_TRANSCRIPT = (
    "[00:00] Hey everyone, let's get started.\n"
    "[00:05] I finished the auth module refactor."
)

FAKE_WHISPER_RESULT = {
    "segments": [
        {"start": 0.0, "end": 5.0, "text": " Hey everyone."},
        {"start": 5.0, "end": 10.0, "text": " Auth refactor done."},
    ]
}

FAKE_CONFIG = {
    "platform": "mac_silicon",
    "transcription_package": "mlx-whisper",
    "transcription_model": "mlx-community/whisper-large-v3-turbo",
    "ollama_model": "llama3.1:8b",
    "stash_dir": "/tmp/hammy_stash",
}

# A minimal prompt string for LLM helper calls
FAKE_PROMPT = "Summarize this meeting."


def _mock_whisper(return_value=None, side_effect=None):
    """Create a mock mlx_whisper module and inject into sys.modules."""
    mock_module = MagicMock()
    if side_effect:
        mock_module.transcribe.side_effect = side_effect
    else:
        mock_module.transcribe.return_value = return_value or FAKE_WHISPER_RESULT
    return patch.dict(sys.modules, {"mlx_whisper": mock_module}), mock_module


class TestWhisperFailure:
    """Whisper errors are handled gracefully in process_file."""

    def test_whisper_failure_does_not_crash(self, tmp_path):
        audio = tmp_path / "bad.m4a"
        audio.touch()
        output_dir = tmp_path / "output"

        ctx, _ = _mock_whisper(side_effect=RuntimeError("out of memory"))
        with ctx:
            try:
                process_file(audio, output_dir, None, FAKE_CONFIG)
            except Exception as e:
                raise AssertionError(
                    f"process_file raised {type(e).__name__}: {e}. "
                    f"Whisper failures should be caught, not propagated. "
                    f"Wrap transcribe_audio() in try/except in process_file."
                )

    def test_whisper_failure_prints_error(self, tmp_path, capsys):
        audio = tmp_path / "bad.m4a"
        audio.touch()
        output_dir = tmp_path / "output"

        ctx, _ = _mock_whisper(side_effect=RuntimeError("corrupt file"))
        with ctx:
            process_file(audio, output_dir, None, FAKE_CONFIG)

        captured = capsys.readouterr()
        output = captured.out + captured.err
        assert "error" in output.lower() or "Error" in output, (
            f"When whisper fails, an error message should be printed. "
            f"Nothing informative was printed. Output: '{output[:300]}'"
        )


class TestClaudeFailure:
    """Claude CLI failures return None (caller falls back to raw)."""

    def test_nonzero_exit_returns_none(self):
        fake = CompletedProcess(args=[], returncode=1, stdout="", stderr="auth error")
        with patch("hammy.llm.subprocess.run", return_value=fake):
            result = structure_with_claude_code(FAKE_TRANSCRIPT, "s.m4a", "0:45", "2026-02-09", FAKE_PROMPT)
        assert result is None, (
            f"When Claude exits non-zero, should return None. Got: {result!r}. "
            f"Check returncode before using stdout."
        )

    def test_exception_returns_none(self):
        with patch("hammy.llm.subprocess.run", side_effect=FileNotFoundError("not found")):
            try:
                result = structure_with_claude_code(FAKE_TRANSCRIPT, "s.m4a", "0:45", "2026-02-09", FAKE_PROMPT)
            except FileNotFoundError:
                raise AssertionError(
                    "structure_with_claude_code should catch subprocess exceptions, "
                    "not let them propagate. Wrap subprocess.run in try/except."
                )
            else:
                assert result is None, (
                    f"On exception, should return None. Got: {result!r}."
                )

    def test_empty_stdout_returns_none(self):
        fake = CompletedProcess(args=[], returncode=0, stdout="  \n", stderr="")
        with patch("hammy.llm.subprocess.run", return_value=fake):
            result = structure_with_claude_code(FAKE_TRANSCRIPT, "s.m4a", "0:45", "2026-02-09", FAKE_PROMPT)
        assert result is None, (
            f"Empty/whitespace stdout should return None. Got: {result!r}."
        )


class TestOllamaFailure:
    """Ollama failures return None (caller falls back to raw)."""

    def test_connection_error_returns_none(self):
        with patch("hammy.llm.requests.post", side_effect=Exception("connection refused")):
            result = structure_with_ollama(FAKE_TRANSCRIPT, "s.m4a", "0:45", "2026-02-09", FAKE_PROMPT, "llama3.1:8b")
        assert result is None, (
            f"When Ollama is unreachable, should return None. Got: {result!r}."
        )

    def test_bad_status_returns_none(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500 error")
        with patch("hammy.llm.requests.post", return_value=mock_resp):
            result = structure_with_ollama(FAKE_TRANSCRIPT, "s.m4a", "0:45", "2026-02-09", FAKE_PROMPT, "llama3.1:8b")
        assert result is None, (
            f"On HTTP error, should return None. Got: {result!r}."
        )


class TestProcessFileFallback:
    """process_file() falls back to raw transcript when LLM fails."""

    def test_llm_failure_still_writes_output(self, tmp_path):
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "output"

        failed_claude = CompletedProcess(args=[], returncode=1, stdout="", stderr="err")
        ctx, _ = _mock_whisper()
        with ctx:
            with patch("hammy.llm.subprocess.run", return_value=failed_claude):
                process_file(audio, output_dir, "claude_code", FAKE_CONFIG)

        outputs = list(output_dir.glob("*.md"))
        assert len(outputs) == 1, (
            f"Even when LLM fails, an output file should be created with "
            f"raw transcript. Found {len(outputs)} files."
        )

    def test_llm_failure_output_has_transcript(self, tmp_path):
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "output"

        failed_claude = CompletedProcess(args=[], returncode=1, stdout="", stderr="err")
        ctx, _ = _mock_whisper()
        with ctx:
            with patch("hammy.llm.subprocess.run", return_value=failed_claude):
                process_file(audio, output_dir, "claude_code", FAKE_CONFIG)

        content = list(output_dir.glob("*.md"))[0].read_text()
        assert "## Raw Transcript" in content, (
            f"Fallback output must contain '## Raw Transcript' section."
        )
        assert "Hey everyone" in content, (
            f"Fallback output must contain the transcript text."
        )

    def test_no_llm_produces_raw_output(self, tmp_path):
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "output"

        ctx, _ = _mock_whisper()
        with ctx:
            process_file(audio, output_dir, None, FAKE_CONFIG)

        outputs = list(output_dir.glob("*.md"))
        assert len(outputs) == 1, (
            f"With no LLM backend, should still produce output file."
        )
        content = outputs[0].read_text()
        assert "## Raw Transcript" in content, (
            f"No-LLM output must contain raw transcript."
        )
