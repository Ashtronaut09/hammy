"""Hammy terminal UI — themed output and wheel animations (stdlib only)."""
import shutil
import sys
import threading
import time
from contextlib import contextmanager
from math import ceil

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

# ── Parakeet chunk progress ───────────────────────────────────────────────────
_SPIN_FRAMES  = ['|', '/', '-', '\\']
_SPIN_COLORS  = [PINK, LAVENDER, SOFT_PINK, CREAM, PINK, LAVENDER]
_BAR_W        = 18
_SCAN_W       = 3
_WIN          = 4   # lines always on screen — never changes, so cursor math is trivial


def _progress_lines(active, total, frame, label):
    """Build exactly _WIN lines for the sliding window.

    active  — 1-based index of the chunk currently processing (0 = not started)
    total   — total chunk count once known, else None
    """
    col  = _SPIN_COLORS[frame % len(_SPIN_COLORS)]
    spin = _SPIN_FRAMES[frame % len(_SPIN_FRAMES)]

    win_start = max(1, active - 1) if active > 0 else 1
    lines = []
    for i in range(_WIN):
        n = win_start + i

        if total is not None and n > total:
            # Past the end — blank padding so line count stays at _WIN
            lines.append(f'  {LAVENDER} [{" " * _BAR_W}]{RESET}')
            continue

        if active == 0 or n > active:          # pending
            bar  = LAVENDER + "░" * _BAR_W
            lines.append(f'  {LAVENDER}·{RESET} {LAVENDER}[{bar}{LAVENDER}]{RESET}'
                         f'  {SOFT_PINK}chunk {n}{RESET}')
        elif n < active:                        # done
            bar  = SUCCESS + "█" * _BAR_W
            lines.append(f'  {SUCCESS}✓{RESET} {LAVENDER}[{bar}{LAVENDER}]{RESET}'
                         f'  {SOFT_PINK}chunk {n}{RESET}')
        else:                                   # active (n == active)
            pos  = frame % (_BAR_W - _SCAN_W + 1)
            bar  = LAVENDER + "░"*pos + col + "█"*_SCAN_W + LAVENDER + "░"*(_BAR_W - pos - _SCAN_W)
            of   = f' of {total}' if total else ''
            lines.append(f'  {col}{spin}{RESET} {LAVENDER}[{bar}{LAVENDER}]{RESET}'
                         f'  {SOFT_PINK}chunk {n}{of}{RESET}  {CREAM}{label}{RESET}')
    return lines


@contextmanager
def transcribe_progress(source_name: str):
    """Fixed 4-bar sliding-window progress for parakeet chunked transcription.

    Always occupies exactly _WIN lines — no growth, no cursor artifacts.
    Yields a chunk_callback(current_samples, total_samples).
    """
    _lock  = threading.Lock()
    _stop  = threading.Event()
    _state = {"active": 0, "total": None}

    def callback(current: int, total_samples: int) -> None:
        with _lock:
            _state["active"] += 1
            if _state["total"] is None and current > 0:
                # chunk_duration=30s, overlap=15s → step=15s
                sr_est         = current / 30.0
                step_samples   = 15.0 * sr_est
                _state["total"] = max(_state["active"],
                                      ceil(total_samples / step_samples))

    def _spin() -> None:
        frame = 0
        label = (source_name[:20] + "…") if len(source_name) > 21 else source_name
        drawn = False
        while not _stop.is_set():
            with _lock:
                active, total = _state["active"], _state["total"]
            lines = _progress_lines(active, total, frame, label)

            if not drawn:
                sys.stderr.write('\n'.join(lines))   # initial draw, no trailing \n
                drawn = True
            else:
                # always _WIN lines — go up (_WIN-1) then overwrite all
                sys.stderr.write(f'\r\033[{_WIN - 1}A')
                for j, line in enumerate(lines):
                    sys.stderr.write('\r\033[2K' + line)
                    if j < _WIN - 1:
                        sys.stderr.write('\n')
            sys.stderr.flush()
            frame += 1
            time.sleep(0.08)

        # cleanup: erase all _WIN lines and leave cursor where it started
        if drawn:
            sys.stderr.write(f'\r\033[{_WIN - 1}A')
            for i in range(_WIN):
                sys.stderr.write('\r\033[2K')
                if i < _WIN - 1:
                    sys.stderr.write('\n')
            sys.stderr.write(f'\r\033[{_WIN - 1}A')
            sys.stderr.flush()

    t = threading.Thread(target=_spin, daemon=True)
    t.start()
    try:
        yield callback
    finally:
        _stop.set()
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


def print_outro(file_count: int, output_dir: str) -> None:
    """Print the Hammy completion screen."""
    p, l, g, c, r = PINK, LAVENDER, SUCCESS, CREAM, RESET
    noun  = "file" if file_count == 1 else "files"
    width = shutil.get_terminal_size(fallback=(80, 24)).columns
    rule  = f'  {g}{"━" * (width - 4)}{r}'

    print()
    print(rule)
    print()
    print(f'  {l}  ╭─────╮{r}')
    print(f'  {l} / ⊙   ⊙\\{r}  {l}(\\(\\{r}')
    print(f'  {l}│  ╰───╯  │{r} {l}(≧ω≦){r}  {p}Wheel complete!{r}  {g}{file_count} {noun} stashed.{r}')
    print(f'  {l} \\       /{r}  {l}o_(")("){r}')
    print(f'  {l}  ╰─────╯{r}')
    print()
    print(f'  {ITALIC}{c}notes in the stash → {output_dir}{r}')
    print()
    print(rule)
    print(flush=True)
