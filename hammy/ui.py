"""Hammy terminal UI — themed output and wheel animations (stdlib only)."""
import shutil
import sys
import threading
import time
from contextlib import contextmanager

# ── ANSI codes ───────────────────────────────────────────────────────────────
def _rgb(r: int, g: int, b: int) -> str:
    return f"\033[38;2;{r};{g};{b}m"

RESET  = "\033[0m"
BOLD   = "\033[1m"
ITALIC = "\033[3m"

# ── Color palette ────────────────────────────────────────────────────────────
PINK      = _rgb(255, 135, 195)  # bubblegum pink  — title, highlights
LAVENDER  = _rgb(201, 160, 220)  # wisteria        — hamster art, accents
SOFT_PINK = _rgb(255, 183, 213)  # muted pink      — regular status text
RULE_COL  = _rgb(177, 156, 217)  # lavender        — section dividers
SUCCESS   = _rgb(152, 251, 152)  # pale green      — success messages
WARNING   = _rgb(255, 213, 128)  # warm yellow     — warnings
ERROR     = _rgb(255, 107, 107)  # soft red        — errors
CREAM     = _rgb(255, 253, 208)  # cream           — subtitle

# ── Splash screen ─────────────────────────────────────────────────────────────
def print_splash() -> None:
    """Print the Hammy splash screen."""
    p, l, r = PINK, LAVENDER, RESET
    print()
    print(f'  {p}██╗  ██╗ █████╗ ███╗   ███╗███╗   ███╗██╗   ██╗{r}')
    print(f'  {p}██║  ██║██╔══██╗████╗ ████║████╗ ████║╚██╗ ██╔╝{r}')
    print(f'  {p}███████║███████║██╔████╔██║██╔████╔██║ ╚████╔╝ {r}   {l}(\\(\\{r}')
    print(f'  {p}██╔══██║██╔══██║██║╚██╔╝██║██║╚██╔╝██║  ╚██╔╝  {r}   {l}( •ω•){r}')
    print(f'  {p}██║  ██║██║  ██║██║ ╚═╝ ██║██║ ╚═╝ ██║   ██║   {r}   {l}o_(")("){r}')
    print(f'  {p}╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝     ╚═╝   ╚═╝{r}')
    print()
    print(f'  {ITALIC}{CREAM}transcribing your meetings, one wheel-spin at a time.{r}')
    print()

# ── Reel spinner ──────────────────────────────────────────────────────────────
_REEL_FRAMES = [
    ["  ╭─────╮", " /   │   \\", "│    ⊙    │", " \\  ╱ ╲  /", "  ╰─────╯"],
    ["  ╭─────╮", " / ╲     \\", "│    ⊙──  │", " \\  ╱    /", "  ╰─────╯"],
    ["  ╭─────╮", " /    ╱  \\", "│  ──⊙    │", " \\   │   /", "  ╰─────╯"],
    ["  ╭─────╮", " /    ╱  \\", "│ ──⊙     │", " \\    ╲  /", "  ╰─────╯"],
]
_REEL_H      = len(_REEL_FRAMES[0])   # 5 lines tall
_REEL_COLORS = [PINK, LAVENDER, SOFT_PINK, LAVENDER, PINK, CREAM]
_CLR         = '\033[2K\r'            # erase line + return to col 0

@contextmanager
def wheel_status(message: str):
    """Spin a reel animation while work is happening."""
    stop_event = threading.Event()

    def _draw(frame, color):
        for j, line in enumerate(frame):
            sys.stderr.write(_CLR)
            if j == 2:  # centre row — hang the message to the right
                sys.stderr.write(f'{color}{line}{RESET}  {SOFT_PINK}{message}{RESET}\n')
            else:
                sys.stderr.write(f'{color}{line}{RESET}\n')

    def _spin():
        i = 0
        _draw(_REEL_FRAMES[0], _REEL_COLORS[0])
        sys.stderr.flush()
        while not stop_event.is_set():
            time.sleep(0.13)
            i += 1
            sys.stderr.write(f'\033[{_REEL_H}A')   # jump back to top of reel
            _draw(_REEL_FRAMES[i % len(_REEL_FRAMES)], _REEL_COLORS[i % len(_REEL_COLORS)])
            sys.stderr.flush()
        # erase all reel lines
        sys.stderr.write(f'\033[{_REEL_H}A')
        for _ in range(_REEL_H):
            sys.stderr.write(_CLR + '\n')
        sys.stderr.write(f'\033[{_REEL_H}A')
        sys.stderr.flush()

    t = threading.Thread(target=_spin, daemon=True)
    t.start()
    try:
        yield
    finally:
        stop_event.set()
        t.join()

# ── Output helpers ────────────────────────────────────────────────────────────
def ok(msg: str) -> None:
    print(f'  {SUCCESS}✓{RESET} {SOFT_PINK}{msg}{RESET}', flush=True)

def warn(msg: str) -> None:
    print(f'  {WARNING}⚠{RESET}  {WARNING}{msg}{RESET}', flush=True)

def err(msg: str) -> None:
    print(f'  {ERROR}✗{RESET} {ERROR}{msg}{RESET}', flush=True)

def info(msg: str) -> None:
    print(f'  {SOFT_PINK}{msg}{RESET}', flush=True)

def section(title: str) -> None:
    width = shutil.get_terminal_size(fallback=(80, 24)).columns
    label = f' (>w<) {title} '
    dashes = max(0, width - len(label))
    left  = dashes // 2
    right = dashes - left
    print(f'\n{RULE_COL}{"─" * left}{PINK}{label}{RULE_COL}{"─" * right}{RESET}', flush=True)
