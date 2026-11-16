# Tarefa 3 — ingestão, reconciliação e banco canônico NFL 2026

Data: 16/11/2026 (America/Sao_Paulo). Base conferida: PRs #1 e #2 abertos, em rascunho e sem merge; branch mais recente `codex/executable-structure-2026-11-16`, commit `f366a9b847edd088505c7f5dcad3caacccf9067a`. Esta etapa usa `codex/canonical-database-2026-11-16` e será encadeada ao PR #2. Nenhuma branch anterior ou histórico foi sobrescrito.

## Parecer e escopo

O primeiro banco canônico de pesquisa foi construído com coleta real NFLverse, 14 tabelas Parquet e catálogo DuckDB portátil. A execução controlada terminou sem erro técnico, mas com estado **PARTIAL** e **2.619 linhas de auditoria pendentes de identidade**. Coleta bem-sucedida não significa identidade completa, informação pré-jogo disponível ou modelo aprovado.

Foram resolvidos por evidência os 89 joins históricos de equipe, os 325 registros de nome/posição e uma atribuição de touchdown após lateral. Os dados e probabilidades históricos permanecem byte a byte; correções aparecem somente no novo banco, com comparação explícita. Não há estratégias, projeções, atualização do Master ou autorização financeira nesta tarefa.

## 1. Fontes, versões e rastreabilidade

Seis loaders reais do `nflreadpy` foram utilizados com cache desativado e instrumentação limitada à sessão do downloader. A origem é a URL efetivamente resolvida pelo loader instalado; não há endpoints novos inventados. O corpo HTTP retornado é preservado em `http/*.body`, com SHA-256. O manifesto registra URL solicitada, URL final sem query de assinatura temporária, status HTTP, ETag/Last-Modified/Date quando retornados, horários por fonte, schema, linhas, semanas, cobertura agregada e hash do Parquet normalizado.

Versões da execução local: Python 3.12.14, nflreadpy 0.1.5, Polars 2.1.0, PyArrow 26.0.1, DuckDB 1.4.3; pytz 2026.6 foi fixado para conversão Python de TIMESTAMPTZ. Dependências completas e hashes estão em `requirements.lock`; instalação do pacote 0.3.0 não resolve dependências adicionais.

| Fonte / arquivo efetivamente obtido em nflverse-data/releases/download | Linhas |
|---|---:|
| schedules/games.parquet (loader filtra 2026) | 272 |
| stats_player/stats_player_week_2026.parquet | 10.376 |
| pbp/play_by_play_2026.parquet | 26.071 |
| snap_counts/snap_counts_2026.parquet | 13.913 |
| weekly_rosters/roster_weekly_2026.parquet | 24.565 |
| injuries/injuries_2026.parquet | 3.168 |

Snapshot da execução de ponta a ponta: `20261116T223417.397919Z-bad6b6c4485f4a3a8e7f08f03e046808`, iniciado às 22:34:17 UTC, 19:34:17 de São Paulo. `reports/task3_2026-11-16/ingestion_manifest.json` preserva os horários exatos, respostas, versões e hashes. O código local estava sobre o commit base, com alterações não commitadas; os SHA-256 de cada módulo/SQL e do lock identificam exatamente os arquivos executados. Não se atribui falsamente a execução a um commit ainda não criado.

`build_manifest.json` registra código do construtor, hashes dos três CSVs históricos utilizados, hash do manifesto bruto, contagem/schema/hash de cada Parquet e hash do catálogo DuckDB. Cada tabela tem `source_snapshot_id` e `available_at`; tabelas factuais incluem índices de linhas de origem. `source_coverage` detalha fonte/escopo/semana/jogo/equipe/jogador; `coverage_audit` detalha todas as equipes/partidas do calendário. Escopos de contagem distinguem linhas de fonte, linhas de equipe no calendário e eventos de papel de jogador, evitando somar essas medidas como se fossem a mesma coisa.

Não houve coleta Sleeper ou Stake nesta etapa. Sleeper ID vem do roster NFLverse quando disponível. A evidência anterior da Stake continua sem cobertura demonstrada de player props/Anytime TD. Licenças/atribuição NFLverse e limites das outras fontes permanecem conforme `DATA_SOURCES.md`.

## 2. Cobertura atual da temporada

Calendário regular: **272 partidas, 32 equipes, W1–W18**. Resultados presentes: **149 partidas**; cada uma tem PBP com marcador `END GAME`, placares consistentes, player stats, snaps e roster para ambas as equipes. Isso certifica presença técnica dessas fontes por jogo/equipe, não todos os atletas elegíveis ou inativos oficiais.

