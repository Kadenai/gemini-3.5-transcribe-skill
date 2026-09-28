"""Transcreve um áudio e imprime o texto.

Usa o Gemini 3.5 Transcribe no modo smart. Se a chave faltar, a API falhar
(cota, rede) ou o áudio passar de 1 hora, cai para o faster-whisper local,
instalando o pacote e baixando o modelo na primeira vez.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

GEMINI_MODEL = "gemini-3.5-transcribe"
WHISPER_MODEL = "large-v3-turbo"
LIMIT = 3600  # o Gemini aceita até 1 h por chamada


def log(message):
    print(message, file=sys.stderr, flush=True)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(f"ffprobe: {out.stderr.strip()[-600:]}")
    return float(json.loads(out.stdout)["format"]["duration"])


def gemini(audio, lang):
    from google import genai
    from google.genai import types

    client = genai.Client(http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            attempts=4, initial_delay=2, max_delay=30, jitter=1,
            http_status_codes=[408, 429, 500, 502, 503, 504],
        )))
    config = {"mode": "smart"}
    if lang:
        config["language_codes"] = [lang]
    uploaded = client.files.upload(file=str(audio))
    try:
        interaction = client.interactions.create(
            model=GEMINI_MODEL,
            input=[{"type": "audio", "uri": uploaded.uri, "mime_type": uploaded.mime_type}],
            generation_config={"transcription_config": config},
        )
    finally:
        try:
            client.files.delete(name=uploaded.name)
        except Exception:
            pass
    return interaction.output_text


def whisper(audio, lang):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        log("Instalando o faster-whisper...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "faster-whisper"], check=True)
        from faster_whisper import WhisperModel
    # CPU int8: o CUDA do faster-whisper falha sem as DLLs do cuBLAS.
    log(f"Carregando o Whisper {WHISPER_MODEL} (baixa na primeira vez)...")
    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(audio), language=lang.split("-")[0] if lang else None,
                                   vad_filter=True)
    return " ".join(s.text.strip() for s in segments)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--lang", help="código BCP-47, ex.: pt-BR (omita para detectar)")
    parser.add_argument("--engine", choices=["auto", "gemini", "whisper"], default="auto")
    args = parser.parse_args()

    source = args.audio.resolve()
    if not source.is_file():
        sys.exit(f"Arquivo não encontrado: {source}")

    engine = args.engine
    if engine == "auto":
        if not os.environ.get("GEMINI_API_KEY"):
            log("GEMINI_API_KEY ausente: usando o Whisper")
            engine = "whisper"
        elif duration(source) > LIMIT:
            log("Áudio com mais de 1 hora: usando o Whisper")
            engine = "whisper"

    with tempfile.TemporaryDirectory(prefix="transcricao-") as tmp:
        # Normaliza qualquer entrada (opus do WhatsApp, m4a, vídeo) para MP3 mono leve.
        audio = Path(tmp) / "audio.mp3"
        done = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(source),
                               "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame",
                               "-b:a", "64k", str(audio)], capture_output=True, text=True)
        if done.returncode:
            sys.exit(f"ffmpeg: {done.stderr.strip()[-600:]}")
        if engine == "whisper":
            text = whisper(audio, args.lang)
        else:
            try:
                text = gemini(audio, args.lang)
            except Exception as exc:
                if args.engine == "gemini":
                    raise
                log(f"Gemini falhou ({type(exc).__name__}: {str(exc)[:200]}): usando o Whisper")
                engine = "whisper"
                text = whisper(audio, args.lang)

    log(f"[motor: {engine}]")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
