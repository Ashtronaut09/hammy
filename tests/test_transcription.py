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

import pytest

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


# ── Configs for non-whisper backends ─────────────────────────────────────────

PARAKEET_MLX_CONFIG = {
    "platform": "mac_silicon",
    "transcription_package": "parakeet-mlx",
    "transcription_model": "mlx-community/parakeet-tdt-0.6b-v2",
}

FASTER_WHISPER_CONFIG = {
    "platform": "nvidia_gpu",
    "transcription_package": "faster-whisper",
    "transcription_model": "Systran/faster-whisper-large-v3-turbo",
}

PARAKEET_NEMO_CONFIG = {
    "platform": "nvidia_gpu",
    "transcription_package": "parakeet-nemo",
    "transcription_model": "nvidia/parakeet-tdt-0.6b-v2",
}

# NeMo uses {"start", "end", "segment"} dicts instead of {"start", "end", "text"}
FAKE_NEMO_SEGMENTS = [
    {"start": 0.0,  "end": 5.0,  "segment": "Hey everyone, let's get started with the standup."},
    {"start": 5.0,  "end": 12.0, "segment": "Yesterday I finished the auth module refactor."},
    {"start": 12.0, "end": 20.0, "segment": "Nice. I'm still working on the database migration."},
]


# ── Mock helpers ──────────────────────────────────────────────────────────────

def _mock_parakeet_mlx(return_value=None):
    """Inject a fake parakeet_mlx module returning mlx-style segment dicts."""
    mock_module = MagicMock()
    mock_module.transcribe.return_value = return_value or {"segments": FAKE_WHISPER_RESULT["segments"]}
    return patch.dict(sys.modules, {"parakeet_mlx": mock_module}), mock_module


def _mock_faster_whisper():
    """Inject a fake faster_whisper module with object-style segments."""
    mock_fw = MagicMock()
    fake_segments = []
    for seg_data in FAKE_WHISPER_RESULT["segments"]:
        seg = MagicMock()
        seg.start = seg_data["start"]
        seg.end   = seg_data["end"]
        seg.text  = seg_data["text"].strip()
        fake_segments.append(seg)
    mock_model = MagicMock()
    mock_model.transcribe.return_value = (iter(fake_segments), MagicMock())
    mock_fw.WhisperModel.return_value = mock_model
    return patch.dict(sys.modules, {"faster_whisper": mock_fw}), mock_fw


def _mock_nemo(segments=None):
    """Inject fake nemo / torch modules with NeMo-style output.

    `import nemo.collections.asr as nemo_asr` resolves via attribute access:
      sys.modules["nemo"].collections.asr
    so we must wire that chain explicitly, not just patch sys.modules keys.
    """
    segs = segments or FAKE_NEMO_SEGMENTS
    fake_result = MagicMock()
    fake_result.timestamp = {"segment": segs}

    mock_model_before = MagicMock()
    mock_model_after  = MagicMock()
    mock_model_after.transcribe.return_value = [fake_result]
    mock_model_before.to.return_value = mock_model_after

    mock_asr = MagicMock()
    mock_asr.models.ASRModel.from_pretrained.return_value = mock_model_before

    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    # Wire attribute chain so mock_nemo.collections.asr == mock_asr
    mock_nemo = MagicMock(name="nemo")
    mock_nemo.collections.asr = mock_asr

    patches = {
        "nemo":                 mock_nemo,
        "nemo.collections":     mock_nemo.collections,
        "nemo.collections.asr": mock_asr,
        "torch":                mock_torch,
    }
    return patch.dict(sys.modules, patches), mock_asr


# ── parakeet-mlx (Apple Silicon, English recommended) ────────────────────────

class TestTranscribeParakeetMlx:
    """_transcribe_parakeet_mlx() via transcribe_audio() with parakeet-mlx config."""

    def test_calls_parakeet_transcribe(self):
        ctx, mock_mod = _mock_parakeet_mlx()
        with ctx:
            transcribe_audio(Path("test.m4a"), PARAKEET_MLX_CONFIG)
        mock_mod.transcribe.assert_called_once()

    def test_passes_file_path(self):
        ctx, mock_mod = _mock_parakeet_mlx()
        with ctx:
            transcribe_audio(Path("standup.m4a"), PARAKEET_MLX_CONFIG)
        assert "standup.m4a" in str(mock_mod.transcribe.call_args)

    def test_passes_model_id(self):
        ctx, mock_mod = _mock_parakeet_mlx()
        with ctx:
            transcribe_audio(Path("test.m4a"), PARAKEET_MLX_CONFIG)
        kwargs = mock_mod.transcribe.call_args[1]
        assert kwargs.get("model") == PARAKEET_MLX_CONFIG["transcription_model"]

    def test_returns_transcript_with_timestamps(self):
        ctx, _ = _mock_parakeet_mlx()
        with ctx:
            transcript, _ = transcribe_audio(Path("test.m4a"), PARAKEET_MLX_CONFIG)
        assert "[00:00]" in transcript

    def test_returns_duration(self):
        ctx, _ = _mock_parakeet_mlx()
        with ctx:
            _, duration = transcribe_audio(Path("test.m4a"), PARAKEET_MLX_CONFIG)
        assert ":" in duration

    def test_falls_back_to_mlx_whisper_if_not_installed(self):
        with patch.dict(sys.modules, {"parakeet_mlx": None}):
            with patch(
                "hammy.transcribe._transcribe_mlx_whisper",
                return_value=("fallback transcript", "0:45"),
            ) as mock_fallback:
                result = transcribe_audio(Path("test.m4a"), PARAKEET_MLX_CONFIG)
        mock_fallback.assert_called_once()
        assert result == ("fallback transcript", "0:45")