| Semana | Jogos no calendário | Com resultado e cobertura técnica |
|---|---:|---:|
| 1 | 16 | 16 |
| 2 | 16 | 16 |
| 3 | 16 | 16 |
| 4 | 16 | 16 |
| 5 | 15 | 15 |
| 6 | 14 | 14 |
| 7 | 14 | 14 |
| 8 | 14 | 14 |
| 9 | 15 | 15 |
| 10 | 14 | 13 |
| 11–18 | 122 | 0 |

A última semana encerrada com cobertura da rodada é **W9**. **W10 permanece parcial**, faltando o jogo de segunda-feira no snapshot, ainda anterior ao seu kickoff. Calendário futuro não é resultado. O campo `has_result` usa os dois placares presentes no calendário; não é um endpoint de status final oficial. A validação adicional exige fim de jogo no PBP e compara placares. Todas as 544 linhas jogo/equipe estão no CSV de cobertura versionado.

## 3. Tabelas e registros

| Tabela | Linhas | Granularidade / observação |
|---|---:|---|
| games | 272 | Uma partida; kickoff ET convertido para UTC, placares e equipe raw/canônica |
| teams | 32 | Temporada/equipe |
| players | 3.458 | Chaves de identidade; 3.072 GSIS e 386 chaves de origem não resolvidas, não 3.458 pessoas necessariamente distintas |
| player_crosswalk | 24.565 | Temporada/tipo/semana/equipe/GSIS, PFR e Sleeper do roster; preserva ausências |
| player_week | 27.174 | Temporada/tipo/semana/equipe/player_key; inclui bye, status desconhecido, defesa e special teams |
| team_week | 298 | Agregados PBP de equipe/partida; EPA/success rate e contagens |
| offensive_opportunities | 17.445 | Eventos por play/role: targets, corridas e laterais; inclui conversões excluídas e valores raw |
| snap_counts | 13.913 | Jogo/equipe/PFR, GSIS quando resolvido, snaps ofensivos/defensivos/ST separados |
| injuries | 3.168 | Report semanal disponível; horário de publicação individual desconhecido |
| defensive_matchups | 899 | Agregado por jogo/defesa/posição; inclui jardas de laterais, sem fabricar target ao recebedor da lateral |
| ingestion_manifest | 6 | Fonte, captura, origem, hashes/schema/HTTP e código |
| reconciliation_audit | 27.823 | Evidência e classificação, incluindo cada registro histórico examinado |
| coverage_audit | 544 | Duas equipes por partida do calendário, inclusive futuras |
| source_coverage | 55.931 | Fonte/escopo/semana/jogo/equipe/jogador |

Todos os Parquets são exportados do mesmo banco e conferidos por contagem/hashes. `nfl.duckdb` materializa as tabelas, sem depender de caminhos absolutos de views para funcionar após download. `open_database` verifica o hash antes de abrir para leitura. Chaves `PFR:`, `STATS:` e `ROSTER:` indicam identidade pendente, não GSIS inventado; não se unem por nome. As chaves anônimas são locais ao snapshot.

## 4. Reconciliação histórica

### Os 89 registros sem correspondência

Os 89 usam a sigla **LAR**; a fonte atual usa **LA**. A normalização documentada `LAR→LA` resolve todos por `(week, game_id, team, GSIS)`. Os outros 2.635 já correspondiam sem essa alteração. **2.724/2.724 têm targets e carries idênticos ao feed semanal**. Os valores raw e a origem da resolução estão na auditoria; não houve correção de estatística para fazer um join passar.

### Os 325 registros de nome/posição incompletos

Todos encontram roster na mesma temporada/tipo/semana/equipe pelo GSIS: **288 QB, 22 RB, 7 WR, 3 P, 3 OL e 2 DL**. Não foi necessário nome, roster de semana futura ou imputação de posição. A concentração em QB evidencia uma limitação do mapeamento anterior, mas não comprova como seu código ausente foi implementado. O novo banco usa a identidade recebida; as linhas antigas ficam intactas.

### Oportunidades e TD após lateral

Dos 3.273 agregados históricos de oportunidades, **3.272 coincidem integralmente** em contagens, cobertura de yardline, red zone, recepções, jardas e TD após aplicar as regras explícitas. Na implementação do comparador, 247 agregados sem recepções apresentavam null de jardas no PBP versus zero no legado; a regra final atribui zero somente a passes comprovadamente incompletos, preservando `source_yards=null`. São 3.078 eventos incompletos com essa normalização auditada; ausência genérica não vira zero.

