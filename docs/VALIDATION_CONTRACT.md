# Contrato de validação estrutural (v0.2)

As funções em `nfl_betting.rules` não consultam redes, não escolhem jogadores e não aprovam modelos. Retornam `ValidationResult` com `issues` (code, field, message, leg_index), `warnings` e `.valid`. Usar `bool(result)` gera TypeError para exigir leitura explícita de `.valid`. A decisão permanece `NO_BET`; não há aprovação estatística/financeira.

O contrato antigo `(bool, reason)` e a contagem avulsa `games_that_day` foram substituídos. `expected_value` não aceita mais flags `calibrated/price_verified` capazes de contornar as verificações. Quem chama deve migrar para o contrato abaixo.

## Contexto

`validate_best_parlay(legs, **context)` e `validate_td_parlay(legs, **context)` recebem:

- `schedule`: lista completa de jogos do dia, com `game_id`, `home_team`, `away_team`, `kickoff`, `source_url`, `checked_at`, `valid_until`. Deve ser obtida de fonte verificável; a função não comprova a autenticidade ou completude da lista recebida.
- `slate_date`: `datetime.date` explícito; `timezone_name` padrão `America/Sao_Paulo` determina o dia do kickoff.
- `as_of`: datetime com timezone; padrão horário UTC atual. Não há partidas já iniciadas. Em avaliações históricas, fornecer o cutoff congelado, não o horário do resultado.
- `require_quotes`: False para shortlist sem odds. True exige cotação válida em todas as legs. Se uma quote for fornecida, será validada mesmo em shortlist.
- `stake`: valor em reais, padrão zero, precisão de centavos, limitado a 35 ou 15. `validate_budget(best, td)` verifica também o total de 50. Isso valida valores informados; não controla saldo ou ordens externas.
- `joint_probability`: opcional, exige `probability` em cada leg e satisfaz limites de Fréchet gerais. A ausência não é substituída por produto de marginais.

Todos os horários aceitam datetime aware ou ISO 8601 com offset/Z. Origem requer URL HTTPS sem credenciais. É proibido inventar URLs para fazer o gate passar. As verificações locais asseguram presença e consistência, **não autenticam o conteúdo da fonte**.

## Leg

| Campo | Contrato |
|---|---|
| `game_id`, `player_id`, `team` | Strings não vazias; jogo consta do calendário e equipe pertence ao jogo |
| `market` | `receptions`, `targets`, `carries`, `rec_yards`, `rush_yards`, `pass_yards`, `pass_attempts`, `completions` ou `anytime_td` |
| `is_player_prop` | True literal, além do catálogo de mercados suportados |
| `side`, `line` | over/under e número finito ≥0; para anytime_td: yes e null |
| `player_availability` | Mapping com `status=ACTIVE`, `source_url`, `checked_at`, `valid_until` |
| `market_availability` | Mapping com `available=True`, `source_url`, `checked_at`, `valid_until` |
| `injury_status` | HEALTHY/ACTIVE; QUESTIONABLE somente com prova ACTIVE atual e aviso. OUT, IR, outros status indisponíveis ou desconhecidos bloqueiam |
| `team_stable` | True literal após avaliação de QB/OL/função. Refere-se à equipe do jogador; instabilidade do adversário não é uma exclusão automática |
| `probability` | Opcional; se presente deve ser numérica, finita e em [0,1] |
| `quote` | Opcional em shortlist; contrato abaixo |

O cadastro de jogador e a ligação à equipe devem ser reconciliados por IDs antes de construir a leg; o gate não substitui o crosswalk temporal. Preferir jogadores com disponibilidade oficial confirmada. Dados de disponibilidade devem estar vinculados a essa seleção pelo chamador, com sua evidência preservada.

Validade padrão máxima desde a observação: calendário 7 dias, jogador 24h, disponibilidade de mercado 5 minutos e preço 5 minutos. Exige sempre `observed/checked <= as_of < valid_until`. São limites conservadores de engenharia, **não garantias de estabilidade da informação**. Inativos oficiais e mudanças de última hora podem exigir nova captura muito antes desses limites.

Duplicata exata é detectada por `(game_id, player_id, market, side, line)`. Repetir o mesmo mercado do mesmo jogador, mesmo mudando linha/lado, também bloqueia como redundante/conflitante; mercados diferentes do mesmo jogador são permitidos estruturalmente e ainda exigem análise de dependência. O mínimo de duas props por jogo não implica independência.

## Quote

Campos obrigatórios: `provider`, `bookmaker`, `source_url`, `selection_id`, `game_id`, `player_id`, `market`, `side`, `line`, `decimal_odds`, `available`, `observed_at`, `valid_until`. Odds precisam ser números finitos >1, sem conversão permissiva de strings ou booleanos. Quote e leg devem concordar em jogo/jogador/mercado/lado/linha. Sem cotação verificada da Stake, odds de outra casa permanecem identificadas como dessa outra casa.

`validate_quote(quote, as_of=..., leg=...)` não aprova preço da combinada: um SGP exige preço próprio oferecido pela casa, equivalência de regras de liquidação e disponibilidade. O protótipo Stake exporta eventos não mapeados para IDs canônicos, **não fornece Quotes prontas**. Como não recebe expiração da fonte, não inventa `valid_until`: o campo permanece vazio e não passa o gate até uma política explícita e validada de validade/binding ser aplicada.

## Probabilidade e EV de pesquisa

`validate_probability`, `validate_decimal_odds`, `implied_probability` e `validate_joint_probability` rejeitam NaN, infinito, booleanos, strings e limites inválidos. Probabilidades conjuntas satisfazem `max(0,sum(p_i)-(n-1)) <= p_joint <= min(p_i)`. Nunca truncar silenciosamente uma previsão histórica para fazê-la passar.

`expected_value(p_win, quote, push_probability=p_push, as_of=...)` retorna `ResearchEV`, com valor por unidade `p_win*odd - (1-p_push)`. Win/push precisam ser finitos em [0,1] e somar no máximo 1. A probabilidade de push deve ser fornecida explicitamente conforme regra real de liquidação; não inferir de uma linha artificial. A função não estima probabilidades, não implementa todos os cenários de void/SGP e não aprova execução. O rótulo é `EXPLORATORY_NOT_CALIBRATION_APPROVAL`, decisão `NO_BET`.

Ver `tests/test_rules.py` para exemplos sintéticos completos. Os preços, atletas, times e URLs `.invalid` desses testes não são dados reais e não devem entrar em relatórios operacionais.
