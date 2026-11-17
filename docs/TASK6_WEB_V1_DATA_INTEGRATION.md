# Task 6 — V1.1: dados reais, evidências estatísticas e dashboard

Data: 17/11/2026 (America/Sao_Paulo). Base conferida: PR #7 aberto, draft,
sem merge, branch `codex/v1-web-foundation`, SHA
`0383888b22d617ddf18869ae7d42231204887163`. Trabalho isolado em
`codex/v1-1-real-data-dashboard-2026-11-17`, encadeado ao PR #7. Nenhuma branch
anterior, Master, planilha histórica ou aposta foi alterada.

## Parecer executivo

A fundação visual do PR #7 foi transformada em uma PWA estática consultável com
dados NFLverse reais derivados do catálogo DuckDB da Task 3. O navegador não
abre DuckDB, não chama provedores de odds e não recebe credenciais. Um exportador
Python verifica o hash do catálogo, aplica cutoff temporal, calcula janelas de
temporada/últimos cinco/últimos três jogos e grava JSON por snapshot.

O snapshot publicado contém 14 jogos da Semana 10, 36 jogadores ofensivos com
histórico elegível e 142 cenários descritivos de props. Há zero quotes
verificadas, zero probabilidades calibradas e zero EVs publicados. Todos os
registros preservam `decision=NO_BET`. Os limiares alternativos são derivados de
quantis observados e rotulados `ANALYTICAL_THRESHOLD_NOT_BOOK_OFFER`; não são
linhas reais nem recomendações.

## 1. Funcionalidades desenvolvidas

- `nfl_betting.web_export`: exportação exclusiva por `source_snapshot_id`,
  catálogo read-only, hash verificado e cutoff aware.
- JSON separados para metadata, jogos, equipes, jogadores, confrontos e props,
  além de `slate.json` compatível com o contrato iniciado no PR #7.
- Estatística descritiva por linha: N, média, mediana, desvio-padrão amostral,
  P25/P50/P75/P90, mínimo, máximo, valores jogo a jogo, hits e frequência
  observada com semântica explícita de não-probabilidade.
- Volume: targets, receptions, carries, snap share ofensivo e oportunidades de
  red zone/goal line. Routes, TPRR e YPRR ficam null.
- Comparação ofensiva por temporada/L5/L3 e defesa agregada contra RB/WR/TE.
- Linhas alternativas analíticas transparentes para explorar sensibilidade.
- Interface de odds exclusivamente por fixtures em `odds_sources.py`, rejeitando
  odds não finitas, IDs/origem/validade ausentes, indisponibilidade e respostas
  parciais. Nenhum adapter live foi habilitado.
- PWA: manifest, ícones SVG, service worker com network-first para JSON e cache
  como fallback, CSP/headers estáticos e ausência de backend.

## 2. Telas implementadas

### Inicial híbrida

Mostra rodada, 14 jogos, horário em America/Sao_Paulo, estado no cutoff e acesso
ao confronto. Abaixo, mantém o scanner estatístico visível mesmo sem odds. Há
filtros por posição, mercado, busca, odd mínima iniciando em 1,50 e opção
“somente com odds”. O mínimo só atua em registros realmente cotados; ausência
de preço não apaga a análise descritiva.

A ordenação padrão usa somente completude da evidência, nunca hit rate como
probabilidade. Ordenação por EV fica desabilitada sem modelo validado e quote
verificada/temporalmente válida.

### Confronto

Mostra temporada/L5/L3 para EPA/play, Success Rate, jogadas, passes, corridas e
dropbacks disponíveis no catálogo; defesa por posição; props vinculadas ao
jogo; e lacunas de QB/inativos. Partidas já encerradas não recebem uma análise
pré-jogo reconstruída retroativamente. EPA/dropback, EPA/rush e pace ficam
explicitamente indisponíveis, pois o catálogo atual não os materializa.

### Prop e Anytime TD

Cada card identifica jogador, time, adversário, posição, mercado e limiar;
distribuições nas três janelas; volume; red zone/goal line; contexto defensivo;
evidências favoráveis e contrárias; completude; disponibilidade não verificada;
ausência de preço; e `NO_BET`. Anytime TD usa TD observado e oportunidades de
campo curto, sem transformar frequência passada em probabilidade de TD.

