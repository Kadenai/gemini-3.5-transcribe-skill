"""Transcreve um áudio e imprime o texto.

Usa o Gemini 3.5 Transcribe (modo smart por padrão). Áudios acima do limite
da API são cortados nos silêncios em partes de 25 a 28 minutos, transcritos
um por chamada e unidos no fim. Se a chave faltar ou a API falhar (cota,
rede), cai para o faster-whisper local, instalando o pacote e baixando o
modelo na primeira vez.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

GEMINI_MODEL = "gemini-3.5-transcribe"
WHISPER_MODEL = "large-v3-turbo"
PART = 1500     # cada parte tem no mínimo 25 min...
WINDOW = 180    # ...e procura um silêncio até 3 min depois (máx. 28 min)
OVERLAP = 2     # sem silêncio na janela, corta em 25 min com 2 s de sobreposição
LIMIT = 3600    # máximo por chamada no smart e no verbatim simples
LIMIT_TIMED = 1800  # com tempos ou diarização


def log(message):
    print(message, file=sys.stderr, flush=True)


def run(command):
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode:
        sys.exit(f"{command[0]}: {done.stderr.strip()[-600:]}")
    return done


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)])
    return float(json.loads(out.stdout)["format"]["duration"])


def silences(path):
    done = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
                "-af", "silencedetect=noise=-35dB:d=0.7", "-f", "null", "-"])
    found, started = [], None
    for line in done.stderr.splitlines():
        if m := re.search(r"silence_start:\s*([0-9.]+)", line):
            started = float(m.group(1))
        elif (m := re.search(r"silence_end:\s*([0-9.]+)", line)) and started is not None:
            found.append((started, float(m.group(1))))
            started = None
    return found


def spans(total, pauses):
    """Partes de 25 a 28 min, cortadas no meio do primeiro silêncio da janela."""
    result, start = [], 0.0
    while total - start > PART + WINDOW:
        low, high = start + PART, start + PART + WINDOW
        cuts = [(max(a, low) + min(b, high)) / 2 for a, b in pauses if b > low and a < high]
        if cuts:
            result.append((start, cuts[0], False))
            start = cuts[0]
        else:
            result.append((start, low, True))
            start = low - OVERLAP
    result.append((start, total, False))
    return result


def seconds(value):
    if hasattr(value, "total_seconds"):
        return float(value.total_seconds())
    return float(str(value).strip().removesuffix("s"))


def gemini_client():
    from google import genai
    from google.genai import types

    return genai.Client(http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            attempts=4, initial_delay=2, max_delay=30, jitter=1,
            http_status_codes=[408, 429, 500, 502, 503, 504],
        )))


def gemini(client, audio, config):
    uploaded = client.files.upload(file=str(audio))
    try:
        return client.interactions.create(
            model=GEMINI_MODEL,
            input=[{"type": "audio", "uri": uploaded.uri, "mime_type": uploaded.mime_type}],
            generation_config={"transcription_config": config},
        )
    finally:
        try:
            client.files.delete(name=uploaded.name)
        except Exception:
            pass


def gemini_words(interaction, offset, part, parts):
    words = []
    for step in getattr(interaction, "steps", None) or []:
        for content in getattr(step, "content", None) or []:
            for item in getattr(content, "annotations", None) or []:
                if getattr(item, "type", None) != "word_info" or item.start_offset is None:
                    continue
                word = {"start": round(offset + seconds(item.start_offset), 3),
                        "end": round(offset + seconds(item.end_offset), 3),
                        "text": str(item.text).strip()}
                if getattr(item, "speaker", None):
                    # Os rótulos do Gemini não se repetem entre chamadas: spk_1 da parte 1
                    # não é necessariamente o spk_1 da parte 2.
                    word["speaker"] = str(item.speaker) + (f"@p{part}" if parts > 1 else "")
                words.append(word)
    return words


def whisper(audio, lang, timestamps):
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
                                   vad_filter=True, word_timestamps=timestamps)
    if not timestamps:
        return " ".join(s.text.strip() for s in segments), None
    words = [{"start": round(w.start, 3), "end": round(w.end, 3), "text": w.word.strip()}
             for s in segments for w in s.words]
    return None, words


def clock(value):
    minutes, secs = divmod(int(value), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def readable(words):
    """Linhas por fala: quebra na troca de locutor, em pausas ou a cada ~12 s."""
    lines, group = [], []

    def flush():
        if group:
            who = f" {group[0]['speaker']}:" if "speaker" in group[0] else ""
            lines.append(f"[{clock(group[0]['start'])}]{who} " + " ".join(w["text"] for w in group))
            group.clear()

    for word in words:
        if group and (word.get("speaker") != group[0].get("speaker")
                      or word["start"] - group[-1]["end"] > 0.8
                      or word["end"] - group[0]["start"] > 12):
            flush()
        group.append(word)
    flush()
    return "\n".join(lines)


def transcribe_gemini(audio, total, args):
    timed = args.timestamps or args.diarize
    if args.mode == "smart":
        config = {"mode": "smart"}
    else:
        mode = {"type": "verbatim"}
        if args.timestamps:
            mode["timestamp_granularities"] = ["word"]
        if args.diarize:
            mode["diarization_mode"] = "speaker"
        config = {"mode": mode}
    if args.lang:
        config["language_codes"] = [args.lang]

    limit = LIMIT_TIMED if timed else LIMIT
    parts = spans(total, silences(audio)) if total > limit else [(0.0, total, False)]
    if len(parts) > 1:
        log(f"Áudio de {clock(total)}: {len(parts)} partes cortadas nos silêncios")

    client = gemini_client()
    texts, words = [], []
    with tempfile.TemporaryDirectory(prefix="transcricao-partes-") as tmp:
        for index, (start, end, overlapped) in enumerate(parts, 1):
            piece = audio
            if len(parts) > 1:
                piece = Path(tmp) / f"parte_{index:02d}.mp3"
                run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(start),
                     "-t", str(end - start), "-i", str(audio), "-c", "copy", str(piece)])
            interaction = gemini(client, piece, config)
            if timed:
                chunk = gemini_words(interaction, start, index, len(parts))
                if index > 1 and parts[index - 2][2]:
                    # Sobreposição: fica a metade de cada lado da emenda.
                    seam = (start + parts[index - 2][1]) / 2
                    words = [w for w in words if w["end"] <= seam]
                    chunk = [w for w in chunk if w["end"] > seam]
                words.extend(chunk)
            else:
                texts.append(interaction.output_text.strip())
            if len(parts) > 1:
                log(f"Parte {index}/{len(parts)} transcrita")
    return ("\n\n".join(texts), None) if not timed else (None, words)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--lang", help="código BCP-47, ex.: pt-BR (omita para detectar)")
    parser.add_argument("--engine", choices=["auto", "gemini", "whisper"], default="auto")
    parser.add_argument("--mode", choices=["smart", "verbatim"], default="smart")
    parser.add_argument("--timestamps", action="store_true", help="tempos por palavra (verbatim)")
    parser.add_argument("--diarize", action="store_true", help="separa os locutores (verbatim)")
    parser.add_argument("--json", type=Path, help="salva as palavras com tempos neste arquivo")
    args = parser.parse_args()
    if args.timestamps or args.diarize:
        args.mode = "verbatim"  # o smart não aceita tempos nem diarização

    source = args.audio.resolve()
    if not source.is_file():
        sys.exit(f"Arquivo não encontrado: {source}")

    engine = args.engine
    if engine == "auto" and not os.environ.get("GEMINI_API_KEY"):
        log("GEMINI_API_KEY ausente: usando o Whisper")
        engine = "whisper"

    with tempfile.TemporaryDirectory(prefix="transcricao-") as tmp:
        # Normaliza qualquer entrada (opus do WhatsApp, m4a, vídeo) para MP3 mono leve.
        audio = Path(tmp) / "audio.mp3"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(source), "-vn", "-ac", "1",
             "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "64k", str(audio)])
        total = duration(audio)
        if engine != "whisper":
            try:
                text, words = transcribe_gemini(audio, total, args)
            except Exception as exc:
                if engine == "gemini":
                    raise
                log(f"Gemini falhou ({type(exc).__name__}: {str(exc)[:200]}): usando o Whisper")
                engine = "whisper"
        if engine == "whisper":
            if args.diarize:
                log("O Whisper não separa locutores: saem só os tempos")
            text, words = whisper(audio, args.lang, args.timestamps or args.diarize)
        else:
            engine = "gemini"

    if words is not None:
        if args.json:
            args.json.write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")
        text = readable(words)
    log(f"[motor: {engine}]")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
