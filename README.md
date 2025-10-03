
# FC26 Market Watch — Bot de Oportunidades (Futbin/Futwiz feeder)

> **Ideia:** Este bot **NÃO faz scraping** nem loga na sua conta EA.  
> Ele **lê arquivos CSV/JSON exportados** por um *feeder* (por exemplo, o `futbin_crawler`) e analisa o mercado para detectar:
> - **Possível snipe/underpriced** (preço menor que a média histórica)
> - **Possível fake BIN** (queda brusca sem confirmação de volume)
> - **Spike de preço** (movimento forte que pode indicar flip)

Ele roda em loop 24/7 (enquanto o processo estiver ativo) e **envia alertas para um Webhook do Discord**.

---

## Como usar (passo a passo)

1) **Instale o Python 3.10+** no seu PC/servidor.

2) **Crie um Webhook no Discord** (Server → Edit Channel → Integrations → Webhooks) e copie a URL.

3) **Baixe os dados do mercado** com um feeder (recomendado: seu `futbin_crawler`).  
   - Configure o crawler para **salvar um CSV** atualizado com campos semelhantes a:
     - `player_id, name, rating, league, position, price, avg_price_24h, std_24h, updated_at`
   - Coloque o arquivo em `./data/futbin_export.csv` (você pode mudar isso no `config.yaml`).  
   - Se ainda não tiver feeder, teste com nosso arquivo de exemplo em `sample_data/futbin_export.csv`.

4) **Configuração**
   - Copie `config.example.yaml` para `config.yaml` e ajuste caminhos/limiares.
   - Copie `.env.example` para `.env` e cole sua `DISCORD_WEBHOOK_URL`.

5) **Instalar dependências**
```bash
pip install -r requirements.txt
```

6) **Rodar**
```bash
python main.py
```
O bot vai assistir o arquivo (CSV) e enviar alertas quando detectar oportunidades.

---

## Esquema do CSV esperado
Mínimo recomendado de colunas (header):
```
player_id,name,rating,league,position,price,avg_price_24h,std_24h,updated_at
```
- `price` = BIN mínimo atual (inteiro em coins)
- `avg_price_24h` e `std_24h` = média e desvio das últimas 24h (se seu feeder não tiver, o bot constrói histórico e usa rolling)
- `updated_at` = ISO8601 (ex.: `2025-10-03T16:00:00Z`)

> Se seu feeder gera **outros nomes de colunas**, atualize o mapeamento em `sources/futbin_csv.py`.

---

## Regras simples (padrão)
- **Underpriced/Snipe:** `price <= avg_24h * (1 - MIN_DISCOUNT)` **e** `zscore <= -ZSCORE_MIN`  
- **Fake BIN (suspeita):** queda > `FAKE_DROP_PCT` **e** `std_24h` muito baixo **ou** histórico curto; não confirma volume
- **Spike:** `price >= avg_24h * (1 + SPIKE_PCT)`

Você pode editar limiares no `config.yaml`.

---

## Atenção (ToS / Risco)
- Respeite os **Termos de Uso** dos sites (Futbin/Futwiz) e do EA FC.  
- Este projeto é **apenas para análise**. Não automatiza ações dentro do jogo.  
- Scraping agressivo pode ser bloqueado. Use o **feeder oficial** (como seu `futbin_crawler`) com delays.

---

## Estrutura do projeto
```
fc26_market_bot/
  main.py
  requirements.txt
  config.example.yaml
  .env.example
  sources/
    futbin_csv.py
  detectors/
    underpriced.py
    fake_bin.py
    spike.py
  notifier/
    discord_webhook.py
  storage/
    state.py
  utils/
    logging_setup.py
  sample_data/
    futbin_export.csv
```

---

## Dúvidas comuns
- **“Quero que rode 24h”:** execute numa VPS ou PC ligado (use `tmux`/`screen`/`pm2`/Docker).  
- **“Posso ligar direto no Futwiz/Futbin?”**: tecnicamente, sim via scraping, mas pode quebrar e infringir ToS. Use feeder externo.  
- **“Quero Excel/Google Sheets”:** basta exportar do feeder para CSV e apontar o `data_path` para esse arquivo.

Bons trades! ⚽📈
