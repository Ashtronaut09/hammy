"""
Tests for LLM note structuring (mocked).

Tests:
- structure_with_claude_code(transcript, source_name, duration, date_str, prompt)
- structure_with_ollama(transcript, source_name, duration, date_str, prompt, model)

Plan reference: "Step 2: Note Structuring" section of plan.md
"""

import json
from unittest.mock import patch, MagicMock
from subprocess import CompletedProcess

from hammy.llm import structure_with_claude_code, structure_with_ollama

FAKE_TRANSCRIPT = (
    "[00:00] Hey everyone, let's get started.\n"
    "[00:05] I finished the auth module refactor."
)
FAKE_LLM_OUTPUT = "# Standup\n\n## Summary\nAuth refactor done.\n"
FAKE_PROMPT = "Summarize this meeting transcript into structured notes."


class TestStructureWithClaude:
    """structure_with_claude_code() calls Claude Code CLI correctly."""

    def test_calls_subprocess(self):
        fake = CompletedProcess(args=[], returncode=0, stdout=FAKE_LLM_OUTPUT, stderr="")
        with patch("hammy.llm.subprocess.run", return_value=fake) as mock_run:
            structure_with_claude_code(FAKE_TRANSCRIPT, "standup.m4a", "0:45", "2026-02-09", FAKE_PROMPT)
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "claude", (
                f"Expected subprocess to call 'claude', got '{cmd[0]}'. "
                f"Use: subprocess.run(['claude', '-p', prompt], ...)"
            )

    def test_uses_p_flag(self):
        fake = CompletedProcess(args=[], returncode=0, stdout=FAKE_LLM_OUTPUT, stderr="")
        with patch("hammy.llm.subprocess.run", return_value=fake) as mock_run:
            structure_with_claude_code(FAKE_TRANSCRIPT, "standup.m4a", "0:45", "2026-02-09", FAKE_PROMPT)
            cmd = mock_run.call_args[0][0]
            assert "-p" in cmd, (
                f"Claude must be called with -p for non-interactive mode. "
                f"Command: {cmd}"
            )

    def test_prompt_includes_transcript(self):
        fake = CompletedProcess(args=[], returncode=0, stdout=FAKE_LLM_OUTPUT, stderr="")
        with patch("hammy.llm.subprocess.run", return_value=fake) as mock_run:
            structure_with_claude_code(FAKE_TRANSCRIPT, "standup.m4a", "0:45", "2026-02-09", FAKE_PROMPT)
            cmd = mock_run.call_args[0][0]
            prompt = cmd[2] if len(cmd) > 2 else ""
            assert "auth module refactor" in prompt, (
                f"Prompt must include the transcript text. "
                f"Could not find transcript content in: '{prompt[:200]}...'"
            )

    def test_prompt_includes_instructions(self):
        fake = CompletedProcess(args=[], returncode=0, stdout=FAKE_LLM_OUTPUT, stderr="")
        with patch("hammy.llm.subprocess.run", return_value=fake) as mock_run:
            structure_with_claude_code(FAKE_TRANSCRIPT, "standup.m4a", "0:45", "2026-02-09", FAKE_PROMPT)
            cmd = mock_run.call_args[0][0]
            prompt = (cmd[2] if len(cmd) > 2 else "").lower()
            # Check prompt asks for structured sections (via prompt.txt or inline)
            assert any(kw in prompt for kw in ["summary", "summarize", "meeting notes", "structure"]), (
                f"Prompt should instruct the LLM to produce structured notes. "
                f"Expected keywords like 'summary', 'meeting notes', etc. "
                f"Got: '{prompt[:300]}...'"
            )

    def test_returns_output_on_success(self):
        fake = CompletedProcess(args=[], returncode=0, stdout=FAKE_LLM_OUTPUT, stderr="")
        with patch("hammy.llm.subprocess.run", return_value=fake):
            result = structure_with_claude_code(FAKE_TRANSCRIPT, "standup.m4a", "0:45", "2026-02-09", FAKE_PROMPT)
        assert result is not None and len(result) > 0, (
            f"Should return the LLM output string. Got: {result!r}. "
            f"Return result.stdout.strip() from subprocess."
        )

    def test_returns_none_on_failure(self):
        fake = CompletedProcess(args=[], returncode=1, stdout="", stderr="error")
        with patch("hammy.llm.subprocess.run", return_value=fake):
            result = structure_with_claude_code(FAKE_TRANSCRIPT, "standup.m4a", "0:45", "2026-02-09", FAKE_PROMPT)
        assert result is None, (
            f"When Claude fails (returncode != 0), should return None. "
            f"Got: {result!r}. Check returncode before using stdout."
        )

    def test_returns_none_on_empty_stdout(self):
        fake = CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with patch("hammy.llm.subprocess.run", return_value=fake):
            result = structure_with_claude_code(FAKE_TRANSCRIPT, "standup.m4a", "0:45", "2026-02-09", FAKE_PROMPT)
        assert result is None, (
            f"When stdout is empty, should return None. Got: {result!r}."
        )


