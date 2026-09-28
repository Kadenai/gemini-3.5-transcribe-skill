# Transcribe X Claude

**Português** · [English](README.en.md)

Skill do Claude Code que transcreve os áudios mandados na conversa com o Gemini 3.5 Transcribe, no modo smart, e responde ao que foi dito. Se a chave faltar ou a API falhar, usa o faster-whisper local, que se instala e baixa o modelo sozinho.

## Instalação

```bash
git clone https://github.com/Kadenai/transcribe-x-claude ~/.claude/skills/transcribe-x-claude
python -m pip install "google-genai>=2.24"
```

Requer também `ffmpeg` e `ffprobe` no PATH e a variável `GEMINI_API_KEY` no ambiente (sem ela, só o Whisper).

## Uso direto

```bash
python scripts/transcrever.py <áudio> [--lang pt-BR] [--engine auto|gemini|whisper]
                                      [--mode smart|verbatim] [--timestamps] [--diarize] [--json saida.json]
```

- `smart` (padrão): texto limpo, sem hesitações.
- `--timestamps` / `--diarize`: modo verbatim com tempos por palavra e separação de locutores.

## Áudios longos

Cada chamada do Gemini aceita até 1 hora, ou 30 minutos com tempos ou diarização. Acima disso, o script detecta os silêncios com o FFmpeg e corta o áudio em partes de 25 a 28 minutos, sempre numa pausa. Se não houver pausa, corta aos 25 minutos com 2 segundos de sobreposição. Faz uma chamada por parte e junta tudo no fim, com os tempos corrigidos.
