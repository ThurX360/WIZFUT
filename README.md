
# FC26 Market Watch — Bot de Oportunidades (Scraper Futwiz)

> **Ideia:** O bot roda offline, consulta o grid do Futwiz periodicamente e envia alertas com oportunidades.
> Ele **não interage com sua conta EA** nem automatiza ações dentro do jogo.
> A cada rodada ele coleta preços, calcula métricas históricas e detecta:
> - **Possível snipe/underpriced** (preço menor que a média histórica)
> - **Possível fake BIN** (queda brusca sem confirmação de volume)
> - **Spike de preço** (movimento forte que pode indicar flip)
> - **Falhas de dados** preenchendo média e desvio automaticamente via histórico local

Ele roda em loop 24/7 (enquanto o processo estiver ativo) e **envia alertas para um Webhook do Discord**.

---

## Como usar (passo a passo)

1) **Instale o Python 3.10+** no seu PC/servidor.

2) **Crie um Webhook no Discord** (Server → Edit Channel → Integrations → Webhooks) e copie a URL.

3) **Configure o bot**
   - Copie `config.example.yaml` para `config.yaml`.
   - Ajuste o bloco `futwiz` (plataforma, páginas e delay entre requisições).
   - Defina os limiares dos detectores se quiser personalizar (`min_discount`, `fake_drop_pct`, etc.).
   - Copie `.env.example` para `.env` e cole sua `DISCORD_WEBHOOK_URL`.
   - Ajuste (se quiser) o bloco `history` para definir janela máxima, pontos e mínimo de amostras.

4) **Instale as dependências**
```bash
pip install -r requirements.txt
```

5) **Execute o bot**
```bash
python main.py
```
O bot vai realizar scraping periódico do Futwiz e enviar alertas quando detectar oportunidades.

---

## Configurações principais

### Bloco `futwiz`
- `platform`: `ps` | `xbox` | `pc`
- `pages`: quantas páginas do grid do Futwiz serão varridas por rodada
- `delay_between_pages`: pausa (segundos) entre cada requisição para evitar bloqueios

### Detectores
- **Underpriced/Snipe:** `price <= avg_24h * (1 - min_discount)` **e** `zscore <= -zscore_min`
- **Fake BIN (suspeita):** queda > `fake_drop_pct` **e** `std_24h` muito baixo **ou** histórico curto; não confirma volume
- **Spike:** `price >= avg_24h * (1 + spike_pct)`

### Histórico inteligente
- Mantemos um **buffer circular em memória** com até `history.max_points` amostras recentes por jogador.
- Quando `avg_price_24h` ou `std_24h` não vêm do Futwiz, eles são recalculados antes da análise.
- Os alertas mostram quantas amostras sustentaram o cálculo (`Hist.: X pts`) para facilitar a confiança.

---

## Atenção (ToS / Risco)
- Respeite os **Termos de Uso** do Futwiz e do EA FC.
- Este projeto é **apenas para análise**. Não automatiza ações dentro do jogo.
- Scraping agressivo pode ser bloqueado. Ajuste `pages`/`delay_between_pages` e o `poll_interval_secs` com cautela.

---

## Estrutura do projeto
```
fc26_market_bot/
  main.py
  requirements.txt
  config.example.yaml
  .env.example
  sources/
    futwiz_scraper.py
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
```

---

## Dúvidas comuns
- **“Quero que rode 24h”:** execute numa VPS ou PC ligado (use `tmux`/`screen`/`pm2`/Docker).
- **“Posso ligar direto no Futwiz?”**: sim, o bot já faz scraping direto no Futwiz (com cautela).
- **“Posso ligar no Futbin/planilhas?”**: o modo CSV foi removido; concentre-se no scraping Futwiz ou adapte sua própria solução externa.

Bons trades! ⚽📈
