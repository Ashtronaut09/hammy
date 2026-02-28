"""
Tests for output file building and formatting.

Tests:
- build_raw_output(transcript, source_name, duration, date_str)
- append_raw_transcript(structured_notes, transcript)
- process_file() output naming: YYYY-MM-DD_name.md

Plan reference: "Output Format" section of plan.md
"""

import re
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

from hammy import build_raw_output, append_raw_transcript

FAKE_TRANSCRIPT = (
    "[00:00] Hey everyone, let's get started.\n"
    "[00:05] I finished the auth module refactor."
)
FAKE_STRUCTURED = (
    "# Team Standup\n\n"
    "## Summary\nAuth refactor done.\n\n"
    "## Key Takeaways\n- Auth done.\n\n"
    "## Action Items\n- [ ] Review PR.\n\n"
    "## Detailed Notes\n### Auth\nCompleted.\n"
)

FAKE_CONFIG = {
    "platform": "mac_silicon",
    "transcription_package": "mlx-whisper",
    "transcription_model": "mlx-community/whisper-large-v3-turbo",
    "ollama_model": "llama3.1:8b",
    "stash_dir": "/tmp/hammy_stash",
}


class TestBuildRawOutput:
    """build_raw_output() produces valid markdown for raw-only mode."""

    def test_has_title(self):
        content = build_raw_output(FAKE_TRANSCRIPT, "meeting.m4a", "5:30", "2026-02-09")
        assert content.strip().startswith("#"), (
            f"Output should start with a '# Title' header. "
            f"Got: '{content[:100]}...'"
        )

    def test_has_date(self):
        content = build_raw_output(FAKE_TRANSCRIPT, "meeting.m4a", "5:30", "2026-02-09")
        assert "**Date:**" in content, (
            f"Missing '**Date:**' metadata. "
            f"Output must include date in the header."
        )
        assert "2026-02-09" in content, (
            f"Date value '2026-02-09' not found in output."
        )

    def test_has_source(self):
        content = build_raw_output(FAKE_TRANSCRIPT, "my-meeting.m4a", "5:30", "2026-02-09")
        assert "**Source:**" in content, (
            f"Missing '**Source:**' metadata."
        )
        assert "my-meeting.m4a" in content, (
            f"Source filename 'my-meeting.m4a' not found in output."
        )

    def test_has_duration(self):
        content = build_raw_output(FAKE_TRANSCRIPT, "meeting.m4a", "45:12", "2026-02-09")
        assert "**Duration:**" in content, (
            f"Missing '**Duration:**' metadata."
        )
        assert "45:12" in content, (
            f"Duration value '45:12' not found in output."
        )

    def test_has_raw_transcript_section(self):
        content = build_raw_output(FAKE_TRANSCRIPT, "meeting.m4a", "5:30", "2026-02-09")
        assert "## Raw Transcript" in content, (
            f"Missing '## Raw Transcript' section. "
            f"Raw transcript must always be included."
        )

    def test_contains_transcript_text(self):
        content = build_raw_output(FAKE_TRANSCRIPT, "meeting.m4a", "5:30", "2026-02-09")
        assert "auth module refactor" in content, (
            f"Transcript text not found in output. "
            f"The transcript must be included under '## Raw Transcript'."
        )


class TestAppendRawTranscript:
    """append_raw_transcript() adds raw transcript after structured notes."""

    def test_appends_raw_section(self):
        result = append_raw_transcript(FAKE_STRUCTURED, FAKE_TRANSCRIPT)
        assert "## Raw Transcript" in result, (
            f"append_raw_transcript must add a '## Raw Transcript' heading."
        )

    def test_structured_notes_preserved(self):
        result = append_raw_transcript(FAKE_STRUCTURED, FAKE_TRANSCRIPT)
        assert "## Summary" in result, (
            f"Structured notes should be preserved in the output. "
            f"'## Summary' not found."
        )

    def test_transcript_text_present(self):
        result = append_raw_transcript(FAKE_STRUCTURED, FAKE_TRANSCRIPT)
        assert "auth module refactor" in result, (
            f"Raw transcript text not found in output."
        )

    def test_raw_after_structured(self):
        result = append_raw_transcript(FAKE_STRUCTURED, FAKE_TRANSCRIPT)
        summary_pos = result.find("## Summary")
        raw_pos = result.find("## Raw Transcript")
        assert summary_pos < raw_pos, (
            f"'## Raw Transcript' should come AFTER structured notes. "
            f"Summary at {summary_pos}, Raw Transcript at {raw_pos}."
        )


def _mock_whisper(return_value=None):
    mock_module = MagicMock()
    mock_module.transcribe.return_value = return_value or {
        "segments": [{"start": 0.0, "end": 5.0, "text": " Hello world."}]
    }
    return patch.dict(sys.modules, {"mlx_whisper": mock_module})


class TestOutputFilenaming:
    """process_file() creates correctly named output files."""

    def test_filename_format(self, tmp_path):
        """Output file should be named YYYY-MM-DD_stem.md."""
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "output"

        with _mock_whisper():
            from hammy import process_file
            process_file(audio, output_dir, None, FAKE_CONFIG)

        outputs = list(output_dir.glob("*.md"))
        assert len(outputs) == 1, (
            f"Expected 1 output file, got {len(outputs)}."
        )
        filename = outputs[0].name
        assert re.match(r"\d{4}-\d{2}-\d{2}_standup\.md$", filename), (
            f"Filename '{filename}' doesn't match 'YYYY-MM-DD_standup.md'. "
            f"Use: f'{{date}}_{{audio_path.stem}}.md'"
        )

    def test_output_dir_created_if_missing(self, tmp_path):
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "new_dir"
        assert not output_dir.exists()

        with _mock_whisper():
            from hammy import process_file
            process_file(audio, output_dir, None, FAKE_CONFIG)

        assert output_dir.exists(), (
            f"process_file should create output dir if missing. "
            f"Add: output_dir.mkdir(parents=True, exist_ok=True)"
        )