A diferença restante é `2026_03_ARI_SF`, GSIS `00-0031408` (Mike Evans), TARGET. O legado registra dois TDs. No play **503**, ele recebe para duas jardas e faz lateral; o marcador em `td_player_id` é `00-0035719`, recebedor da lateral. No play **1079**, Evans marca seu TD. O feed semanal registra **um receiving TD** para Evans. O banco novo usa o marcador por ID e registra a lateral separadamente, sem criar target/recepção para quem recebeu a lateral. A atribuição antiga é compatível com usar `pass_touchdown` indiscriminadamente; como o gerador antigo está ausente, não se afirma essa causa de código como fato.

Os 14 eventos de lateral são preservados. `defensive_matchups` incorpora as jardas de recepção por lateral sem adicionar targets. O histórico continua com o valor original e a comparação detalhada está classificada `HISTORICAL_TD_ATTRIBUTION_RESOLVED`.

### Conversões de dois pontos e outras classificações

O PBP contém **71 jogadas de conversão**: 54 eventos com recebedor, 14 com rusher e três sem ID ofensivo atribuível. Os 68 eventos com ID permanecem em `offensive_opportunities`, classificados como `TWO_POINT_CONVERSION`, fora de targets/carries convencionais. Os três restantes têm evidência de play no audit e permanecem no bruto. Na coorte histórica W1–W9, são **50 targets e sete carries em 57 player-games**, reproduzindo a dimensão do problema documentado nas fases anteriores. Isso não recupera os arquivos anteriores à correção, que continuam ausentes.

Soma convencional observada: **9.352 targets e 8.011 carries**, sem discrepâncias nos **10.366 registros identificados do feed semanal**; os dez registros sem GSIS são preservados, mas não comprovam reconciliação de atleta. Kneels contam como carries; no_play/deleted não contam. O código testa explicitamente essas regras, mesmo quando o feed atual não traz jogador atribuível nas jogadas anuladas.

### Participação histórica

| Evidência anterior | Classificação com fontes atuais | Registros |
|---|---|---:|
| OFFENSE_TOUCH_CONFIRMED | Oportunidades registradas | 2.301 |
| OTHER_STAT_EVENT_NO_OFFENSE_PROOF | Snaps ofensivos, zero targets/carries | 268 |
| OTHER_STAT_EVENT_NO_OFFENSE_PROOF | Somente special teams | 150 |
| OTHER_STAT_EVENT_NO_OFFENSE_PROOF | Participação não confirmada | 1 |
| LISTED_ONLY_NO_EVENT_PROOF | Snaps ofensivos, zero targets/carries | 1 |
| LISTED_ONLY_NO_EVENT_PROOF | Somente special teams | 3 |

As 2.724 comparações estão versionadas em `historical_participation.csv`; não se trataram os 419 eventos sem prova ofensiva como zeros ofensivos indistintamente.

## 5. Divergências resolvidas e pendentes

Resolvidas: alias dos 89 joins; nome/posição dos 325; exclusão convencional de dois pontos; distinção dos zeros com snaps; normalização de incompletos e atribuição do TD após lateral. Três rushes convencionais de punters em **punt formation**, confirmados no PBP/weekly, coexistem com zero snaps ofensivos no provedor de snaps. A auditoria os classifica como `OPPORTUNITY_FROM_PUNT_FORMATION`, preservando a contagem oficial; não elimina essas oportunidades nem reclassifica a fonte de snaps artificialmente.

Pendências de identidade, explicitamente retidas:

- **2.598 linhas de snaps** cujo PFR não aparece no campo PFR dos rosters coletados. São principalmente T/G/C/OL/LS. Não é apenas “mesmo jogador em outra semana”: o PFR não existe no snapshot de rosters inteiro. Existem 6.258 linhas de roster sem PFR. Isso não autoriza unir por nomes parecidos; cada linha permanece com `PFR:<id>`.
- **11 linhas de roster sem GSIS**, com chave de origem e evidência raw.
- **10 linhas semanais sem GSIS/nome/posição**, mantidas como registros anônimos da fonte, sem atribuição a atleta.

Total **2.619 pendências de audit**. São contagens de registros, não de pessoas distintas, nem necessariamente conjuntos disjuntos de atletas. As 2.598 linhas de snaps estão integralmente em `unresolved_snap_ids.csv`. O banco permanece PARTIAL por isso.

