# Transcribe X Claude

Skill do Claude Code que transcreve os áudios mandados na conversa com o Gemini 3.5 Transcribe, no modo smart, e responde ao que foi dito. Se a chave faltar, a cota acabar ou o áudio passar de 1 hora, usa o faster-whisper local, que se instala e baixa o modelo sozinho.

## Instalação

```bash
git clone https://github.com/Kadenai/transcribe-x-claude ~/.claude/skills/transcribe-x-claude
python -m pip install "google-genai>=2.24"
```

Requer também `ffmpeg` e `ffprobe` no PATH e a variável `GEMINI_API_KEY` no ambiente (sem ela, só o Whisper).

## Uso direto

```bash
python scripts/transcrever.py <áudio> [--lang pt-BR] [--engine auto|gemini|whisper]
```
