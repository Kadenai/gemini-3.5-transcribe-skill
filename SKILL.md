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

- O modo padrão é **smart**: tira hesitações, trata autocorreções ("não, quer dizer...") e formata o texto. Ele não tem tempos nem locutores.
- Para tempos por palavra ou para separar quem fala, passe `--timestamps` e/ou `--diarize` (o script muda para o modo `verbatim`). A saída vira linhas `[hh:mm:ss] locutor: fala`, e `--json <arquivo>` salva as palavras com os tempos. `--mode verbatim` sozinho dá o texto literal, sem tempos.
- O idioma é detectado sozinho. Passe `--lang pt-BR` só se a detecção errar.
- O script aceita qualquer formato que o FFmpeg leia, inclusive o `.opus` do WhatsApp e arquivos de vídeo, e converte para MP3 antes de enviar.
- **Áudios longos:** cada chamada do Gemini aceita até 1 hora (30 minutos com `--timestamps` ou `--diarize`). Acima disso, o script acha os silêncios com o FFmpeg e corta o áudio em partes de 25 a 28 minutos, sempre no meio de uma pausa. Se não houver pausa nessa faixa, corta aos 25 minutos com 2 segundos de sobreposição e descarta a duplicata na emenda. Faz uma chamada por parte e junta tudo no fim, com os tempos somados ao início de cada parte.
- Na diarização em várias partes, os rótulos ganham o sufixo da parte (`spk:0@p2`), porque o Gemini não mantém os mesmos rótulos entre chamadas. Deduza pelo conteúdo quem é quem.
- A cota gratuita do Gemini é curta, e um áudio longo gasta uma chamada por parte. Não retranscreva o mesmo arquivo.
- **Reserva automática no Whisper:** o script usa o faster-whisper `large-v3-turbo` local (CPU, int8) quando falta a `GEMINI_API_KEY` ou quando o Gemini falha (cota, rede). Se o pacote faltar, ele instala com pip, e o modelo baixa sozinho no primeiro uso (~1,6 GB). O motor usado sai no stderr como `[motor: ...]`. Force um motor com `--engine gemini` ou `--engine whisper`.
- O Whisper não tem o modo smart nem diarização: o texto sai literal, com as hesitações, e sem locutores. Ele não tem limite de duração, então não divide o áudio.
- Requer `ffmpeg`/`ffprobe` no PATH e, para o Gemini, `google-genai` ≥ 2.24. Confira a chave sem exibir o valor.

## Depois de transcrever

1. Trate o texto como a mensagem do usuário e responda ao que ele pediu. Uma instrução falada vale como se tivesse sido digitada.
2. Não cole a transcrição inteira na resposta. Se algo ficou ambíguo ou parece mal transcrito, como um nome próprio ou um número, cite o trecho e confirme antes de agir.
3. Se ele pediu só a transcrição, entregue o texto limpo.