## 6. Cobertura e semântica dos snaps

| Semana | Jogos com snaps | Linhas de snaps | Linhas ligadas a GSIS |
|---|---:|---:|---:|
| 1 | 16 | 1.492 | 1.216 |
| 2 | 16 | 1.502 | 1.222 |
| 3 | 16 | 1.494 | 1.216 |
| 4 | 16 | 1.482 | 1.209 |
| 5 | 15 | 1.400 | 1.139 |
| 6 | 14 | 1.301 | 1.060 |
| 7 | 14 | 1.310 | 1.059 |
| 8 | 14 | 1.311 | 1.071 |
| 9 | 15 | 1.401 | 1.135 |
| 10 | 13 | 1.220 | 988 |
| Total | 149 | 13.913 | 11.315 |

No player_week: 2.874 registros com targets/carries; um com lateral sem target/carry; 802 com snaps ofensivos e zero oportunidades, 1.851 com snaps ofensivos mas oportunidades desconhecidas por identidade não resolvida; 2.640 somente ST; 4.045 defesa+ST; 1.714 somente defesa; 13.247 sem participação confirmada. Essa coorte inclui rosters/bye e identidades não unificadas: não é denominador de jogadores ativos nem probabilidade de participação.

Zero oportunidade é computado somente com identidade GSIS conhecida e observação PBP com fim de jogo; sem isso, não vira zero por ausência. Estar no roster não comprova snap. `offensive_snap_share` é o share de snaps retornado pela fonte; **não é routes run, TPRR ou YPRR**.

## 7. Testes e automação

**59 testes offline passaram**, incluindo os 39 anteriores. Cobrem chaves duplicadas, alias, ambiguidade de IDs, equipe/semana/tipo de temporada, calendário, resultado futuro, corte as_of, fim do PBP, snaps, fonte opcional ausente/essencial com falha, hash adulterado, preservação, two-point/no_play/kneel/lateral, captura/restauração do downloader e diagnósticos sem manifest ou com banco parcial. Os exemplos e erros injetados são sintéticos; a execução controlada acima é uma coleta real separada.

Também passaram pip check, verificação SHA-256 histórica e actionlint dos workflows. A coleta local de ponta a ponta retornou exit 0, seis fontes HTTP capturadas, banco PARTIAL e zero erro técnico. Os testes não aprovam os dados ou modelos para uso financeiro.

O workflow semanal agora tenta o banco mesmo após uma ingestão parcial, conserva manifests/brutos/Parquets/DuckDB/auditoria/logs em artefato de 90 dias, publica recibo da tentativa de upload e criação de PR, e deixa falhas visíveis no job. Somente diagnósticos entram em PR automático; o Master e os CSVs legados não são atualizados.

### Validação real do workflow e permissões

