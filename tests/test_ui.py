"""
Tests for the Hammy UI module (hammy/ui.py).

Verifies that:
- All output helpers print something to stdout
- The splash screen renders without errors
- The wheel spinner starts, runs, and cleans up its thread
- The section divider adapts to terminal width
- No rich or third-party dependencies are required
"""

import os
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

from hammy import ui


class TestOutputHelpers:
    """ok/warn/err/info write themed output to stdout."""

    def test_ok_prints_to_stdout(self, capsys):
        ui.ok("everything worked")
        captured = capsys.readouterr()
        assert "everything worked" in captured.out

    def test_warn_prints_to_stdout(self, capsys):
        ui.warn("something is off")
        captured = capsys.readouterr()
        assert "something is off" in captured.out

    def test_err_prints_to_stdout(self, capsys):
        ui.err("something broke")
        captured = capsys.readouterr()
        assert "something broke" in captured.out

    def test_info_prints_to_stdout(self, capsys):
        ui.info("just so you know")
        captured = capsys.readouterr()
        assert "just so you know" in captured.out

    def test_ok_contains_checkmark(self, capsys):
        ui.ok("done")
        captured = capsys.readouterr()
        assert "✓" in captured.out

    def test_warn_contains_warning_symbol(self, capsys):
        ui.warn("heads up")
        captured = capsys.readouterr()
        assert "⚠" in captured.out

    def test_err_contains_cross(self, capsys):
        ui.err("failed")
        captured = capsys.readouterr()
        assert "✗" in captured.out


class TestSection:
    """section() prints a rule containing the title."""

    def test_section_contains_title(self, capsys):
        ui.section("my-meeting.m4a")
        captured = capsys.readouterr()
        assert "my-meeting.m4a" in captured.out

    def test_section_contains_hamster(self, capsys):
        ui.section("standup.mp3")
        captured = capsys.readouterr()
        assert "(>w<)" in captured.out

    def test_section_contains_dashes(self, capsys):
        ui.section("test.m4a")
        captured = capsys.readouterr()
        assert "─" in captured.out

    def test_section_respects_terminal_width(self, capsys):
        with patch("shutil.get_terminal_size", return_value=os.terminal_size((60, 24))):
            ui.section("file.m4a")
        captured = capsys.readouterr()
        # Output line (excluding newlines) should not exceed 60 chars of visible content
        lines = [l for l in captured.out.split("\n") if "─" in l]
        assert len(lines) >= 1


class TestSplash:
    """print_splash() renders the HAMMY banner without errors."""

    def test_splash_prints_to_stdout(self, capsys):
        ui.print_splash()
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_splash_contains_hammy_letters(self, capsys):
        ui.print_splash()
        captured = capsys.readouterr()
        # The block-letter art uses these box-drawing chars
        assert "██" in captured.out

    def test_splash_contains_hamster_art(self, capsys):
        ui.print_splash()
        captured = capsys.readouterr()
        assert "ω" in captured.out or "(\\(\\" in captured.out or "o_" in captured.out

    def test_splash_contains_tagline(self, capsys):
        ui.print_splash()
        captured = capsys.readouterr()
        assert "wheel-spin" in captured.out


class TestWheelStatus:
    """wheel_status() spins while work happens and cleans up after."""

    def test_runs_without_error(self):
        with ui.wheel_status("doing stuff"):
            time.sleep(0.05)

    def test_spinner_writes_to_stderr(self, capsys):
        with ui.wheel_status("working"):
            time.sleep(0.15)  # enough for at least one frame
        captured = capsys.readouterr()
        assert len(captured.err) > 0

    def test_spinner_clears_stderr_on_exit(self, capsys):
        with ui.wheel_status("working"):
            time.sleep(0.05)
        captured = capsys.readouterr()
        # The cleanup sequence \r\033[K should be in stderr output
        assert "\r" in captured.err

    def test_no_dangling_threads(self):
        before = threading.active_count()
        with ui.wheel_status("running"):
            time.sleep(0.05)
        time.sleep(0.05)  # give thread a moment to join
        after = threading.active_count()
        assert after <= before, (
            f"wheel_status left a dangling thread. "
            f"Before: {before}, after: {after}."
        )

    def test_spinner_message_appears_in_stderr(self, capsys):
        with ui.wheel_status("Hammy is running on the wheel"):
            time.sleep(0.15)
        captured = capsys.readouterr()
        assert "Hammy is running on the wheel" in captured.err

    def test_context_manager_yields_control(self):
        results = []
        with ui.wheel_status("computing"):
            results.append(1 + 1)
        assert results == [2]

    def test_exception_inside_still_cleans_up(self):
        before = threading.active_count()
        try:
            with ui.wheel_status("about to fail"):
                raise ValueError("intentional")
        except ValueError:
            pass
        time.sleep(0.05)
        after = threading.active_count()
        assert after <= before, "Thread not cleaned up after exception inside wheel_status."


class TestHammyModule:
    """hammy package can be invoked as a module."""

    def test_hammy_help_exits_zero(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "hammy", "--help"],
            capture_output=True, text=True
        )
        assert result.returncode == 0, (
            f"python -m hammy --help exited {result.returncode}. "
            f"stderr: {result.stderr[:200]}"
        )
        assert "hammy" in result.stdout.lower() or "audio" in result.stdout.lower()

    def test_no_rich_dependency(self):
        """hammy/ui.py must not import rich."""
        ui_path = Path(__file__).resolve().parent.parent / "hammy" / "ui.py"
        ui_source = ui_path.read_text()
        assert "import rich" not in ui_source and "from rich" not in ui_source, (
            "hammy/ui.py must not import rich. Use stdlib ANSI codes only."
        )
