# Gemini 3.5 Transcribe Skill

Skill do Claude Code que transcreve os áudios mandados na conversa com o Gemini 3.5 Transcribe, no modo smart, e responde ao que foi dito.

## Instalação

```bash
git clone https://github.com/Kadenai/gemini-3.5-transcribe-skill ~/.claude/skills/transcricao
python -m pip install "google-genai>=2.24"
```

Requer também `ffmpeg` e `ffprobe` no PATH e a variável `GEMINI_API_KEY` no ambiente.

## Uso direto

```bash
python scripts/transcrever.py <áudio> [--lang pt-BR]
```