Ensaio remoto no commit `13f648651da7dda523a1304ba9214b1ec2b32bce`: [run 43971993500](https://github.com/LeozinSCR/nfl-betting-intelligence/actions/runs/43971993500). A condição temporária de push foi retirada após o ensaio; ficam apenas schedule e workflow_dispatch, sujeitos à integração à branch padrão. O ensaio não fez merge nem alterou configurações de segurança do repositório.

| Etapa observada | Resultado |
|---|---|
| Instalação, pip check e 59 testes | Sucesso |
| Seis fontes em coleta HTTP real | Sucesso |
| Banco e auditoria canônicos | Sucesso técnico, estado PARTIAL com 2.619 pendências |
| Upload de brutos/banco/manifests/logs | Sucesso: artefato 14280045605, 22.814.876 bytes |
| Upload do recibo de permissões | Sucesso: artefato 14279990619 |
| Push da branch de diagnóstico | Sucesso: automation/nflverse-weekly |
| Criação automática de PR | **Bloqueada pela política do GitHub** |
| Resultado final do job | **failure**, corretamente, sem ocultar a falha de publicação |

Erro efetivo: **“GitHub Actions is not permitted to create or approve pull requests.”** O recibo registra `ARTIFACT_OUTCOME=success`, `CANONICAL_OUTCOME=success`, `PR_OUTCOME=failure` e PR_URL vazia. A configuração `pull-requests: write` no YAML não supera essa política. Para liberar a publicação automática, um administrador deve revisar Settings → Actions → General → Workflow permissions → Allow GitHub Actions to create and approve pull requests, conforme as políticas da organização. Essa permissão permanece pendente; o workflow não é declarado plenamente operacional. O PR de código #3 foi aberto separadamente pelo conector autorizado, não pelo bot; nenhum PR automático de diagnóstico foi criado.

Baixei o [bundle real](https://github.com/LeozinSCR/nfl-betting-intelligence/actions/runs/43971993500/artifacts/14280045605) e o [recibo](https://github.com/LeozinSCR/nfl-betting-intelligence/actions/runs/43971993500/artifacts/14279990619), conferi o digest SHA-256 dos ZIPs contra a API, os hashes de cada fonte/corpo HTTP/Parquet, e abri o catálogo baixado em outro caminho. As 14 contagens coincidem com a execução local; os fingerprints dos módulos/SQL/lock também coincidem. O runner usou Python 3.12.16. As comparações de hashes das fontes e os resultados completos estão em `reports/task3_2026-11-16/workflow_validation.json`. Os artefatos expiram em **14/02/2027** segundo a API; arquivar antes disso.

O CI de PR separado [43972105293](https://github.com/LeozinSCR/nfl-betting-intelligence/actions/runs/43972105293) concluiu com sucesso. A falha do ensaio semanal é evidência de uma permissão efetivamente negada, não falha de ingestão ou resultado de modelo. Os testes de falhas/parciais verificam que a mesma rotina preserva diagnósticos sem dado inventado.


## 8. Consulta, armazenamento e limites

Reprodução pela raiz após instalar o lock e o pacote:

```bash
python -m unittest discover -s tests -v
python tools/verify_history.py
# Coleta real + construção em pastas exclusivas, sem tocar o legado:
python -m nfl_betting.canonical --season 2026 --raw-out data/raw_auto --out data/canonical
# Reprocessar exatamente uma coleta existente:
python -m nfl_betting.canonical --snapshot data/raw_auto/2026/SEU_RUN_ID --out data/canonical
```

Consulta a um catálogo materializado:

```python
from nfl_betting.canonical import open_database
with open_database('/caminho/do/run-canonico') as con:
    print(con.sql('select participation, count(*) from player_week group by participation'))
    print(con.sql('select * from reconciliation_audit where severity = \'PENDING\''))
```

A execução controlada local está em `/workspace/scratch/task3-final-controlled/`, com raw e canonical separados. `reports/task3_2026-11-16/evidence_index.json` aponta ao catálogo, hashes e CSVs de revisão. `historical_focus.csv` contém o subconjunto explícito de 415 resoluções (89+325+1); a auditoria **completa de 27.823 linhas** está no Parquet, DuckDB e CSV do run, com hash registrado no manifesto. Não apresentar o recorte como auditoria completa.

Raw/Parquet/DuckDB são ignorados pelo Git; os manifests e evidências revisáveis são versionados. Artefatos de Actions têm retenção de 90 dias, não armazenamento permanente. Local scratch também não é arquivo durável garantido. É necessário arquivar os bundles antes do vencimento e verificar hashes ao movê-los. `open_database` pode verificar o catálogo movido porque não depende de views com caminhos locais.

Limites adicionais: injury reports são semanais, sem data/hora de publicação individual; não certificam inativos oficiais. `available_at` é conservadoramente o término da coleta, nunca a data do evento. `as_of`/`resolve_player` não permitem usar esse snapshot antes de sua captura e não preenchem IDs usando semana futura. Não há snapshots antigos pré-jogo, portanto não se comprova disponibilidade histórica prospectiva destes dados apenas por filtrar week. Defesa por posição não é matchup individual de defensor, ajuste por adversário ou routes.

## 9. Próximas ações para reconstruir modelos

1. Completar a ligação dos PFR ausentes com fonte de IDs autorizada, preservando o vínculo temporal de equipe e os não resolvidos; investigar os 21 registros de origem sem GSIS.
2. Arquivar os snapshots, obter versões realmente pré-jogo de rosters/lesões/inativos e estabelecer um catálogo durável de revisão/publicação. Manter event_time e available_at separados.
3. Recuperar geradores e fontes históricos dos modelos e reproduzir baselines por corte cronológico, usando coorte elegível anterior ao jogo e distinguindo zeros de não participação.
4. Recalcular/avaliar TD e dependências com atribuição correta de lateral, limites matemáticos, tratamento de special teams e validação por mercado. Preservar os resultados negativos e comparar com modelos simples.
5. Só depois executar holdouts futuros e calibração por faixas/intervalos. Preços reais e regras de liquidação continuam necessários para qualquer análise financeira; nenhum modelo foi aprovado por esta entrega.
