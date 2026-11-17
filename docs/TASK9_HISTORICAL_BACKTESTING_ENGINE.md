# V1.6 — Motor histórico de avaliação NFL

## Modos e proveniência

- `STRICT_AS_OF` escolhe jogos de catálogos verificados apresentados como
  features. Define o primeiro cutoff viável, com antecedência configurável, e
  exige `available_at <= cutoff < kickoff`. Uma versão de calendário
  conflitante já visível no corte bloqueia o jogo. Nos dois remanejamentos
  oficiais da V1.4, a evidência precisa estar disponível antes do mais cedo
  dos deadlines original e corrigido. Catálogos de resultados ficam
  separados. Um rótulo exige o mesmo jogo, GSIS, equipe, mercado e kickoff.
- `RETROSPECTIVE_EXPLORATORY` usa um arquivo posterior para reconstruir o
  histórico por data de jogo. A coorte vem de rosters de semanas anteriores.
  O histórico usa apenas jogos de datas anteriores ao alvo e kickoffs
  anteriores ao cutoff hipotético. O contrato exige marcador de fim no
  arquivo, que pode ter sido coletado muito depois do jogo. O relatório
  conserva os horários reais de captura, marca o roster como
  `HISTORICAL_ROSTER_PROXY` e apresenta `availability_claim=false`.
  Este modo serve para dimensionar cobertura e estudar o método.

Os dois modos usam os três modelos fixos da V1.5 e hash dos artefatos
selecionados. GSIS ausentes ou ambíguos são excluídos, sem identificação por
nome. Um zero observado entra no cálculo. Um valor ausente permanece nulo.
O inventário registra versões de calendário, cutoffs, catálogos, hashes e as
versões das fontes da ingestão. Os relatórios mantêm `NO_BET`,
`statistical_model_approved=false` e `financial_approved=false`.

## Partições, métricas e gates

As datas dos planos aceitos são agrupadas em `America/New_York` e divididas
cronologicamente em 50% treino, 25% validação e o restante teste.
O histórico expande até cada cutoff nas fases de treino e validação. No
primeiro cutoff do teste, o histórico é congelado e exclui toda a primeira
data de teste e todas as seguintes. No modo estrito, o roster de cada jogo
de teste continua sendo consultado com o cutoff daquele jogo. No retrospectivo,
o limite de semana do roster também é congelado antes do bloco de teste.
Nenhum resultado do bloco final altera as outras projeções do mesmo bloco.

- O teste compara apenas pares jogador–jogo–mercado com resultado admissível e
  previsão dos três modelos. Registra N, jogos, datas, maior participação
  de um jogo e previsão por modelo. Abaixo de 20 datas, 400 pares, acima
  de 10% de concentração num jogo ou sem suporte nas fases anteriores,
  retorna `INSUFFICIENT_EVALUATION_DATA` e deixa as métricas nulas.
- Quando os gates de amostra passam, calcula MAE, RMSE e viés. Compara os
  erros absolutos pareados à média da temporada, com IC de 95% por bootstrap
  de 1.000 reamostragens de datas, seed 2026. A melhora só é sustentada
  quando o limite superior do IC da diferença é negativo.
- Intervalos empíricos usam apenas resíduos da validação estrita cujos
  resultados já estavam disponíveis no congelamento. São necessárias pelo
  menos dez datas. A cobertura no teste considera apenas intervalos produzidos
  antes de cruzar os resultados. O modo retrospectivo mantém os intervalos
  indisponíveis.
- Qualquer aprovação probabilística futura exige, por limiar, ao menos 50
  eventos, 50 não eventos, calibração validada e comparação com baseline.
  A V1.6 mantém o bloqueio de aprovação. Jardas e tentativas de passe
  continuam `INSUFFICIENT_DATA` no esquema individual atual.

## Execução reproduzível

Na raiz, usando o ambiente do projeto e pastas de saída inéditas:

```powershell
$v16Pre = 'C:/CAMINHO/BUILD_PRE_W10'
$v16Labels = 'C:/CAMINHO/BUILD_17NOV'
$v16Weeks = @(1..10 | ForEach-Object { '--week'; [string]$_ })
python -B -m nfl_betting.backtesting --mode STRICT_AS_OF --season 2026 --as-of 2026-11-17T22:28:00Z --lead-minutes 135 --features $v16Pre --labels $v16Labels --output C:/CAMINHO/STRICT @v16Weeks
python -B -m nfl_betting.backtesting --mode RETROSPECTIVE_EXPLORATORY --season 2026 --as-of 2026-11-17T22:28:00Z --lead-minutes 135 --features $v16Labels --labels $v16Labels --output C:/CAMINHO/RETRO @v16Weeks
```

É possível repetir `--features`, `--labels` e `--evidence` para registrar
outros catálogos e capturas verificáveis. Os builds reais desta execução estão
identificados por ID e hash no [relatório da V1.5](TASK8_PROSPECTIVE_PROJECTION_ENGINE.md).
O CLI lê o DuckDB canônico em modo somente leitura e cria `report.json` e
`report.md` em um diretório novo. Nenhum arquivo é publicado no dashboard.

## Resultado real, W1–W10 de 2026

O arquivo de resultados cobre 150 jogos. O bloco estrito tem apenas
**LAC–BAL** e 55 pares na coorte comum. As outras 149 partidas foram
excluídas por `LATE_CAPTURE`. O retrospectivo criou planos de avaliação
para os 150 jogos, com 134 jogos com resultado admissível associado à
coorte e 2.751 pares comuns somadas as fases. Seu teste final cobre apenas
oito datas com pares por mercado. Ambos retornaram
`INSUFFICIENT_EVALUATION_DATA`, com MAE, RMSE, viés e intervalos finais
indisponíveis. Os resultados unitários com amostras acima dos gates são
de fixtures sintéticas.

| Mercado | Estrito, pares no teste | Retrospectivo, pares na validação | Retrospectivo, pares no teste (jogos / datas) |
| --- | ---: | ---: | ---: |
| Jardas passadas | 0 | 0 | 0 (0 / 0) |
| Tentativas de passe | 0 | 0 | 0 (0 / 0) |
| Jardas corridas | 6 | 114 | 187 (42 / 8) |
| Carries | 6 | 118 | 194 (42 / 8) |
| Recepções | 14 | 241 | 419 (42 / 8) |
| Jardas recebidas | 14 | 241 | 418 (42 / 8) |
| TDs ofensivos | 15 | 303 | 516 (42 / 8) |

O retrospectivo ainda não tem pares comuns na primeira fase, dado o
requisito de histórico por jogador. No estrito, além da falta de amostra,
há concentração integral em um jogo, 114 ocorrências de histórico
insuficiente e 118 de resultado ausente. No retrospectivo, as principais
ocorrências são histórico insuficiente (25.523), resultado ausente
(17.136) e feature ausente (4.335). Contagens de exclusão incluem níveis
de jogo, jogador e mercado. Um registro pode acumular mais de uma causa.
