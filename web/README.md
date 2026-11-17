# NFL Betting Intelligence — Web V1.1

PWA React/Vite estática e responsiva. O frontend lê JSON derivado do catálogo
canônico; não acessa DuckDB, APIs de odds ou segredos no navegador.

## Desenvolvimento reproduzível

Node 22 e o `package-lock.json` versionado:

```bash
cd web
npm ci --no-audit --no-fund
npm test
npm run dev
npm run build
npm run preview
```

`npm test` cobre estado sem odds, filtro mínimo, bloqueio de EV e ordenação por
completude. O build copia `public/data/` para `dist/data/`.

## Contrato de dados

`public/data/slate.json` mantém compatibilidade com a fundação do PR #7.
Cada export também fica em `public/data/snapshots/<source_snapshot_id>/`:

- `metadata.json`: schema, snapshot, hashes, cutoff, publicação, cobertura e limitações;
- `games.json`, `teams.json`, `players.json`;
- `game_analysis.json`: janelas temporada/L5/L3 e defesa por posição;
- `player_props_analysis.json`: distribuições, volume, contexto e evidências;
- `slate.json`: envelope agregado do snapshot.

O exportador é `python -m nfl_betting.web_export --help`. Ele recusa banco
adulterado/ERROR, cutoff sem timezone, pasta de snapshot já existente e dados
indisponíveis no cutoff. Linhas `ANALYTICAL_THRESHOLD_NOT_BOOK_OFFER` não são
mercados reais. `historical_frequency` não é probabilidade prospectiva.

Quotes ausentes não escondem análises. O filtro de odd mínima começa em 1,50 e
só atua sobre registros que realmente possuem preço. O ranking de EV permanece
desabilitado enquanto não houver simultaneamente modelo validado, probabilidade
finita, bookmaker/provider, quote verificada e validade temporal.

## PWA e hospedagem gratuita

Cloudflare Pages Free é o alvo preparado, mas nenhum deploy foi executado:

- root: `web`;
- install: `npm ci --no-audit --no-fund`;
- build: `npm run build`;
- output: `dist`;
- variável obrigatória: nenhuma;
- domínio: subdomínio gratuito `pages.dev`.

`manifest.webmanifest`, ícones SVG, service worker e headers estáticos estão
incluídos. O service worker prioriza a rede para JSON e usa cache somente como
fallback; o snapshot continua identificado na tela. Instalação PWA completa
deve ser revalidada no domínio HTTPS final.

Alternativa GitHub Pages: definir `VITE_BASE_PATH=/nfl-betting-intelligence/`
no build. A publicação não foi ativada e pode exigir configuração humana do
repositório. Nenhum domínio pago, backend ou cartão é necessário.