Validação visual real em Chromium confirmou home e confronto no viewport
desktop, carregamento dos 14 jogos/142 cenários, estado sem odds e proveniência.
O DevTools do navegador gerenciado bloqueou emulação mobile; responsividade foi
verificada por regras CSS nos breakpoints 900/680 px, build e navegação fixa. A
revalidação em aparelhos reais/HTTPS permanece antes de chamar a PWA publicada.

## 3. Fontes reais utilizadas

Snapshot canônico Task 3:
`20261116T223417.397919Z-bad6b6c4485f4a3a8e7f08f03e046808`.
Build PARTIAL, banco SHA-256
`868d8e2429674b5f0ac697a438b69869220661859df3e4be02e4649e87e8a046`.
Cutoff do export: `2026-11-16T23:00:00+00:00` (20h de São Paulo), anterior ao
kickoff LAC@BAL. A fonte foi coletada às 22:34 UTC; o export nunca antecipa seu
`available_at`. Os 2.619 registros de auditoria de identidade pendentes seguem
preservados.

Tabelas efetivamente lidas: `games`, `teams`, `team_week`, `player_week`,
`offensive_opportunities` e `defensive_matchups`. `injuries` não é publicado
como inativo, pois não tem timestamp individual confiável. Weekly roster não é
prova de elegibilidade ou titularidade.

NFLverse permanece sujeito às atribuições/licenças por dataset documentadas em
`DATA_SOURCES.md`. Nenhum raw NFLverse ou DuckDB foi colocado no frontend.

## 4. Quantidade carregada

| Artefato | Registros |
|---|---:|
| Jogos da Semana 10 | 14 |
| Jogos finais no cutoff | 13 |
| Jogos futuros analisáveis no cutoff | 1 |
| Equipes no catálogo | 32 |
| Jogadores ofensivos exportados | 36 |
| Cenários de props/TD | 142 |
| Quotes verificadas | 0 |
| Modelos probabilísticos aprovados | 0 |

O número de cenários é maior que o de jogadores porque uma distribuição pode
produzir até três limiares derivados de P25/P50/P75. Isso não representa 142
mercados disponíveis.

## 5. Métricas efetivamente calculadas

Por jogador/linha: N, média, mediana, desvio-padrão amostral, P25/P50/P75/P90,
mínimo, máximo, sequência observada e hits em temporada/L5/L3; targets,
receptions, carries, offensive snap share, red-zone/goal-line opportunities e
TDs ofensivos. `offensive_snap_share` não é routes run.

Por equipe: EPA/play e Success Rate ponderados por observações; jogadas,
tentativas de passe, corridas e dropbacks por jogo nas três janelas. Por defesa:
targets, recepções e jardas recebidas por jogo com evento de RB/WR/TE. Esse
agregado não é matchup individual, ajuste de adversário ou causalidade.

O `evidence_completeness_score` mede N/recência/cobertura de snap e só ordena
qualidade dos dados. Não é edge, previsão, probabilidade ou aprovação.

## 6. Testes executados

- Baseline antes das alterações: 82/82 testes Python e preservação histórica OK.
- Suíte ampliada: 91 testes Python, incluindo export/schema, imutabilidade,
  cutoff, janelas, distribuição, linhas alternativas, odds inválidas, resposta
  parcial, zero quotes e `NO_BET`.
- Frontend: quatro testes Node para estado sem odds, filtro mínimo, gate de EV e
  ordenação por completude.
- `npm ci`, `npm test` e `npm run build` com Node 22 e lockfile.
- `pip check`, `compileall`, `tools/verify_history.py` e workflow lint.

Os números finais são registrados após a execução completa desta branch; testes
de fixtures não comprovam cobertura de provedores reais.

## 7. Limitações do modelo e dos dados

- Não existe modelo probabilístico aprovado, calibração por mercado ou registro
  de promoção. Frequência histórica permanece descritiva.
- Snapshot é congelado e PARTIAL; não é feed ao vivo. Somente um jogo da rodada
  ainda era futuro no cutoff.
- Inativos oficiais, titulares, mudanças de QB, OL, clima, pressure rate,
  routes/TPRR/YPRR, EPA/dropback, EPA/rush e pace não estão integrados.
- Candidatos usam identidade GSIS exata e time atual; nenhum match por nome.
- Elegibilidade oficial fica `UNVERIFIED`; roster semanal não a substitui.
- Limiares são cenários analíticos. Sem preço real não existe comparação
  financeira ou recomendação de linha.
