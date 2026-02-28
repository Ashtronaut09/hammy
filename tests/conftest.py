"""
Shared fixtures for audio transcriber tests.

All external dependencies (mlx_whisper, claude CLI, ollama) are mocked.
Tests run instantly with no hardware or API requirements.
"""

import pytest
from pathlib import Path
from subprocess import CompletedProcess

from hammy import STASH_DIR
from hammy.core import DEFAULT_OLLAMA_MODEL

# ---------------------------------------------------------------------------
# Fake data constants
# ---------------------------------------------------------------------------

SUPPORTED_AUDIO_EXTENSIONS = {".m4a", ".mp3", ".wav", ".ogg", ".flac", ".webm"}
NON_AUDIO_EXTENSIONS = {".txt", ".pdf", ".md", ".py", ".docx"}

FAKE_TRANSCRIPT = (
    "[00:00] Hey everyone, let's get started with the standup.\n"
    "[00:05] Sure. Yesterday I finished the auth module refactor.\n"
    "[00:12] Nice. I'm still working on the database migration.\n"
    "[00:20] Any blockers?\n"
    "[00:22] Yeah, I need the new schema docs from Sarah.\n"
    "[00:30] Sarah, can you get those over by end of day?\n"
    "[00:33] Already on it, will send by 3pm.\n"
    "[00:40] Great. Anything else? Ok let's wrap up."
)

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

FAKE_STRUCTURED_NOTES = (
    "# Team Standup\n\n"
    "**Date:** 2026-02-09\n"
    "**Source:** standup.m4a\n"
    "**Duration:** 0:45\n\n"
    "## Summary\n\n"
    "The team held a brief standup meeting. The auth module refactor is complete.\n"
    "Database migration is in progress, blocked on schema docs from Sarah.\n\n"
    "## Key Takeaways\n\n"
    "- Auth module refactor is complete.\n"
    "- Database migration blocked on schema docs.\n"
    "- Sarah will send schema docs by 3pm.\n\n"
    "## Action Items\n\n"
    "- [ ] Sarah — Send schema docs by 3pm today.\n"
    "- [ ] Continue database migration after receiving docs.\n\n"
    "## Detailed Notes\n\n"
    "### Auth Module\n"
    "Refactor completed yesterday. No issues.\n\n"
    "### Database Migration\n"
    "Blocked on schema docs from Sarah. She will deliver by 3pm.\n"
)

FAKE_CLAUDE_RESULT = CompletedProcess(
    args=["claude", "-p", "..."],
    returncode=0,
    stdout=FAKE_STRUCTURED_NOTES,
    stderr="",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_transcript():
    return FAKE_TRANSCRIPT


@pytest.fixture
def fake_whisper_result():
    return FAKE_WHISPER_RESULT


@pytest.fixture
def audio_dir(tmp_path):
    """Directory with dummy audio files and non-audio files."""
    for ext in SUPPORTED_AUDIO_EXTENSIONS:
        (tmp_path / f"recording{ext}").touch()
    for ext in NON_AUDIO_EXTENSIONS:
        (tmp_path / f"document{ext}").touch()
    return tmp_path


@pytest.fixture
def single_audio_file(tmp_path):
    """A single dummy .m4a file."""
    f = tmp_path / "meeting-call-feb9.m4a"
    f.touch()
    return f


@pytest.fixture
def output_dir(tmp_path):
    """A temp directory for output files."""
    d = tmp_path / "output"
    d.mkdir()
    return d
