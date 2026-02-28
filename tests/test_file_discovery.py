"""
Tests for audio file discovery.

Tests find_audio_files(path) which returns a list of Path objects.
Supported extensions: .m4a, .mp3, .wav, .ogg, .flac, .webm

Plan reference: "Step 1: Transcription" section of plan.md
"""

from hammy import find_audio_files

SUPPORTED = {".m4a", ".mp3", ".wav", ".ogg", ".flac", ".webm"}


class TestFindAudioFiles:
    """find_audio_files(path) discovers the right files."""

    def test_finds_m4a_files(self, tmp_path):
        (tmp_path / "call.m4a").touch()
        files = find_audio_files(str(tmp_path))
        extensions = {f.suffix.lower() for f in files}
        assert ".m4a" in extensions, (
            f"find_audio_files did not find .m4a files. "
            f"Found: {[f.name for f in files]}. "
            f"Make sure .m4a is in SUPPORTED_EXTENSIONS."
        )

    def test_finds_all_supported_formats(self, audio_dir):
        files = find_audio_files(str(audio_dir))
        found = {f.suffix.lower() for f in files}
        assert SUPPORTED.issubset(found), (
            f"find_audio_files should find all supported formats. "
            f"Expected at least: {sorted(SUPPORTED)}. "
            f"Found: {sorted(found)}. "
            f"Missing: {sorted(SUPPORTED - found)}."
        )

    def test_ignores_non_audio_files(self, audio_dir):
        files = find_audio_files(str(audio_dir))
        non_audio = {".txt", ".pdf", ".md", ".py", ".docx"}
        found = {f.suffix.lower() for f in files}
        overlap = found & non_audio
        assert not overlap, (
            f"find_audio_files returned non-audio files: {sorted(overlap)}. "
            f"Only return files with audio extensions."
        )

    def test_single_file_returns_that_file(self, single_audio_file):
        files = find_audio_files(str(single_audio_file))
        assert len(files) == 1, (
            f"When given a single file path, should return [that_file]. "
            f"Expected 1 file, got {len(files)}: {files}. "
            f"Check: if path.is_file() and has audio extension, return [path]."
        )

    def test_empty_directory_returns_empty_list(self, tmp_path):
        files = find_audio_files(str(tmp_path))
        assert files == [], (
            f"Empty directory should return []. Got: {files}."
        )

    def test_no_audio_in_directory_returns_empty(self, tmp_path):
        (tmp_path / "readme.txt").touch()
        (tmp_path / "data.pdf").touch()
        files = find_audio_files(str(tmp_path))
        assert files == [], (
            f"Directory with only non-audio files should return []. "
            f"Got: {[f.name for f in files]}."
        )

    def test_single_non_audio_file_returns_empty(self, tmp_path):
        txt = tmp_path / "notes.txt"
        txt.touch()
        files = find_audio_files(str(txt))
        assert files == [], (
            f"Non-audio file should return []. Got: {files}. "
            f"Check file extension before returning."
        )

    def test_returns_list(self, audio_dir):
        files = find_audio_files(str(audio_dir))
        assert isinstance(files, list), (
            f"find_audio_files must return a list, got {type(files).__name__}."
        )