- O service worker não torna um snapshot novo “atual”; apenas oferece fallback
  do último JSON identificado que o navegador já carregou.

## 8. Situação das APIs gratuitas

Revisão pública em 17/11/2026, sem cadastro, chave, compra ou chamada de odds:

| Fonte | Evidência pública | Decisão Task 6 |
|---|---|---|
| PropLine | Free anunciado como US$0 contínuo, 1.000 req/dia, props NFL; termos permitem valores individuais em produto, proíbem bulk/espelhamento e chave exige cadastro | Interface candidata; não habilitada sem amostra real, binding GSIS/evento, secrets no CI e revisão de redistribuição |
| ParlayAPI | Free 1.000 créditos/mês sem cartão e endpoint NFL props documentado | Rejeitada para site público: termos atuais limitam free a avaliação pessoal e exigem acordo escrito para exibição pública/derivados |
| The Odds API | Free 500 créditos/mês, chave por cadastro, props NFL/event endpoint documentados; histórico pago | Candidata somente a fixture/adaptador futuro; nenhuma chave ou resposta real nesta tarefa |
| FanLine Wire | Free permanente sem cartão, 100 REST/dia e demo pública; alega board NFL/props FanDuel | Não habilitada: termos proíbem compartilhar/revender feed e direitos de exibição pública não ficaram suficientemente claros |
| Stake | Evidência anterior: endpoint público retornou jogos/mercados de equipes, sem player props/Anytime TD demonstrados | Mantida como não integrada para props; não inventar endpoint ou validade |

Fontes públicas: [PropLine pricing](https://prop-line.com/pricing),
[PropLine terms](https://prop-line.com/terms),
[ParlayAPI docs](https://parlay-api.com/docs),
[ParlayAPI terms](https://parlay-api.com/terms),
[The Odds API](https://the-odds-api.com/),
[FanLine Wire](https://fanlinewire.com/),
[FanLine Wire terms](https://fanlinewire.com/terms).

`odds_sources.PROVIDERS` mantém todos os adapters `live_enabled=False`. Se uma
chave gratuita for autorizada no futuro, deverá ficar em GitHub Secret e o
workflow deverá falhar para estado sem configuração sem expor o valor. Nenhum
feed bruto será publicado quando os termos não permitirem.

## 9. Situação da hospedagem

O build está preparado para Cloudflare Pages: root `web`, `npm ci`, `npm run
build`, output `dist`, sem variável ou backend. A documentação oficial do plano
Free registra 500 builds/mês, 20.000 arquivos/site e 25 MiB por asset; o pacote
atual fica muito abaixo desses limites. Requests de assets estáticos não usam
Pages Functions. Fonte: [Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits/).

Nenhum projeto Cloudflare, conta, domínio ou deploy foi criado. Portanto o site
está **deploy-ready**, não publicado. A instalação PWA e CSP precisam ser
testadas novamente no `pages.dev` HTTPS final.

GitHub Pages é fallback técnico com `VITE_BASE_PATH=/nfl-betting-intelligence/`,
mas a política de Pages não é adequada a todo uso comercial/SaaS e deve ser
revista antes da ativação. Fonte: [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits).

## 10. Próximas prioridades do Issue #6

1. Capturar snapshots realmente pré-jogo de inativos, QB/depth e odds com
   autorização de exibição pública, IDs canônicos, timestamp e expiry.
2. Materializar EPA/dropback, EPA/rush e pace a partir do PBP com testes de
   cutoff; continuar deixando indisponíveis pressure/routes sem fonte.
3. Avaliar uma única API gratuita com chave em ambiente isolado e fixture real,
   respeitando quota/termos; não ativar ParlayAPI para o site público sem licença.
4. Definir coorte/targets e executar backtest walk-forward, calibração e CIs por
   mercado/posição antes de habilitar probabilidade ou EV.
5. Após revisão humana, configurar Cloudflare Pages Free e validar PWA, CSP,
   acessibilidade/mobile e rollback no domínio gratuito, sem cartão ou upgrade.

O resultado desta tarefa é um dashboard estatístico auditável e útil, não um
sistema validado de apostas. Nenhuma ordem, aposta, merge ou gasto foi realizado.
