```
  ██╗  ██╗ █████╗ ███╗   ███╗███╗   ███╗██╗   ██╗
  ██║  ██║██╔══██╗████╗ ████║████╗ ████║╚██╗ ██╔╝
  ███████║███████║██╔████╔██║██╔████╔██║ ╚████╔╝    (\(\
  ██╔══██║██╔══██║██║╚██╔╝██║██║╚██╔╝██║  ╚██╔╝    ( •ω•)
  ██║  ██║██║  ██║██║ ╚═╝ ██║██║ ╚═╝ ██║   ██║    o_(")(")
  ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝     ╚═╝   ╚═╝

  transcribing your meetings, one wheel-spin at a time.
```

Your meeting notes, handled entirely on your own machine. No cloud, no subscriptions, no recording uploaded to a stranger's server. Just drop an audio file in a folder, run `hammy`, and get structured Markdown notes — summary, key takeaways, action items, and the full timestamped transcript — before you've finished your coffee.

Everything happens locally. Transcription runs on-device using Whisper. Note structuring runs through whatever LLM you already have — Ollama, Claude Code, Codex CLI, or an API key you already own. If you pair it with Ollama you can process a full meeting with zero internet connection, which means it works on a plane, in a basement, or anywhere you'd rather your recordings not leave the room.

## How it works

1. Drop audio into your **thewheel/** folder
2. Run `hammy`
3. Find structured notes in your **stash/** folder

That's it. Hammy figures out the best transcription model for your hardware, auto-detects whatever LLM you have available, and handles the rest.

## Requirements

- Python 3.11+
- [pipx](https://pipx.pypa.io) (recommended for installation)
- **ffmpeg** — needed for `.aac`, `.mp4`, `.aiff`, `.webm` files: `brew install ffmpeg`

## Installation

Install with the extra that matches your hardware:

```bash
# Mac with Apple Silicon (M1/M2/M3/M4)
pipx install "hammy[mac]"

# PC with NVIDIA GPU
pipx install "hammy[nvidia]"

# PC with AMD GPU or CPU only
pipx install "hammy[cpu]"
```

## First-time setup

Run the interactive setup wizard once before using Hammy:

```bash
hammy setup
```

The wizard walks you through:
- **Platform** — Mac Silicon, NVIDIA, AMD, or CPU
- **Language** — English-optimised or multilingual models
- **Transcription model** — recommends the best model for your hardware
- **LLM backend** — how to structure notes (see [LLM backends](#llm-backends))
- **Workspace location** — where thewheel/ and stash/ folders will live

Config is saved to `~/.config/hammy/config.json`.

## Usage

```bash
# Process all audio in thewheel/ (configured during setup)
hammy

# Process a specific file
hammy meeting.m4a

# Process all audio in a directory
hammy ~/recordings/

# Save notes to a different folder
hammy --output ~/notes/

# Force a specific LLM backend
hammy --llm ollama
hammy --llm claude_code
hammy --llm none        # raw transcript only

# Use a specific Ollama model
hammy --model mistral:7b

# Check for updated model recommendations
hammy check
```

### Supported audio formats

`.m4a` `.mp3` `.wav` `.ogg` `.flac` `.webm` `.aiff` `.aifc` `.mp4` `.aac`

## LLM backends

Hammy auto-detects which LLM to use, or you can pin one during `hammy setup` or override with `--llm`. The fully offline path is **Ollama** — everything stays on your machine, no API key required.

| Backend | Offline? | What you need |
|---|---|---|
| `ollama` | Yes | [Ollama](https://ollama.com) running locally |
| `claude_code` | No | [Claude Code CLI](https://claude.ai/code) installed and signed in |
| `codex_cli` | No | [OpenAI Codex CLI](https://github.com/openai/codex) installed and signed in |
| `anthropic_api` | No | Anthropic API key (set during `hammy setup`) |
| `openai_api` | No | OpenAI API key (set during `hammy setup`) |
| `none` | Yes | Nothing — saves raw timestamped transcript only |

## Output

Each processed file produces a Markdown file in stash/ named `YYYY-MM-DD_filename.md`. If an LLM is available the file contains structured notes followed by the raw transcript. If no LLM is configured, the raw timestamped transcript is saved on its own.

After processing, the original audio file is moved into stash/ alongside the notes.

Already-processed files are skipped automatically on subsequent runs.

## Customising the prompt

To change how Hammy structures notes, create a `prompt.txt` file in your workspace root (the parent of stash/). Hammy will use it instead of the built-in prompt.

```
~/hammy/prompt.txt   ← your custom prompt
~/hammy/thewheel/    ← drop audio here
~/hammy/stash/       ← notes land here
```

## Transcription models

Models are selected during `hammy setup` based on your platform and language preference. Run `hammy check` to see if newer recommendations are available.

| Platform | English (recommended) | Multilingual (recommended) |
|---|---|---|
| Mac Silicon | parakeet-tdt-0.6b-v2 (1.2 GB) | whisper-large-v3 (3.1 GB) |
| NVIDIA GPU | parakeet-tdt-0.6b-v2 (1.2 GB) | faster-whisper-large-v3 (3.1 GB) |
| AMD GPU | faster-whisper-large-v3-turbo (1.6 GB) | faster-whisper-large-v3 (3.1 GB) |
| CPU | faster-whisper-medium (1.5 GB) | faster-whisper-medium (1.5 GB) |

## License

MIT
