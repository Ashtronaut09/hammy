"""
Tests for the Whisper transcription step (mocked).

Tests transcribe_audio(audio_path, config) which:
- Calls mlx_whisper.transcribe() with the file path.
- Returns (timestamped_transcript_string, duration_string).
- Returns ("", "0:00") if no segments.

Note: mlx_whisper is imported locally inside transcribe_audio(), so we
mock it by injecting into sys.modules before calling the function.

Plan reference: "Step 1: Transcription" section of plan.md
"""

import re
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

from hammy import transcribe_audio

FAKE_WHISPER_RESULT = {
    "segments": [
        {"start": 0.0, "end": 5.0, "text": " Hey everyone, let's get started with the standup."},
        {"start": 5.0, "end": 12.0, "text": " Sure. Yesterday I finished the auth module refactor."},
        {"start": 12.0, "end": 20.0, "text": " Nice. I'm still working on the database migration."},
        {"start": 20.0, "end": 22.0, "text": " Any blockers?"},
        {"start": 22.0, "end": 30.0, "text": " Yeah, I need the new schema docs from Sarah."},
        {"start": 30.0, "end": 33.0, "text": " Sarah, can you get those over by end of day?"},
        {"start": 33.0, "end": 40.0, "text": " Already on it, will send by 3pm."},
        {"start": 40.0, "end": 45.0, "text": " Great. Anything else? Ok let's wrap up."},
    ]
}

FAKE_CONFIG = {
    "platform": "mac_silicon",
    "transcription_package": "mlx-whisper",
    "transcription_model": "mlx-community/whisper-large-v3-turbo",
}


def _mock_whisper(return_value=None, side_effect=None):
    """Create a mock mlx_whisper module and inject into sys.modules."""
    mock_module = MagicMock()
    if side_effect:
        mock_module.transcribe.side_effect = side_effect
    else:
        mock_module.transcribe.return_value = return_value or FAKE_WHISPER_RESULT
    return patch.dict(sys.modules, {"mlx_whisper": mock_module}), mock_module


class TestTranscribeAudio:
    """transcribe_audio(path, config) calls whisper and formats output."""

    def test_calls_whisper(self):
        ctx, mock_mod = _mock_whisper()
        with ctx:
            transcribe_audio(Path("test_audio.m4a"), FAKE_CONFIG)
            mock_mod.transcribe.assert_called_once()
            call_args = mock_mod.transcribe.call_args
            assert "test_audio.m4a" in str(call_args), (
                f"mlx_whisper.transcribe() not called with the file path. "
                f"Called with: {call_args}. "
                f"Pass str(audio_path) as the first arg."
            )

    def test_returns_tuple(self):
        ctx, _ = _mock_whisper()
        with ctx:
            result = transcribe_audio(Path("test.m4a"), FAKE_CONFIG)
        assert isinstance(result, tuple) and len(result) == 2, (
            f"transcribe_audio should return (transcript, duration). "
            f"Got: {type(result).__name__} = {result!r}."
        )

    def test_transcript_has_timestamps(self):
        ctx, _ = _mock_whisper()
        with ctx:
            transcript, _ = transcribe_audio(Path("test.m4a"), FAKE_CONFIG)
        assert "[00:00]" in transcript, (
            f"Transcript missing timestamps. Expected '[MM:SS]' format "
            f"like '[00:00] Hey everyone'. "
            f"Got: '{transcript[:200]}...'. "
            f"Convert segment 'start' seconds to [MM:SS]."
        )

    def test_every_line_has_timestamp(self):
        ctx, _ = _mock_whisper()
        with ctx:
            transcript, _ = transcribe_audio(Path("test.m4a"), FAKE_CONFIG)
        lines = [l for l in transcript.strip().split("\n") if l.strip()]
        for line in lines:
            assert re.match(r"\[\d{2}:\d{2}\]", line), (
                f"Every line must start with [MM:SS]. "
                f"Bad line: '{line}'."
            )

    def test_all_segments_present(self):
        ctx, _ = _mock_whisper()
        with ctx:
            transcript, _ = transcribe_audio(Path("test.m4a"), FAKE_CONFIG)
        expected = len(FAKE_WHISPER_RESULT["segments"])
        lines = [l for l in transcript.strip().split("\n") if l.strip()]
        assert len(lines) == expected, (
            f"Expected {expected} transcript lines (one per segment), "
            f"got {len(lines)}."
        )

    def test_preserves_text_content(self):
        ctx, _ = _mock_whisper()
        with ctx:
            transcript, _ = transcribe_audio(Path("test.m4a"), FAKE_CONFIG)
        assert "auth module refactor" in transcript, (
            f"Transcript text missing. Expected 'auth module refactor'. "
            f"Make sure segment['text'] is included in each line."
        )

    def test_minutes_seconds_conversion(self):
        """65 seconds should produce [01:05]."""
        result = {
            "segments": [
                {"start": 65.0, "end": 70.0, "text": " Test at 65 seconds."},
            ]
        }
        ctx, _ = _mock_whisper(return_value=result)
        with ctx:
            transcript, _ = transcribe_audio(Path("test.m4a"), FAKE_CONFIG)
        assert "[01:05]" in transcript, (
            f"65 seconds should produce '[01:05]'. Got: '{transcript.strip()}'. "
            f"Use: minutes = int(start // 60), seconds = int(start % 60)."
        )

    def test_returns_duration_string(self):
        ctx, _ = _mock_whisper()
        with ctx:
            _, duration = transcribe_audio(Path("test.m4a"), FAKE_CONFIG)
        assert duration and ":" in duration, (
            f"Duration should be a string like '0:45'. Got: '{duration}'."
        )

    def test_empty_segments_returns_empty(self):
        ctx, _ = _mock_whisper(return_value={"segments": []})
        with ctx:
            transcript, duration = transcribe_audio(Path("test.m4a"), FAKE_CONFIG)
        assert transcript == "", (
            f"Empty segments should return empty transcript. Got: '{transcript}'."
        )
        assert duration == "0:00", (
            f"Empty segments should return '0:00' duration. Got: '{duration}'."
        )