# ── faster-whisper (NVIDIA / AMD / CPU) ──────────────────────────────────────

class TestTranscribeFasterWhisper:
    """_transcribe_faster_whisper() via transcribe_audio() with faster-whisper config."""

    def test_creates_whisper_model_with_correct_id(self):
        ctx, mock_fw = _mock_faster_whisper()
        with ctx:
            transcribe_audio(Path("test.m4a"), FASTER_WHISPER_CONFIG)
        mock_fw.WhisperModel.assert_called_once_with(FASTER_WHISPER_CONFIG["transcription_model"])

    def test_calls_transcribe_with_file_path(self):
        ctx, mock_fw = _mock_faster_whisper()
        with ctx:
            transcribe_audio(Path("standup.m4a"), FASTER_WHISPER_CONFIG)
        model_instance = mock_fw.WhisperModel.return_value
        model_instance.transcribe.assert_called_once()
        assert "standup.m4a" in str(model_instance.transcribe.call_args)

    def test_returns_transcript_with_timestamps(self):
        ctx, _ = _mock_faster_whisper()
        with ctx:
            transcript, _ = transcribe_audio(Path("test.m4a"), FASTER_WHISPER_CONFIG)
        assert "[00:00]" in transcript

    def test_returns_duration(self):
        ctx, _ = _mock_faster_whisper()
        with ctx:
            _, duration = transcribe_audio(Path("test.m4a"), FASTER_WHISPER_CONFIG)
        assert ":" in duration

    def test_raises_if_not_installed(self):
        with patch.dict(sys.modules, {"faster_whisper": None}):
            with pytest.raises(RuntimeError, match="faster-whisper not installed"):
                transcribe_audio(Path("test.m4a"), FASTER_WHISPER_CONFIG)


# ── parakeet-nemo (NVIDIA GPU, English recommended) ───────────────────────────

class TestTranscribeParakeetNemo:
    """_transcribe_parakeet_nemo() via transcribe_audio() with parakeet-nemo config."""

    def test_calls_from_pretrained_with_model_id(self):
        ctx, mock_asr = _mock_nemo()
        with ctx:
            transcribe_audio(Path("test.m4a"), PARAKEET_NEMO_CONFIG)
        mock_asr.models.ASRModel.from_pretrained.assert_called_once_with(
            model_name=PARAKEET_NEMO_CONFIG["transcription_model"]
        )

    def test_returns_transcript_with_timestamps(self):
        ctx, _ = _mock_nemo()
        with ctx:
            transcript, _ = transcribe_audio(Path("test.m4a"), PARAKEET_NEMO_CONFIG)
        assert "[00:00]" in transcript

    def test_transcript_contains_segment_text(self):
        ctx, _ = _mock_nemo()
        with ctx:
            transcript, _ = transcribe_audio(Path("test.m4a"), PARAKEET_NEMO_CONFIG)
        assert "auth module refactor" in transcript

    def test_returns_duration(self):
        ctx, _ = _mock_nemo()
        with ctx:
            _, duration = transcribe_audio(Path("test.m4a"), PARAKEET_NEMO_CONFIG)
        assert ":" in duration

    def test_raises_if_not_installed(self):
        nemo_nulls = {
            "nemo":                None,
            "nemo.collections":   None,
            "nemo.collections.asr": None,
        }
        with patch.dict(sys.modules, nemo_nulls):
            with pytest.raises(RuntimeError, match="nemo-toolkit not installed"):
                transcribe_audio(Path("test.m4a"), PARAKEET_NEMO_CONFIG)


# ── Routing / dispatch ────────────────────────────────────────────────────────

class TestTranscribeRouting:
    """transcribe_audio() routes to the correct backend based on platform + package."""

    def test_mac_silicon_parakeet_mlx(self):
        with patch("hammy.transcribe._transcribe_parakeet_mlx", return_value=("", "0:00")) as fn:
            transcribe_audio(Path("test.m4a"), PARAKEET_MLX_CONFIG)
        fn.assert_called_once()

    def test_mac_silicon_mlx_whisper(self):
        with patch("hammy.transcribe._transcribe_mlx_whisper", return_value=("", "0:00")) as fn:
            transcribe_audio(Path("test.m4a"), FAKE_CONFIG)
        fn.assert_called_once()

    def test_nvidia_parakeet_nemo(self):
        with patch("hammy.transcribe._transcribe_parakeet_nemo", return_value=("", "0:00")) as fn:
            transcribe_audio(Path("test.m4a"), PARAKEET_NEMO_CONFIG)
        fn.assert_called_once()

    def test_nvidia_faster_whisper(self):
        with patch("hammy.transcribe._transcribe_faster_whisper", return_value=("", "0:00")) as fn:
            transcribe_audio(Path("test.m4a"), FASTER_WHISPER_CONFIG)
        fn.assert_called_once()
