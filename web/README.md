# NFL Betting Intelligence — Web V1 (foundation)

Interface React/Vite responsiva, preparada para PWA, sem backend online ou chaves de API no navegador.

## Desenvolvimento

```bash
cd web
npm install
npm run dev
npm run build
```

A aplicação carrega `public/data/slate.json`. O arquivo inicial contém **nenhuma seleção fictícia** e estado `UNAVAILABLE`.

## Contrato de dados

`schema_version`, `status` (READY/PARTIAL/UNAVAILABLE), `season`, `week`, `generated_at_utc`, `source_snapshot_id`, `cutoff_utc`, `games`, `props`, `matchups`.

Cada jogo deve ter `game_id`, `home_team`, `away_team`, `kickoff_utc`. Cada prop deve ter `id`, `game_id`, `player_name`, `team`, `market`, `side`, `line`, `history`, `evidence`, `quote` e `model` com contratos de validação explícitos. O preço exige bookmaker/provider, horário de captura e validade; o EV requer modelo validado e quote verificada, além de controle de cutoff/eligibilidade no exportador antes da publicação. O frontend é somente visualização e NÃO é fonte de autorização financeira.

**Aviso:** não publique feed bruto/licenciado, token de API, dados confidenciais nem probabilidade exploratória como `validated:true`. A exportação segura e a validação estatística serão implementadas em PRs separados.

## Implantação 100% gratuita

Alvo: Cloudflare Pages Free, root `web`, build `npm run build`, output `dist`, subdomínio `pages.dev`. Alternativa: GitHub Pages, com base path a ajustar. Nenhum serviço pago é necessário para a estrutura. Publicação não foi configurada neste PR.

Roadmap e critérios: issue #6. Não fazer merge automático.
