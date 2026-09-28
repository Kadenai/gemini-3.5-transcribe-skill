"""Transcreve um áudio com o Gemini 3.5 Transcribe no modo smart e imprime o texto."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

MODEL = "gemini-3.5-transcribe"
LIMIT = 3600  # a API aceita até 1 h por chamada


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(f"ffprobe: {out.stderr.strip()[-600:]}")
    return float(json.loads(out.stdout)["format"]["duration"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--lang", help="código BCP-47, ex.: pt-BR (omita para detectar)")
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY não está configurada")
    source = args.audio.resolve()
    if not source.is_file():
        sys.exit(f"Arquivo não encontrado: {source}")
    if duration(source) > LIMIT:
        sys.exit("Áudio com mais de 1 hora: divida antes de transcrever")

    from google import genai
    from google.genai import types

    client = genai.Client(http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            attempts=4, initial_delay=2, max_delay=30, jitter=1,
            http_status_codes=[408, 429, 500, 502, 503, 504],
        )))
    config = {"mode": "smart"}
    if args.lang:
        config["language_codes"] = [args.lang]

    with tempfile.TemporaryDirectory(prefix="transcricao-") as tmp:
        # Normaliza qualquer entrada (opus do WhatsApp, m4a, vídeo) para MP3 mono leve.
        audio = Path(tmp) / "audio.mp3"
        done = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(source),
                               "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame",
                               "-b:a", "64k", str(audio)], capture_output=True, text=True)
        if done.returncode:
            sys.exit(f"ffmpeg: {done.stderr.strip()[-600:]}")
        uploaded = client.files.upload(file=str(audio))
        try:
            interaction = client.interactions.create(
                model=MODEL,
                input=[{"type": "audio", "uri": uploaded.uri, "mime_type": uploaded.mime_type}],
                generation_config={"transcription_config": config},
            )
        finally:
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                pass

    sys.stdout.reconfigure(encoding="utf-8")
    print(interaction.output_text)


if __name__ == "__main__":
    main()
