# AmazonRadio — captura, transcrição e corte de radiojornais

Fluxo: **grava stream nos horários → Whisper transcreve (com tempos) → acha nomes de clientes
→ IA define início/fim da matéria → ffmpeg corta o clipe.**

## Arquivos
- `stations.csv` – 27 emissoras (portal + coluna **stream_url**, a preencher).
- `schedule.csv` – 73 programas/horários (Manaus, UTC-4), vindos da planilha do Drive.
- `clientes.yaml` – clientes e termos que disparam o corte.
- `radio.py` – tudo (plan / daemon / record / transcribe / cut). `find_streams.py` – caça URLs de stream.

## Uso
```
pip install -r requirements.txt ; apt install ffmpeg
export OPENAI_API_KEY=...
python find_streams.py --write   # tenta achar stream_url; confira o que sobrar à mão
python radio.py plan             # janelas de hoje e o que falta
python radio.py daemon           # grava, transcreve e corta sozinho (rodar com systemd/tmux)
```
Saída: `data/clips/<cliente>/*.mp3` e `data/clips.csv` (data/hora, cliente, termo, emissora,
programa, duração, arquivo, texto).

## Pontos de atenção
- **stream_url**: os links da planilha são sites/agregadores, não streams diretos. Sem isso não grava.
  Difusora FM está só no YouTube (usa `yt-dlp`, instale). Rádios do governo/Marinha/Câmara têm stream oficial.
- **Custo**: ~162 h/dia gravadas. Whisper API ≈ US$0,006/min ⇒ ≈ US$58/dia. Para cortar: gravar só
  as emissoras que importam, ou `RADIO_ASR=local` (faster-whisper; precisa de CPU/GPU decente —
  a GTX 750 Ti de 2 GB do servidor atual não serve para modelos grandes).
- **Corte**: com `OPENAI_API_KEY`, gpt-4o-mini decide onde a matéria começa/termina; sem chave
  (ou `RADIO_BOUNDS=gap`) usa silêncio entre falas, que é bem menos preciso em rádio.
- Os clipes são regravados em mp3 96k para o corte ser exato ao quadro (sem depender de keyframe).
- Dados em `data/` (`RADIO_DATA` muda o caminho). Reprocessar: apague o `.json` e rode `transcribe`.
