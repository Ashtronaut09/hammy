"""
Tests for skip/resume logic in process_file().

Two features:
1. Skip completed files — if the .md output already exists, skip it.
2. Atomic writes via .partial — write to .md.partial, rename to .md.
   Partial files from interrupted runs get overwritten on re-run.

Plan reference: "Add resilient skip/resume logic" feature
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from subprocess import CompletedProcess

from hammy import process_file

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


def _mock_whisper(return_value=None):
    mock_module = MagicMock()
    mock_module.transcribe.return_value = return_value or FAKE_WHISPER_RESULT
    return patch.dict(sys.modules, {"mlx_whisper": mock_module}), mock_module


class TestSkipCompleted:
    """process_file() skips files that already have .md output."""

    def test_skips_when_output_exists(self, tmp_path):
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Pre-create the output file (simulating a previous completed run)
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        existing_output = output_dir / f"{date_str}_standup.md"
        existing_output.write_text("# Previous output\nAlready done.")

        ctx, mock_mod = _mock_whisper()
        with ctx:
            process_file(audio, output_dir, None, FAKE_CONFIG)

        # Whisper should NOT have been called
        mock_mod.transcribe.assert_not_called(), (
            "When the output .md file already exists, process_file should "
            "skip the file entirely and NOT call mlx_whisper.transcribe(). "
            "Add an early return: if output_path.exists(): return"
        )

    def test_skip_prints_message(self, tmp_path, capsys):
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        existing = output_dir / f"{date_str}_standup.md"
        existing.write_text("# Already done")

        ctx, _ = _mock_whisper()
        with ctx:
            process_file(audio, output_dir, None, FAKE_CONFIG)

        captured = capsys.readouterr()
        output = captured.out.lower()
        assert "skip" in output or "already" in output, (
            f"When skipping a completed file, process_file should print a "
            f"message containing 'skip' or 'already'. Got: '{captured.out.strip()}'. "
            f"Add: print(f'  Skipping (already done): {{output_path.name}}')"
        )

    def test_skip_does_not_modify_existing_output(self, tmp_path):
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        existing = output_dir / f"{date_str}_standup.md"
        original_content = "# Previous run output\nDo not overwrite."
        existing.write_text(original_content)

        ctx, _ = _mock_whisper()
        with ctx:
            process_file(audio, output_dir, None, FAKE_CONFIG)

        assert existing.read_text() == original_content, (
            f"Skipped files should NOT be overwritten. The existing output "
            f"was modified. process_file must return early without writing."
        )

    def test_processes_when_no_output_exists(self, tmp_path):
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "output"

        ctx, mock_mod = _mock_whisper()
        with ctx:
            process_file(audio, output_dir, None, FAKE_CONFIG)

        # Whisper SHOULD have been called
        mock_mod.transcribe.assert_called_once(), (
            "When no output .md exists, process_file should proceed normally "
            "and call mlx_whisper.transcribe()."
        )
        outputs = list(output_dir.glob("*.md"))
        assert len(outputs) == 1, (
            f"Expected 1 output file to be created. Found {len(outputs)}."
        )


class TestAtomicWrite:
    """process_file() writes to .partial then renames to .md."""

    def test_no_partial_file_after_success(self, tmp_path):
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "output"

        ctx, _ = _mock_whisper()
        with ctx:
            process_file(audio, output_dir, None, FAKE_CONFIG)

        partials = list(output_dir.glob("*.partial"))
        assert partials == [], (
            f"After successful processing, no .partial files should remain. "
            f"Found: {[f.name for f in partials]}. "
            f"The .partial file must be renamed to .md after writing."
        )

    def test_md_file_exists_after_success(self, tmp_path):
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "output"

        ctx, _ = _mock_whisper()
        with ctx:
            process_file(audio, output_dir, None, FAKE_CONFIG)

        mds = list(output_dir.glob("*.md"))
        assert len(mds) == 1, (
            f"After successful processing, exactly 1 .md file should exist. "
            f"Found {len(mds)}: {[f.name for f in mds]}."
        )

    def test_partial_overwritten_on_rerun(self, tmp_path):
        """A leftover .partial from a crashed run gets overwritten."""
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Simulate a crashed previous run — .partial exists but no .md
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        stale_partial = output_dir / f"{date_str}_standup.md.partial"
        stale_partial.write_text("INCOMPLETE GARBAGE")

        ctx, _ = _mock_whisper()
        with ctx:
            process_file(audio, output_dir, None, FAKE_CONFIG)

        # .partial should be gone, replaced by .md
        assert not stale_partial.exists(), (
            f"Stale .partial file should be overwritten and renamed to .md. "
            f"The .partial file still exists."
        )
        mds = list(output_dir.glob("*.md"))
        assert len(mds) == 1, (
            f"After reprocessing, exactly 1 .md file should exist."
        )
        content = mds[0].read_text()
        assert "INCOMPLETE GARBAGE" not in content, (
            f"The stale .partial content should NOT appear in the final output. "
            f"The file was not properly reprocessed."
        )

    def test_partial_does_not_trigger_skip(self, tmp_path):
        """A .partial file should NOT cause the file to be skipped."""
        audio = tmp_path / "standup.m4a"
        audio.touch()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        stale_partial = output_dir / f"{date_str}_standup.md.partial"
        stale_partial.write_text("INCOMPLETE")

        ctx, mock_mod = _mock_whisper()
        with ctx:
            process_file(audio, output_dir, None, FAKE_CONFIG)

        mock_mod.transcribe.assert_called_once(), (
            "A .partial file should NOT prevent reprocessing. The skip check "
            "should only look for .md files, not .partial files."
        )


class TestSkipResumeIntegration:
    """End-to-end: batch processing with skip/resume."""

    def test_batch_skips_completed_reprocesses_rest(self, tmp_path):
        """
        Simulate: 3 audio files, 1 already has output.
        Expect: 2 get processed, 1 gets skipped.
        """
        audio_dir = tmp_path / "recordings"
        audio_dir.mkdir()
        (audio_dir / "meeting1.m4a").touch()
        (audio_dir / "meeting2.m4a").touch()
        (audio_dir / "meeting3.m4a").touch()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Pre-create output for meeting2 (already done)
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        done = output_dir / f"{date_str}_meeting2.md"
        done.write_text("# Already processed")

        ctx, mock_mod = _mock_whisper()
        with ctx:
            with patch("sys.argv", ["hammy", str(audio_dir),
                                    "--output", str(output_dir), "--llm", "none"]):
                from hammy import main
                main()

        # Should have 3 .md files total (1 pre-existing + 2 new)
        mds = list(output_dir.glob("*.md"))
        assert len(mds) == 3, (
            f"Expected 3 .md files (1 pre-existing + 2 new). "
            f"Found {len(mds)}: {[f.name for f in mds]}. "
            f"The skip logic may be preventing new files or the completed "
            f"file may have been overwritten."
        )

        # meeting2 should not have been reprocessed
        assert done.read_text() == "# Already processed", (
            f"meeting2.md was overwritten even though it already existed. "
            f"The skip check should prevent reprocessing completed files."
        )

        # Whisper should have been called exactly 2 times (meeting1 + meeting3)
        assert mock_mod.transcribe.call_count == 2, (
            f"Expected whisper to be called 2 times (skipping meeting2). "
            f"Called {mock_mod.transcribe.call_count} times. "
            f"The skip check should prevent calling whisper for completed files."
        )
