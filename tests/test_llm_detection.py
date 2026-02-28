"""
Tests for LLM backend auto-detection.

Tests get_llm_backend() which checks:
1. shutil.which("claude") — returns "claude_code" if found
2. requests.get("http://localhost:11434") — returns "ollama" if responds
3. Returns None if nothing available

Plan reference: "How the LLM auto-detection works" section of plan.md
"""

from unittest.mock import patch

from hammy import get_llm_backend


class TestAutoDetection:
    """get_llm_backend() detects available backends in priority order."""

    def test_detects_claude_when_on_path(self):
        with patch("hammy.llm.shutil.which", return_value="/usr/local/bin/claude"):
            result = get_llm_backend()
        assert result in ("claude", "claude_code"), (
            f"When 'claude' is on PATH, should return a claude backend. "
            f"Got '{result}'. "
            f"Check: if shutil.which('claude'): return 'claude_code'"
        )

    def test_detects_ollama_when_running(self):
        with patch("hammy.llm.shutil.which", return_value=None):
            with patch("hammy.llm.requests.get") as mock_get:
                mock_get.return_value.status_code = 200
                result = get_llm_backend()
        assert result == "ollama", (
            f"When claude not on PATH but Ollama responds, should return "
            f"'ollama'. Got '{result}'. "
            f"Check localhost:11434 after claude check fails."
        )

    def test_returns_none_when_nothing_available(self):
        with patch("hammy.llm.shutil.which", return_value=None):
            with patch("hammy.llm.requests.get", side_effect=Exception("refused")):
                result = get_llm_backend()
        assert result is None, (
            f"When neither is available, should return None. Got '{result}'."
        )

    def test_claude_takes_priority_over_ollama(self):
        with patch("hammy.llm.shutil.which", return_value="/usr/local/bin/claude"):
            with patch("hammy.llm.requests.get") as mock_get:
                mock_get.return_value.status_code = 200
                result = get_llm_backend()
        assert result in ("claude", "claude_code"), (
            f"When BOTH are available, should return a claude backend (highest "
            f"priority). Got '{result}'. "
            f"Check claude first, then ollama."
        )

    def test_ollama_not_checked_when_claude_found(self):
        with patch("hammy.llm.shutil.which", return_value="/usr/local/bin/claude"):
            with patch("hammy.llm.requests.get") as mock_get:
                get_llm_backend()
                mock_get.assert_not_called(), (
                    "When claude is found, Ollama should not be checked. "
                    "Return early after finding claude."
                )
