# NFL Betting Intelligence — Web V1.3

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

`npm test` cobre estado sem odds, filtro mínimo, bloqueio de EV, ordenação por
completude e filtro por equipe combinado com os demais controles. O build copia
`public/data/` para `dist/data/`.

## Leitura do dashboard

Os jogos pertencem ao snapshot indicado no topo. Dentro de um confronto, os
segmentos Geral, visitante e mandante usam os códigos exatos das equipes
publicadas. A troca de confronto restaura Geral e preserva os outros filtros.

As barras comparam a frequência observada na temporada, nos últimos 5 e nos
últimos 3 jogos elegíveis, com acertos e tamanho de amostra. No detalhe da prop,
os gráficos comparam mínimo, P25, mediana, P75 e máximo na escala comum da
temporada. O painel também exibe P90, volume e proveniência quando disponíveis.

O topo mostra semana, cutoff e disponibilidade da fonte no horário de Brasília.
O aviso **Desatualizado** aparece a partir de sete dias da coleta. Para snapshots
legados, a referência é o cutoff quando a data da fonte não existe. A data de
publicação local não renova a idade do snapshot. O calendário mantém o status
observado no cutoff. Depois do kickoff, a falta de placar continua desconhecida.
Os contadores separam confrontos com evidência de equipes e com props. A seção
do confronto identifica roster ausente, identidades pendentes e lacunas de
amostra por jogador e mercado.

## Gerar, validar e atualizar localmente

Na raiz do repositório, com o pacote Python instalado, selecione o diretório
que contém `build_manifest.json` e `nfl.duckdb`. O exemplo usa o cutoff congelado
da Semana 11 de 2026, às 20h de São Paulo de 16/11/2026.

```bash
python -m nfl_betting.web_export --database /CAMINHO/BUILD --output web/public/data --season 2026 --week 11 --cutoff 2026-11-16T23:00:00Z
python -m nfl_betting.web_export --validate-export /PASTA/IMPRESSA/NO/DESTINATION
python -m nfl_betting.web_export --output web/public/data --publish-export /PASTA/IMPRESSA/NO/DESTINATION
```

O primeiro comando imprime uma pasta nova em `snapshots/`, identificada por
fonte, versão do schema, temporada, semana e cutoff UTC. A mesma fonte permite
outras rodadas e cutoffs. Uma combinação já arquivada retorna erro. Use outro
`--output` para validação isolada. A validação confere hashes, vínculo entre os
arquivos e o envelope, cutoff das observações, contadores e regras de NO_BET.
O último comando revalida e troca atomicamente o `slate.json` da raiz de
`--output`. Uma publicação concorrente falha ao encontrar
`.slate-publish.lock`. Em caso de encerramento forçado, retire esse lock somente
após conferir que nenhuma publicação está em execução.

### Decisão sobre o exportador

`web_export.py` já produz calendário, análises, envelopes e proveniência para
o React. A alternativa `export_slate.py` em `3c82556` cobre apenas o calendário.
O pipeline oficial incorporou a checagem do nome e vínculo do DuckDB, o
tratamento de kickoff ausente e a troca atômica de `slate.json`. O exportador
alternativo continua na sua branch de origem. Se o catálogo ou as linhas
disponíveis no cutoff faltarem, a geração falha e o React continua lendo o
último JSON presente.

## Contrato de dados

`public/data/slate.json` mantém compatibilidade com a fundação do PR #7.
Cada export da V1.3 fica em uma pasta própria dentro de `public/data/snapshots/`.
O envelope conserva `source_snapshot_id` e aponta para essa pasta em `snapshot_path`.

- `metadata.json`: schema, snapshot, hashes, cutoff, publicação, cobertura e limitações;
- `games.json`, `teams.json`, `players.json`;
- `game_analysis.json`: janelas temporada/L5/L3 e defesa por posição;
- `player_props_analysis.json`: distribuições, volume, contexto e evidências;
- `player_coverage.json`: cobertura por jogador identificado e mercado, com N e motivo da lacuna;
- `slate.json`: envelope agregado do snapshot.

O exportador é `python -m nfl_betting.web_export --help`. Ele recusa banco
adulterado/ERROR, cutoff sem timezone, pasta de snapshot já existente e
calendário indisponível no cutoff. O escopo atual é a temporada regular (REG).
Análises pré-jogo só saem para partidas com kickoff posterior ao cutoff. O
histórico exige fim de jogo no PBP e disponibilidade de cada evidência até
o cutoff. Props exigem associação única do GSIS no roster da rodada e pelo
menos três valores observados por mercado. Históricos em outra equipe usam o
mesmo GSIS, registram a equipe da observação e sinalizam a mudança. Quando
falta o valor do PBP de um jogo elegível, o valor semanal equivalente só é
usado se estiver presente no catálogo. Cada observação registra o campo usado.
Limiares `ANALYTICAL_THRESHOLD_NOT_BOOK_OFFER` e `historical_frequency` são
estatísticas descritivas.

Quotes ausentes não escondem análises. O filtro de odd mínima começa em 1,50 e
só atua sobre registros que realmente possuem preço. O ranking de EV permanece
desabilitado enquanto não houver simultaneamente modelo validado, probabilidade
finita, bookmaker/provider, quote verificada e validade temporal.

### Cobertura real verificada

Catálogo NFLverse congelado `20261116T223853.798034Z-c42926123911446fbeb78d05c1635302`,
estado `PARTIAL`, cutoff `2026-11-16T23:00:00Z`. Exportações e publicação local
validadas em pasta temporária, com os snapshots existentes preservados.

| Semana REG 2026 | Jogos | Agendados no cutoff | Análises de confronto | Jogos com props | Jogadores avaliados | Jogadores com props | Cenários |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 14 | 1 | 1 | 1 | 51 | 28 | 180 |
| 11 | 13 | 13 | 13 | 0 | 0 | 0 | 0 |

A Semana 10 tinha apenas um jogo pré-kickoff. A Semana 11 tinha calendário e
histórico de equipes, mas o roster do catálogo acabava na Semana 10. As duas
exportações têm zero odds verificadas, zero modelos aprovados e `NO_BET`.
O teste offline com props em dois confrontos usa uma fixture sintética.

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