class TestStructureWithOllama:
    """structure_with_ollama() calls Ollama API correctly."""

    def test_posts_to_correct_endpoint(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": FAKE_LLM_OUTPUT}
        with patch("hammy.llm.requests.post", return_value=mock_resp) as mock_post:
            structure_with_ollama(FAKE_TRANSCRIPT, "standup.m4a", "0:45", "2026-02-09", FAKE_PROMPT, "llama3.1:8b")
            url = mock_post.call_args[0][0]
            assert "11434" in url, (
                f"Should POST to localhost:11434. Got: '{url}'."
            )
            assert "/api/generate" in url or "/api/chat" in url, (
                f"URL must use /api/generate or /api/chat. Got: '{url}'."
            )

    def test_includes_transcript_in_body(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": FAKE_LLM_OUTPUT}
        with patch("hammy.llm.requests.post", return_value=mock_resp) as mock_post:
            structure_with_ollama(FAKE_TRANSCRIPT, "standup.m4a", "0:45", "2026-02-09", FAKE_PROMPT, "llama3.1:8b")
            body = mock_post.call_args[1].get("json", {})
            body_str = json.dumps(body)
            assert "auth module refactor" in body_str, (
                f"Request body must include transcript. "
                f"Body: {body_str[:300]}..."
            )

    def test_uses_specified_model(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": FAKE_LLM_OUTPUT}
        with patch("hammy.llm.requests.post", return_value=mock_resp) as mock_post:
            structure_with_ollama(FAKE_TRANSCRIPT, "standup.m4a", "0:45", "2026-02-09", FAKE_PROMPT, "mistral:7b")
            body = mock_post.call_args[1].get("json", {})
            assert body.get("model") == "mistral:7b", (
                f"Should use specified model in request body. "
                f"Expected 'mistral:7b', got body: {body}."
            )

    def test_returns_output_on_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": FAKE_LLM_OUTPUT}
        mock_resp.raise_for_status = MagicMock()
        with patch("hammy.llm.requests.post", return_value=mock_resp):
            result = structure_with_ollama(FAKE_TRANSCRIPT, "standup.m4a", "0:45", "2026-02-09", FAKE_PROMPT, "llama3.1:8b")
        assert result is not None and len(result) > 0, (
            f"Should return Ollama response text. Got: {result!r}."
        )

    def test_returns_none_on_connection_error(self):
        with patch("hammy.llm.requests.post", side_effect=Exception("refused")):
            result = structure_with_ollama(FAKE_TRANSCRIPT, "standup.m4a", "0:45", "2026-02-09", FAKE_PROMPT, "llama3.1:8b")
        assert result is None, (
            f"When Ollama is unreachable, should return None. Got: {result!r}. "
            f"Wrap requests.post in try/except."
        )
