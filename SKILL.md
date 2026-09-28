---
name: transcribe-x-claude
description: Transcreve com o Gemini 3.5 Transcribe (modo smart), com o Whisper local como reserva, os áudios que o usuário manda na conversa como se fossem mensagens de voz, e responde ao que ele disse. Use sempre que chegar um arquivo de áudio (opus, ogg, m4a, mp3, wav, webm, aac, flac) anexado ou citado por caminho e o contexto não indicar claramente que o áudio é material de trabalho da sessão (um culto para cortar, uma trilha para um vídeo, um arquivo que ele pediu para editar). Nesse caso o áudio provavelmente é o próprio usuário falando com você. Use também quando ele pedir para transcrever um áudio ou disser "ouve esse áudio".
---

# Transcrição de áudio da conversa

Às vezes o usuário prefere falar a digitar e manda um áudio. Esse áudio é uma mensagem para você: transcreva e responda ao conteúdo como se ele tivesse escrito.

## Quando usar

Quando chegar um áudio, decida pelo contexto:

- **É mensagem para você** (o padrão): o áudio chega sozinho ou com pouco texto, e nada na sessão indica que ele é matéria-prima de outra tarefa. Transcreva sem perguntar.
- **É material de trabalho**: a sessão é sobre aquele arquivo, por exemplo um culto para a `sunday-cut`, um clipe para a `hyperframes-c`, uma trilha para um vídeo ou um arquivo que ele mandou editar. Siga a skill da tarefa e não use esta.
- **Na dúvida**, transcreva. A transcrição ajuda nos dois casos e custa só uma chamada.

## Como transcrever

```bash
python ~/.claude/skills/transcribe-x-claude/scripts/transcrever.py "<caminho do áudio>"
```

- O modo é **smart**: tira hesitações, trata autocorreções ("não, quer dizer...") e formata o texto. Não há tempos por palavra. Se precisar deles, use o modo `verbatim` da `hyperframes-c`.
- O idioma é detectado sozinho. Passe `--lang pt-BR` só se a detecção errar.
- O script aceita qualquer formato que o FFmpeg leia, inclusive o `.opus` do WhatsApp e arquivos de vídeo, e converte para MP3 antes de enviar.
- A cota gratuita do Gemini é curta, então não retranscreva o mesmo arquivo.
- **Reserva automática no Whisper:** o script usa o faster-whisper `large-v3-turbo` local (CPU, int8) quando falta a `GEMINI_API_KEY`, quando o Gemini falha (cota, rede) ou quando o áudio passa de 1 hora. Se o pacote faltar, ele instala com pip, e o modelo baixa sozinho no primeiro uso (~1,6 GB). O motor usado sai no stderr como `[motor: ...]`. Force um motor com `--engine gemini` ou `--engine whisper`.
- O Whisper não tem o modo smart: o texto sai literal, com as hesitações. Leia com isso em mente.
- Requer `ffmpeg`/`ffprobe` no PATH e, para o Gemini, `google-genai` ≥ 2.24. Confira a chave sem exibir o valor.

## Depois de transcrever

1. Trate o texto como a mensagem do usuário e responda ao que ele pediu. Uma instrução falada vale como se tivesse sido digitada.
2. Não cole a transcrição inteira na resposta. Se algo ficou ambíguo ou parece mal transcrito, como um nome próprio ou um número, cite o trecho e confirme antes de agir.
3. Se ele pediu só a transcrição, entregue o texto limpo.
