# Transcribe X Claude

[Português](README.md) · **English**

A Claude Code skill that transcribes the voice notes you send in a conversation using Gemini 3.5 Transcribe in smart mode, then answers what you said. If the API key is missing or the API fails, it falls back to a local faster-whisper, which installs itself and downloads its model on first use.

## Installation

```bash
git clone https://github.com/Kadenai/transcribe-x-claude ~/.claude/skills/transcribe-x-claude
python -m pip install "google-genai>=2.24"
```

It also needs `ffmpeg` and `ffprobe` on the PATH and `GEMINI_API_KEY` in the environment (without it, only Whisper runs).

## Direct use

```bash
python scripts/transcrever.py <audio> [--lang en-US] [--engine auto|gemini|whisper]
                                      [--mode smart|verbatim] [--timestamps] [--diarize] [--json out.json]
```

- `smart` (default): clean text, with filler words removed.
- `--timestamps` / `--diarize`: verbatim mode with word timestamps and speaker labels.

## Long audio

Each Gemini call takes up to 1 hour of audio, or 30 minutes with timestamps or diarization. Beyond that, the script finds silences with FFmpeg and splits the audio into 25 to 28 minute parts, always at a pause. When there is no pause, it cuts at 25 minutes with a 2 second overlap. It makes one call per part and merges everything at the end, with timestamps shifted back into place.

The skill's instructions (`SKILL.md`) and the script's messages are in Portuguese.
