# NFL Betting Intelligence — auditoria inicial do Codex

Data: 16/11/2026 (America/Sao_Paulo). Repositório: [LeozinSCR/nfl-betting-intelligence](https://github.com/LeozinSCR/nfl-betting-intelligence).

Commit de referência: `a4022fafd2e93d4465800e12757e5798ef8b269a`, único commit disponível, mensagem `Add files via upload`. Branch encontrada: `main`; `origin/HEAD` aponta para `main`. Branch desta entrega: `codex/initial-audit-2026-11-16`.

## Parecer executivo

**O material constitui uma migração de pesquisa, sem aprovação para recomendações financeiras automáticas.** Os artefatos existem e o pacote tem integridade verificável, mas o repositório publicado contém somente `NFL_Codex_GitHub_Migration_Starter.zip`. Código, testes, README e workflow estão dentro do ZIP, não nos caminhos executáveis do checkout. As 33 fases são contexto documental; o histórico Git não contém seus commits ou seus scripts de modelagem.

O Master mais recente é `legacy/NFL_Master_Phase33_Audited.xlsx`, com 22 abas e snapshot declarado de 14/11/2026. O histórico local cobre W1–W9, com apenas WAS–NYG em W10 nos agregados e oportunidades. Os quatro testes do pacote passam após extração. Confirmei uma violação de limites de probabilidade conjunta e ganhos pequenos/mistos dos modelos. Não há prova de rentabilidade, calibração prospectiva ou atualização persistente do Master.

Uma sondagem independente, sem substituir o histórico, conseguiu executar o coletor NFLverse nas seis fontes, inclusive snaps e lesões. O feed retornou W10 parcial (13 de 14 partidas com placar/PBP). A API pública da Stake respondeu a consultas reais e forneceu 14 partidas e 498 seleções de mercados de equipes; **nenhuma player prop nem Anytime TD foi observada nesse snapshot**. Isso comprova conectividade pontual, sem comprovar cobertura dos mercados desejados ou integração operacional.

Escopo desta entrega: documentação e evidências; ZIP e valores históricos preservados. Nenhuma aposta foi criada, nenhum modelo promovido e nenhuma automação ativada.

## 1. Inventário e método

O workspace inicial não tinha checkout Git utilizável. Localizei o repositório pelo conector GitHub, confirmei metadados e refs remotas e clonei a URL pública. Não encontrei `AGENTS.md`. Li integralmente `README.md`, `docs/CODEX_HANDOFF.md`, as demais configurações/documentações e todos os módulos Python do pacote. Inspecionei os 14 CSVs, as duas planilhas e o relatório W10.

### Estrutura completa anterior à auditoria

```text
nfl-betting-intelligence/
└── NFL_Codex_GitHub_Migration_Starter.zip  (1.344.210 bytes)
```

`.git/` é metadado local. Não havia arquivos soltos de aplicação, testes ou workflow. A auditoria acrescenta apenas `docs/CODEX_INITIAL_AUDIT.md` e `docs/CODEX_INITIAL_AUDIT_EVIDENCE.json`.

### Conteúdo completo do ZIP (30 arquivos)

```text
.github/workflows/weekly_refresh.yml
.gitignore
README.md
requirements.txt
docs/CODEX_HANDOFF.md
docs/DATA_SOURCES.md
docs/FILE_MANIFEST.json
src/__init__.py
src/nfl_betting/__init__.py
src/nfl_betting/ingest_nflverse.py
src/nfl_betting/rules.py
tests/test_rules.py
tools/stake_odds.py
tools/STAKE_CONNECTOR_README.md
legacy/NFL_Master_Phase33_Audited.xlsx
legacy/NFL_Phase32_Master.xlsx
reports/W10_206_selections.md
data/processed/calibration_summary.csv
data/processed/defense_position_corrected_2026.csv
data/processed/opportunities_corrected_2026.csv
data/processed/parlay_comparison.csv
data/processed/targets_walkforward_w8w9.csv
data/processed/td_backtest.csv
data/processed/td_comparison.csv
data/processed/team_week_corrected_2026.csv
data/processed/weekly_participation_2026.csv
data/processed/weekly_reconciliation_2026.csv
data/reference/W10_TD_audit.csv
data/reference/W10_player_props_audit.csv
data/reference/W10_props_market.csv
```

Extração de inspeção: `/workspace/scratch/nfl-initial-audit`, fora do checkout, após verificar que os caminhos do ZIP não escapavam do destino. Os 29 arquivos listados em `FILE_MANIFEST.json` conferem em tamanho e SHA-256; o manifesto não lista a si próprio. O JSON de evidências desta entrega registra os 30 arquivos, hashes, schemas, contagens, dependências e sondagens externas. Checksum prova integridade do pacote, não veracidade estatística.

### Masters e arquivos históricos

Phase33 (625.270 bytes) é o Master mais recente pela fase e changelog interno, não pelo timestamp de download. Phase32 (612.876 bytes) preserva o estágio anterior, com 16 abas. Phase33 contém as 16 abas anteriores mais seis abas de auditoria:

| Aba Phase33 | Linhas após cabeçalho |
|---|---:|
| TEAM_WEEK | 274 |
| DEF_VS_POSITION | 274 |
| PLAYER_PARTICIPATION | 2.724 |
| PLAYER_USAGE | 529 |
| TARGET_BACKTEST | 409 |
| TD_BACKTEST | 480 |
| PARLAY_BACKTEST | 218 |
| CALIBRATION | 28 |
| TD_PROJECTIONS | 438 |
| SOURCE_RECON | 2.724 |
| START_HERE | 28 |
| MODEL_REGISTRY | 5 |
| QA | 16 |
| STAKE_QUOTES | 50 |
| BET_LOG | 1 |
| SOURCES | 13 |
| P33_QA_FINAL | 20 |
| P33_JOINT_BOUNDS | 1 |
| P33_STAKE_AUDIT | 25 |
| P33_WEEKLY_SOP | 9 |
| P33_RELEASE_MATRIX | 9 |
| P33_CHANGELOG | 5 |

Contagens incluem linhas vazias/modelos de preenchimento. As 50 linhas de `STAKE_QUOTES` não representam 50 cotações verificadas: são formulário sem preços preenchidos. `BET_LOG` contém um registro legado de perda, odd 8,6 e valor financeiro ausente; não foi revalidado externamente e não permite calcular ROI. Watchlists W10 não são apostas executadas.

## 2. Arquitetura atual e dependências

Há três componentes de código, independentes:

1. `ingest_nflverse.py`: CLI que chama `nflreadpy`, grava seis Parquets e manifesto com linhas, colunas, hash, caminho e instante UTC; retorna código 2 se alguma fonte falhar.
2. `rules.py`: validadores estruturais de parlays, probabilidade implícita e cálculo de EV condicionado a dois booleanos de autorização lógica.
3. `tools/stake_odds.py`: CLI somente leitura, descoberta de esporte/torneio/partidas, snapshot JSON e normalização de `offers/selections` para CSV.

O fluxo histórico é uploads externos → derivados CSV/Excel → resultados de pesquisa e relatório Markdown. **Não foram encontrados scripts de transformação/reconciliação, treinamento, previsão, xTD, calibração, simulação ou geração do relatório W10.** A planilha conserva resultados e fórmulas operacionais, não a implementação reprodutível dos modelos.

`requirements.txt`: `nflreadpy>=0.1`, `polars>=1.0`, `pyarrow>=15.0`. Não há lockfile, `pyproject.toml`, pacote instalável, configuração de banco, container ou CLI unificada. Python 3.12 é usado no workflow. Nesta auditoria a instalação em diretório isolado funcionou com nflreadpy 0.1.5, Polars 2.1.0, PyArrow 26.0.1; openpyxl 3.1.5 foi instalado somente para inspeção dos XLSX. Versões completas constam no JSON. Não confundir instalação bem-sucedida com ambiente futuro reproduzível.

O workflow do ZIP agenda terça-feira 13:00 UTC (10h de São Paulo), executa testes/coleta e propõe PR com manifesto. Enquanto encapsulado no ZIP, **não é um workflow descoberto por GitHub Actions**. O estado `CONFIGURED/SCHEDULED` no Excel descreve intenção/histórico externo; não comprova execução no GitHub.

## 3. Fontes implementadas, sondadas e pendentes

Sondagens realizadas em 16/11/2026, aproximadamente 18h26 de São Paulo. Os horários exatos UTC estão no JSON/manifestos. São consultas de auditoria, sem atualização dos CSVs ou do Master versionados.

| Fonte | Implementação existente | Evidência desta sessão | Pendência |
|---|---|---|---|
| NFLverse/nflreadpy | Seis loaders na CLI | Todas as fontes retornaram dados e Parquet; exit 0 | Contratos, IDs, qualidade, disponibilidade por jogo, persistência e integração com modelos |
| Sleeper | Somente URL/documentação | GET `/v1/players/nfl`: HTTP 200, 12.229 registros, 14.663.727 bytes | Adaptador, snapshot diário, crosswalk e validação de status; cadastro não prova ativo no jogo |
| NFL oficial | Referência de consulta | Página de termos respondeu HTTP 200 | Sem coletor de injury reports, inativos, depth charts ou resultados oficiais; sem validação individual nesta auditoria |
| Stake | Protótipo read-only | Três chamadas de dados bem-sucedidas no total; detalhes na seção 8 | Player props, TD, normalização tipada, freshness, cotação combinada e contratos |
| Outras casas | Nenhum adaptador | Documentação de The Odds API localizada | Acesso autenticado, licença/plano e resposta real ainda não testados |

### Resultado do coletor NFLverse

| Fonte | Linhas retornadas | Cobertura indicada |
|---|---:|---|
| schedules | 272 | Temporada regular W1–W18; agenda futura não é resultado |
| player_stats | 10.376 | W1–W10 |
| pbp | 26.071 | W1–W10; jogos de 09/09 a 15/11/2026 |
| snap_counts | 13.913 | W1–W10; campos ofensivos, defensivos e special teams separados |
| injuries | 3.168 | W1–W10; sem timestamp de publicação individual no schema retornado |
| rosters_weekly | 24.565 | W1–W10; inclui GSIS/PFR/Sleeper IDs |

Os loaders e suas assinaturas funcionaram com as versões instaladas. Ter linhas em todas as semanas não comprova cobertura completa por time/jogador. O calendário retornou 14 jogos W10, 13 com placar; o PBP tem 13 jogos W10. Falta o jogo de segunda-feira no retrato de resultados, e não há W11 observada. A fonte de snaps está acessível nesta sessão, embora ausente no histórico do Master. Routes run não foram obtidas.

Comparei os 2.724 registros históricos reconciliados com `player_stats` novo por `(week, game_id, team, player_id)`: 2.635 correspondências, sem divergência de targets/carries nessas correspondências; 89 sem correspondência devem ser investigados. Não substituir esses 89 por zeros nem inferir que todas as variáveis foram reconciliadas.

### Documentação e termos

- [NFLverse](https://github.com/nflverse) e [licença](https://github.com/nflverse/nflverse-data/blob/main/LICENSE.md): maioria dos dados CC-BY 4.0; FTN tem condições específicas (CC-BY-SA 4.0). A licença do código nflreadpy é MIT, distinta da dos dados. Exigir atribuição e conferência por dataset.
- [nflreadpy API](https://nflreadpy.nflverse.com/api/load_functions/): documentação acessível; coletor não registra URL resolvida, versão do loader e data de revisão de cada fonte no manifesto.
- [Sleeper](https://docs.sleeper.com/): API read-only sem token, gratuita para uso não comercial; uso comercial depende de licença própria. A documentação recomenda cache do cadastro e consulta no máximo diária. O acesso direto à página de docs recebeu 403 nesta sessão, mas foi possível consultar sua documentação via ferramenta de busca; o endpoint de dados respondeu 200.
- [NFL termos](https://www.nfl.com/legal/terms): restringem recuperação sistemática de conteúdo sem consentimento e uso comercial; não implementei scraping nem presumi licença de redistribuição. Integração oficial precisa de mecanismo permitido/licenciado; leitura pública não basta.
- [Stake API](https://sportsbook-api.stake.com/): documentação consultada via busca indica 4 requisições/hora sem chave. Página raiz direta recebeu 403, enquanto os endpoints de dados responderam. Não houve contorno de login/bloqueio nem uso de conta pessoal. Acesso pontual não estabelece SLA ou licença ampla de redistribuição.
- [The Odds API V4](https://the-odds-api.com/liveapi/guides/v4/): candidata para props e linhas alternativas por evento, com bookmaker e `last_update`; histórico depende do plano. Não houve chave, compra ou consulta de odds autenticada. Preço de outra casa deve manter sua identificação e jamais ser renomeado como preço Stake.

## 4. Última semana efetivamente coberta

**Artefatos do projeto: W9 é a última semana com cobertura semanal consolidada; W10 é parcial.** A contagem de times por semana em `team_week_corrected_2026.csv` é 32, 32, 32, 32, 30, 28, 28, 28, 30 e 2. W1–W9 somam 272 linhas de equipes, correspondentes a 136 partidas segundo a estrutura e o calendário consultado. Os agregados abrangem as 32 equipes.

| Arquivo | Linhas | Semanas |
|---|---:|---|
| team_week_corrected_2026.csv | 274 | W1–W9 + 2 equipes W10 |
| defense_position_corrected_2026.csv | 274 | W1–W9 + W10 parcial |
| opportunities_corrected_2026.csv | 3.273 | W1–W9 + 21 linhas W10 de `2026_10_WAS_NYG` |
| weekly_participation_2026.csv | 2.724 | W1–W9 |
| weekly_reconciliation_2026.csv | 2.724 | W1–W9 |
| targets_walkforward_w8w9.csv | 409 | W8–W9 |
| td_backtest.csv | 1.549 | W4–W9; modelo antigo distinto do holdout xTD |
| W10_player_props_audit.csv | 102 | Shortlist exploratória baseada em W1–W9 |
| W10_TD_audit.csv | 104 | Shortlist exploratória baseada em W1–W9 |
| W10_props_market.csv | 23 | Referências de recepções, explicitamente NOT_STAKE |

O relatório de 206 seleções é análise, não cobertura de resultados W10. Os dados novos da sondagem ficaram em scratch, separados dos artefatos versionados. Não se declara que o projeto foi atualizado para W10 completa.

## 5. Modelos e auditoria estatística

Menor Brier/Log Loss é melhor. Diferencio métricas recalculadas das previsões congeladas de reprodução do treinamento, que não é possível com os scripts disponíveis.

| Modelo/amostra | Baseline → alternativa | Resultado e decisão |
|---|---|---|
| Targets W8–W9, n=409 | MAE positivo 1,84434; com touches 1,82722; todos os registros 1,80114 | MAEs recalculados; inclusão de zeros melhora modestamente; pesquisa |
| TD antigo W4–W9, n=1.549 | Poisson Brier 0,155229 / LL 0,486659; Gamma-Poisson 0,155397 / LL 0,487275 | Recalculado do CSV; Gamma-Poisson não melhora esses totais; não comparar diretamente com n=480 |
| Anytime TD W8–W9, n=480 | Brier 0,170388 → 0,172151; LL 0,525106 → 0,524243 | Recalculado do Master e consistente com resumos; pior Brier, leve melhora de LL; não promover xTD |
| Props de referência, n=1.898 | Brier 0,173539 → 0,171316; LL 0,529052 → 0,515683 | Ganho registrado nos resumos; faltam previsões individuais completas e gerador no pacote para recomputar integralmente |
| Parlay 2 props W8–W9, n=218 | Brier 0,238128 → 0,238554; LL 0,672965 → 0,673295 | Recalculado do Master; ajuste de dependência piora o total e tem uma probabilidade inválida |
| Parlay 2 TDs, n=87 | Brier 0,120650 → 0,120482; LL 0,397581 → 0,397299 | Ganho ínfimo nos resumos; sem prova suficiente para promoção |

Ganhos por segmento são heterogêneos: xTD melhora WR (Brier 0,184602 → 0,180313), mas piora RB e TE. Props de jardas recebidas de RB apresentam probabilidade média alternativa 0,64766 versus taxa observada 0,39850; isso é um sinal forte de descalibração agregada, não um diagnóstico completo por faixa. `calibration_summary.csv` segmenta por mercado/posição, **não fornece curva de confiabilidade por intervalos de probabilidade**, nem calibrador ajustado fora da amostra. Gap médio pequeno não prova calibração.

Diagnóstico adicional desta auditoria: bootstrap pareado por partida, 5.000 reamostragens, seed 20261116, 29 clusters W8–W9. Para ΔBrier = alternativa − baseline, IC percentil 95% do TD é [-0,004211; 0,007747] (estimativa +0,001763); parlay é [-0,002315; 0,003131] (estimativa +0,000426). Ambos incluem zero. É diagnóstico das previsões congeladas: não refaz treinamento, não resolve dependência temporal/equipes compartilhadas e não substitui validação prospectiva. Método e valores estão no JSON de evidências.

### Falha matemática confirmada

`PARLAY_BACKTEST!N207`, jogo `2026_08_ATL_TB`, Bucky Irving carries + Ko Kieft receptions:

- P(A) = 0,9792964888420533; P(B) = 0,00000000025331716052168143.
- P(A∩B) registrada = 0,000009680823682207268, maior que P(B).
- Deve valer `max(0, P(A)+P(B)-1) <= P(A∩B) <= min(P(A), P(B))`.

Reconfirmei uma violação em 218 pares, já documentada em `P33_JOINT_BOUNDS`. Preservar a previsão histórica; truncar para o limite serve como diagnóstico, não como correção validada do modelo. O código gerador ausente impede corrigir a fórmula nesta entrega. Um teste com pares não valida uma combinada de oito ou mais legs; essa extensão precisa de modelagem conjunta e avaliação próprias.

### Seleção, zeros, snaps e vazamento

Todos os 409 registros de targets têm `eligible_current_record_only=YES`; 48 têm zero targets observados. Selecionar retrospectivamente quem teve registro na semana de avaliação cria risco de viés de participação. As 2.724 linhas de participação dividem-se em 2.301 `OFFENSE_TOUCH_CONFIRMED`, 419 `OTHER_STAT_EVENT_NO_OFFENSE_PROOF` e 4 `LISTED_ONLY_NO_EVENT_PROOF`. Não equiparar essas duas últimas categorias a snaps ofensivos positivos ou a inatividade.

As 529 linhas de `PLAYER_USAGE` não têm valores verificados em `snap_share`, `routes_per_game`, `tprr` e `yprr`. Snaps novos possuem PFR ID; modelos usam GSIS ID: o crosswalk precisa ser explícito e temporal. Não preencher routes com snaps. Os holdouts são rotulados cronologicamente, mas, sem geradores e snapshots pré-jogo, não é possível provar ausência de leakage, incluindo lesões, mudanças de time e seleção de jogadores pós-jogo.

As faixas de 80% do piloto W10 são descritas no próprio relatório como incerteza paramétrica, não intervalo preditivo completo. Não encontrei MAE reprodutível de jardas, avaliação de clima/pressão/OL/alinhamento, resultados prospectivos com odds verificadas, CLV ou série financeira apta a demonstrar lucro.

## 6. Problemas de código, dados e referências

| Prioridade | Evidência | Consequência |
|---|---|---|
| P0 | Apenas ZIP no checkout | Instalação/testes por README falham na raiz; workflow inativo |
| P0 | Violação Fréchet no Master | Probabilidade conjunta inválida; bloquear promoção |
| P0 | Geradores e fontes brutas históricos ausentes | Backtests não reproduzíveis desde a origem; sem garantia de ausência de leakage |
| P0 | Elegibilidade e preço apoiados em campos/booleanos do chamador | Aceitação estrutural não é autorização financeira |
| P1 | `P33_QA_FINAL` marca PASS para 50 targets e 7 carries divergentes, com critério zero | Sumário contradiz dados: SOURCE_RECON e CSV têm todos os deltas zero; histórico de 57 correções não pode ser refeito sem original |
| P1 | `MODEL_REGISTRY` registra MAE de targets sob cabeçalhos Brier | Comparação/automação por coluna pode interpretar métrica errada |
| P1 | 325/3.273 linhas de oportunidades têm posição UNKNOWN e nome vazio | DVP/identidade incompletos; não excluir silenciosamente nem atribuir posição por palpite |
| P1 | Referências sem arquivos originais | `NFL_historical_sources_2026.zip`, `play_by_play_2026.xlsx/.parquet`, `stats_player_week_2026.xlsx` não estão no pacote |
| P1 | `SOURCES` cita nomes de fases anteriores ausentes | Alguns têm derivados renomeados ou abas correspondentes; não presumir equivalência integral ou que CSV faltante seja recuperável da aba |
| P1 | README diz relatório W10 em legacy | Arquivo está em `reports/W10_206_selections.md` |
| P1 | Coletor sem validação de cobertura/chaves | Dataset não vazio recebe OK mesmo incompleto; não comprova rodada encerrada |
| P1 | Snapshot com precisão de segundos e `exist_ok=True` | Duas execuções no mesmo segundo podem sobrescrever; imutabilidade declarada não é garantida |
| P1 | Manifesto sem URL efetiva, revisão, versões e tempo do evento | `fetched_at_utc` é início da execução, não publicação da fonte nem cutoff de previsão |
| P1 | Coleta parcial falha e workflow interrompe etapas seguintes | Sem `if: always()`, upload do diagnóstico e PR de falha não são garantidos; raw pode ser perdido |
| P1 | Artefatos de Actions por somente 7 dias | Insuficiente para histórico de auditoria; manifesto referencia caminho local do runner |
| P2 | Dependências abertas e sem testes de integração | Próxima resolução pode mudar comportamento; não há teste de schema/HTTP/paginação |
| P2 | Protótipo Stake aceita preços string e não finitos sem validação forte | CSV requer normalização tipada e rejeição de odds inválidas |

`STAKE_CONNECTOR_README` manda executar `python stake_odds.py` sem indicar `cd tools`; da raiz o caminho correto é `python tools/stake_odds.py`. A fonte `fieldworklines.com` das 23 linhas de referência não foi revalidada; não representa preço efetivo da Stake. Flags de lesões no piloto permanecem alegações históricas não confirmadas nesta auditoria.

## 7. Regras de negócio implementadas e faltantes

| Regra | Situação no código |
|---|---|
| Best: ≥8 legs, ≥4 jogos, ≥2 por cada jogo | Implementada por contagem; jogos não são validados contra calendário |
| Best exclusivamente player props | Checa booleano `is_player_prop`; não valida catálogo/mercado real |
| Best mercado disponível | Checa `available`; sem fonte, horário ou prazo de validade |
| Excluir OUT/IR | Implementado nas duas funções com strings exatas; missing/unknown não bloqueiam |
| TD exclusivamente Anytime TD; ≥4 ou ≥2 conforme jogos do dia | Implementado; quantidade do calendário é informada pelo chamador |
| TD distribuído em várias partidas | Exige ≥2 jogos e limita a 2 legs por jogo quando há vários; preferência do usuário virou limite rígido |
| TD mercado disponível | **Ausente**; aceita `available=False` |
| Duplicatas de atleta/seleção e jogo pertencente ao dia | Ausentes; dois TDs idênticos no mesmo jogo passam |
| Orçamento R$50, tetos R$35/R$15 | Só documentação; sem política monetária/ledger no código |
| Instabilidade QB/OL/uso sem excluir automaticamente o adversário | Só documentação e triagens manuais; sem gate por equipe e data |
| Considerar dependências e robustez/EV, não completar com legs fracas | Não implementado no construtor; não há construtor ou otimizador |
| Shortlist sem exigir odds; execução/EV com preço verificável | Relatórios sem odds existem; `expected_value` exige flags, mas não verifica evidências |
| NO_BET por insuficiência de dados | Intenção documentada; falta decisão central com razões e evidências |

`validate_best_parlay`/`validate_td_parlay` retornam explicitamente `STRUCTURAL_ONLY_NO_EV_APPROVAL`: resultado True não deve chegar diretamente a recomendação de execução. Campos obrigatórios ausentes podem gerar KeyError em vez de reprovação estruturada. `expected_value(.7, -2, calibrated=True, price_verified=True)` retorna -2,4; com odd NaN retorna NaN. `implied_probability` também precisa validar finitude. Não há tratamento de push/void na função Python de EV, embora a planilha tenha abas de auditoria para isso.

As flags `calibrated` e `price_verified` são controles locais, não prova de validação. Falta vincular aprovação a versão do modelo, mercado, janela temporal e cotação rastreável. A recomendação operacional continua **NO_BET** até fechar as evidências necessárias.

## 8. Situação real da API Stake

O estado anterior era protótipo não testado ao vivo. Nesta sessão:

1. `GET /en/sports?limit=30&offset=0` retornou dados, incluindo `american-football`. A primeira execução foi intencionalmente limitada a 1 chamada e terminou com exit 1 ao tentar exceder esse teto local; o snapshot parcial foi preservado.
2. Reutilizando o ID retornado, `GET /en/sports/american-football/tournaments?limit=30&offset=0` retornou cinco torneios, incluindo `nfl`.
3. `GET /en/sports/american-football/tournaments/nfl/matches?limit=30&offset=0` retornou 14 partidas; a segunda execução terminou exit 0 e exportou 498 seleções com odds e `available=True`.

Foram três requisições de **dados** no total, sem chave, sem novas consultas de preços nesta auditoria. A tentativa da página raiz é separada e recebeu HTTP 403. Ambas as respostas NFL informam `hasNextPage=False`; isso encerra a paginação desse snapshot, não garante todos os mercados da casa. A resposta de partidas inclui `lastUpdatedAt`; o CSV usa horário de captura, sem manter esse horário de atualização em coluna própria.

Os nomes observados incluem winner, handicap, total, mercados por período e totais de equipes. Não há player props ou Anytime TD nas ofertas retornadas, mesmo com campo `props: true` em partidas. **Não inferir mercados a partir desse flag nem inventar endpoint privado.** A amostra tem preços da fonte Stake no instante da captura; não houve confirmação de execução, interface regional ou cotação da combinada.

O protótipo limita requisições por processo, sem orçamento compartilhado por hora entre execuções; não implementa backoff/Retry-After ou cache de cota. Lê somente primeira página, não tipa jogador/linha/lado, não preserva `startsAt` e suspensão em colunas canônicas e deixa `event_json` sempre vazio (`[:0]`), embora o JSON bruto preserve o evento. Se uma execução reutilizar diretório com snapshot antigo e falhar, a lógica do `finally` pode conservar o arquivo antigo em vez da resposta parcial nova. Usar pasta única e lineage explícita.

Alternativa avaliada: The Odds API para mercados documentados por evento. Ainda não há credencial, licença ou resposta de dados; é candidata, não integração pronta. Persistir `provider` e `bookmaker` separadamente; odds de outras casas não habilitam execução na Stake.

## 9. Arquitetura proposta de atualização automática

Proposta, **ainda não implementada**:

```text
Fontes permitidas → snapshots imutáveis + manifesto/versionamento
                 → contratos de schema/identidade/qualidade
                 → tabelas canônicas Parquet + consultas DuckDB
                 → features com cutoff pré-jogo e modelos versionados
                 → avaliação cronológica / registro de aprovação por mercado
                 → rankings + shortlist + gates de disponibilidade/preço
                 → parlays com distribuição/dependência/orçamento ou NO_BET
                 → relatório revisável em PR → resultados reais + auditoria
```

A base deve distinguir `event_time`, `source_updated_at`, `ingested_at_utc`, `prediction_asof_utc` e `settled_at`, com timezone explícito. Chaves: temporada/tipo/semana/game_id; GSIS para jogadores e crosswalk temporal de PFR/Sleeper; identificadores próprios de evento/mercado/cotação e relação validada com o calendário. Snapshots com UUID/hash, gravação atômica e nenhuma sobrescrita; armazenamento persistente com retenção compatível com backtesting.

Atualização semanal: terça 10h de São Paulo como proposta inicial, após checar encerramento real da rodada. Detectar jogos adiados e revisões; não tratar cron como prova de completude. Atualização pré-jogo: rosters/lesões/inativos e odds com limites específicos de cada fonte; frequência de preços deve respeitar cota pública ou contrato licenciado. Não usar cadastro Sleeper como relatório oficial de inativos.

Pipeline por etapas independentes, idempotentes e com status `OK/PARTIAL/ERROR`, quarentena de violações e manifesto publicado inclusive em falha. CI executa testes estruturais e de contratos, publica logs/artefatos com `always()`, mantém fonte congelada e abre PR de dados/diagnóstico sem auto-merge. Falha ou fonte indisponível produz relatório de dados faltantes e bloqueia recomendação financeira dependente.

Features: passes/corridas, shares, snaps ofensivos e zeros, EPA/success rate e oportunidades de red zone disponíveis primeiro; routes/TPRR/YPRR, OL/pressão, defensores/alinhamento e clima somente com fonte validada. Nenhum indicador indisponível será aproximado silenciosamente. Modelos simples são baselines obrigatórios; treino, ajuste e calibração usam somente observações anteriores ao cutoff e conjunto elegível definido antes do jogo.

Relatórios por jogo/mercado devem guardar justificativa individual, tamanho da amostra, cenários, elegibilidade, probabilidade/intervalo, versão e aprovação, linha/lado/regras de liquidação, preço/fonte/horário, dependências e razões de NO_BET. Avaliar probabilidade conjunta respeitando limites matemáticos, sem multiplicar marginais por padrão. Usar preço da combinada efetivamente oferecido para EV de SGP. Tesouraria com Decimal, limites máximos R$35/R$15 e total R$50, valor zero permitido.

Registrar previsões imutáveis antes do kickoff e resultados posteriores em ledger separado, sem confundir sugerida, aprovada e executada. Avaliação periódica: MAE para volume/jardas, Brier/LL, calibração por faixas, incerteza por jogo/semana e segmentos, comparação pareada contra baselines e controle de drift. CLV/ROI somente com preços, regras e execução comprovados. Relatórios Markdown e PRs permitem revisão pelo GitHub Mobile; dashboard fica posterior à qualidade dos dados.

## 10. Plano de ação priorizado e resultados dos testes

As cinco próximas ações recomendadas, nesta ordem:

1. **P0 — Tornar o pacote executável no Git.** Descompactar em branch revisável, preservar ZIP/legados e hashes, corrigir referências e separar histórico de fontes brutas. Critério: instalação e testes funcionam em clone limpo, workflow visível; nenhuma alteração do baseline.
2. **P0 — Recuperar a linhagem e sanear QA.** Recuperar originais/geradores, conferir 89 registros sem correspondência, 325 identidades incompletas, 57 correções alegadas e QA contraditório. Definir contratos, IDs e snapshots pré-jogo; guardar resultado negativo. Critério: transformação reproduzível com discrepâncias explicitadas, sem preencher desconhecidos com zero.
3. **P0 — Fechar os gates e invalidar probabilidades impossíveis.** Corrigir gerador conjunto quando recuperado; validar limites/finitude, duplicatas, calendário, inativos, estabilidade por equipe, preços, push/void e orçamento. Critério: casos adversos reprovam com razão; True estrutural nunca libera operação financeira.
4. **P1 — Implementar atualização rastreável e integrações de mercado.** Partir dos seis loaders comprovados; separar pré-jogo/rodada/revisões, persistir fonte e diagnóstico inclusive em falhas. Validar cobertura Stake por mercado; se insuficiente, testar provedor licenciado identificado por casa. Critério: PR de atualização reproduzível com cobertura e freshness, sem promessa de props não observadas.
5. **P1 — Reproduzir e ampliar avaliação prospectiva.** Recuperar modelos e baselines, corrigir seleção de elegíveis/zeros/snaps, congelar forecasts e avaliar W10+ sem vazamento, por mercado, com intervalos e calibração por faixas. Critério: registro de aprovação sustentado por holdouts futuros e melhora relevante predefinida; até lá, pesquisa/NO_BET. Depois, relatórios mobile e ledger operacional.

### Execuções realizadas

| Verificação | Resultado |
|---|---|
| `git ls-remote`, `git status`, `git log`, `git ls-tree` | `main`, único commit e único ZIP confirmados antes das alterações |
| `python -m unittest discover -s tests -v` na raiz do checkout | **Falhou**: `ImportError: Start directory is not importable: 'tests'` — diretório só existe no ZIP |
| Mesmo comando na extração temporária | **4 testes passaram**, sem falhas: mínimo Best, IR, distribuição TD e bloqueio EV sem flags |
| Manifesto do pacote | **29/29** tamanho/hash válidos; 30 arquivos no ZIP |
| Instalação das dependências | Sucesso no diretório isolado; versões no JSON; sem alterar requirements |
| CLI NFLverse, temporada 2026 | **Exit 0**, seis fontes OK; schemas/contagens no JSON; W10 ainda parcial |
| CLI Stake com teto 1 | **Exit 1 esperado pelo teto local**, após resposta de esportes preservada |
| CLI Stake com esporte descoberto e teto 2 | **Exit 0**, torneios/partidas reais, 498 seleções; zero player props/TD observadas |
| Recomputar métricas dos 480 TDs/218 pares e MAE de 409 targets | Consistentes com valores apresentados; não reproduz treinamento |
| Limites Fréchet dos 218 pares | **1 violação confirmada**; não corrigida por truncamento |
| Probes adversos das regras existentes | TD indisponível e TD duplicado aceitos; EV com odd negativa/NaN não rejeitado |

Os probes adversos foram executados como diagnóstico, não adicionados à suíte original nem apresentados como testes aprovados. Quatro testes aprovados cobrem somente regras básicas; não validam fontes, modelos, lesões, mercados ou retorno financeiro.

### Reprodução da inspeção

Em clone no commit auditado, extrair o ZIP para diretório separado (não sobrepor arquivos de trabalho), conferir `docs/FILE_MANIFEST.json` e, a partir da extração:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m src.nfl_betting.ingest_nflverse --season 2026 --out /tmp/nfl-audit-snapshots
```

Para reproduzir os dados originais, usar os hashes/snapshots desta auditoria: uma coleta futura pode devolver revisões diferentes. Os Parquets de sondagem, cadastro Sleeper e JSONs de odds ficaram em `/workspace/scratch/` (caminhos e hashes registrados no JSON); **não estão anexados ao Git e não são armazenamento durável garantido**. O JSON versionado preserva inventário, cobertura, schemas, hashes e resultados resumidos. Preservação externa dos brutos e recuperação das fontes históricas são pendências explícitas.

Não repetir a CLI Stake sem verificar o orçamento horário compartilhado. Esta auditoria não ativou agendas, não alterou o Master e não fez merge.
