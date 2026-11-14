# AmazonRadio — captura, transcrição e corte de radiojornais

Fluxo: **grava stream nos horários → Whisper transcreve (com tempos) → acha nomes de clientes
→ IA define início/fim da matéria → ffmpeg corta o clipe.**

## Arquivos
- `stations.csv` – 27 emissoras (portal + coluna **stream_url**, a preencher).
- `schedule.csv` – 73 programas/horários (Manaus, UTC-4), vindos da planilha do Drive.
- `clientes.yaml` – clientes e termos que disparam o corte.
- `radio.py` – tudo (plan / daemon / record / transcribe / cut). `find_streams.py` – caça URLs de stream.

## Uso local (Mac, 100% grátis)
```
brew install ffmpeg ollama ; ollama pull qwen2.5:7b      # LLM local p/ achar início/fim da matéria
pip install -r requirements.txt
export RADIO_LLM=ollama                                  # sem isso e sem chave OpenAI, corta por silêncio (impreciso)
python find_streams.py --write   # tenta achar stream_url; confira o que sobrar à mão
python radio.py plan             # janelas de hoje e o que falta
python radio.py daemon           # grava, transcreve e corta sozinho
```
Variáveis: `RADIO_MODEL` (tiny/base/small/medium; padrão small), `RADIO_KBPS` (padrão 32),
`RADIO_KEEP_DAYS` (padrão 3: apaga o áudio bruto antigo, os clipes ficam), `RADIO_DATA` (pasta de dados),
`RADIO_ASR=openai` (usa a API paga no lugar do Whisper local).

## Onde grava e quanto ocupa
Grava em `amazonradio/data/audio/AAAA-MM-DD/<emissora>_<data>_<hora>.mp3` **na máquina onde o daemon roda**.
mp3 mono: 32 kbps = 14,4 MB/h (padrão) · 64 kbps = 28,8 MB/h.
Os 162 h/dia: **~2,3 GB/dia a 32k** (~70 GB/mês) · ~4,7 GB/dia a 64k (~140 GB/mês). Com `RADIO_KEEP_DAYS=3`
o áudio bruto nunca passa de ~7 GB a 32k; os clipes e a transcrição (.json, pequena) ficam.

## Pontos de atenção
- **stream_url**: os links da planilha são sites, não streams diretos. Sem isso não grava.
  Difusora FM está só no YouTube (`yt-dlp`).
- **Velocidade no Mac**: transcrever 162 h/dia pede muito processamento; comece com poucas emissoras
  (`schedule.csv`) e o modelo `base` ou `small`, e meça. Não medi neste projeto.
- Os clipes são regravados em mp3 96k para o corte ser exato (sem depender de keyframe).
- Reprocessar: apague o `.json` do áudio e rode `transcribe`.
