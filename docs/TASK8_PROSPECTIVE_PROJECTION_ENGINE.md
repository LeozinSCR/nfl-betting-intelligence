# V1.5 — motor prospectivo de projeções, etapa 1

O módulo `nfl_betting.projection` produz contagens e jardas esperadas por
jogador e jogo, condicionadas à participação ofensiva. A participação oficial
segue `UNVERIFIED`. O resultado é pesquisa com `NO_BET`, sem aprovação
estatística ou financeira. TDs são contagens ofensivas de corrida e recepção.

## Coorte e relógio

- Cada `--fold SEMANA@CUTOFF` usa o catálogo canônico verificado mais recente
  disponível até o cutoff. Só entram jogos agendados com kickoff posterior ao
  cutoff. Correções verificadas de kickoff da V1.4 respeitam a disponibilidade
  da evidência. Cada jogo pode aparecer em um único fold.
- A coorte é definida antes de ler os resultados, com roster da semana exata
  visível até o cutoff. Usa GSIS e equipe inequívocos. Treinamento usa apenas
  histórico da mesma equipe e temporada regular, em datas de jogo anteriores,
  com placar, fim de jogo no PBP, participação ofensiva confirmada e dados
  disponíveis até o cutoff. O jogo-alvo é excluído por ID.
- Resultados são lidos de catálogos declarados separadamente em `--labels`.
  A avaliação combina jogo, equipe, GSIS e mercado. A versão admissível mais
  antiga fornece o resultado observado. O kickoff precisa bater com o da
  previsão e a disponibilidade do resultado precisa ser posterior ao kickoff.
  Jogadores sem resultado ofensivo observado ficam fora da métrica condicional,
  sem imputar zero.
- O agrupamento walk-forward usa a data do jogo em America/New_York. Nenhuma
  previsão ou resultado do mesmo dia entra na calibração dos intervalos daquele
  dia. Capturas tardias de semanas anteriores servem para descrever aquele
  histórico a partir da captura.

## Baselines e intervalos

| Modelo fixado antes da avaliação | Cálculo |
| --- | --- |
| `season_mean` | Média dos jogos elegíveis da temporada. |
| `recency_mean` | Média ponderada por três faixas disjuntas. Jogos fora de L5 têm peso 1, os dois jogos de L5 fora de L3 têm peso 1,5 e os três jogos de L3 têm peso 2. |
| `usage_efficiency` | Snaps esperados pela recência × oportunidades por snap × produção por oportunidade. As duas razões usam somas dos jogos elegíveis. O denominador usa carries para corrida, targets para recepção e a soma para TD. A eficiência de carries é 1. |

Cada mercado exige cinco jogos com valor observado. O modelo de uso exige
também cinco jogos com snaps positivos e oportunidades utilizáveis e dez
oportunidades acumuladas. Valores ausentes ficam ausentes. A produção usa
o valor canônico do PBP e, quando falta um valor, o equivalente semanal
observado. Inconsistências entre produção e oportunidades ficam fora do ajuste
de eficiência. Os zeros observados e as jardas negativas são preservados.

O intervalo empírico usa o maior erro absoluto por data anterior, para o
mesmo mercado e modelo, com rótulos disponíveis até o cutoff. Com pelo menos
dez datas, aplica o quantil de ordem `ceil((n + 1) × 0,80)` a esses máximos
como raio ao redor da previsão. Para contagens o limite inferior é limitado
a zero. A cobertura empírica é avaliada separadamente. Deriva temporal e
dependência entre datas ainda precisam de validação. Com menos datas, o
intervalo retorna `INSUFFICIENT_DATA` e a cobertura permanece `null`.

Nenhum ajuste de adversário foi aplicado. Falta um efeito verificável fora da
amostra por posição e mercado. Os agregados defensivos atuais também variam
em cobertura e têm denominadores diferentes.

## Auditoria e avaliação reais

O catálogo congelado antes de LAC–BAL estava disponível em **16/11/2026 às
19h38 de São Paulo**. O primeiro fold usou 20h00. Um catálogo separado foi
capturado em **17/11/2026 às 19h27**, servindo de fonte do resultado W10 e de
features para a W11 somente a partir do cutoff de **19h28**.

- Pré-W10: 149 jogos concluídos, 3.677 registros jogador–jogo com participação
  ofensiva, dos quais 3.662 com snaps. Carries tinha 3.677 valores observados.
  Cada um de jardas corridas, recepções, jardas recebidas e TDs tinha 3.237.
- **Jardas passadas e tentativas de passe**: zero observações individuais
  materializadas em `player_week`. A coleta bruta tem `passing_yards`,
  `attempts` e eventos de passe, mas falta materializar e reconciliar
  volume e resultado por GSIS. Tentativas agregadas de equipe não cobrem o
  mercado individual. Ambos retornam `INSUFFICIENT_DATA`.
- W11: 13 jogos, 651 jogadores considerados e 1.359 pares jogador–mercado
  com estimativa pontual de 313 jogadores. Foram 313 de carries, 275 de
  jardas corridas, 248 de recepções, 248 de jardas recebidas e 275 de TD.
  Esses jogos ainda estavam pendentes de resultado.

**Única data avaliada: LAC–BAL, W10.** Foram 20 jogadores, 86 pares
jogador–mercado e 227 previsões de modelos avaliadas. Os tamanhos das amostras
da média da temporada e da média por recência nos cinco mercados foram
17/20/16/16/17, na ordem da tabela. A tabela compara os três modelos nos
mesmos casos com suporte de snaps. Cada célula mostra **MAE / RMSE / viés
(previsão menos observado)**, na unidade do mercado.

| Mercado | N comum | Média temporada | Média por recência | Uso × eficiência |
| --- | ---: | ---: | ---: | ---: |
| Jardas corridas | 6 | 36,12 / 40,87 / +7,42 | 36,39 / 40,78 / +6,36 | 36,23 / 40,71 / +6,98 |
| Carries | 6 | 4,56 / 5,72 / +0,56 | 4,71 / 5,80 / +0,39 | 4,60 / 5,70 / +0,45 |
| Recepções | 14 | 1,63 / 2,05 / −0,91 | 1,70 / 2,12 / −0,89 | 1,62 / 2,07 / −0,90 |
| Jardas recebidas | 14 | 19,90 / 26,30 / −9,24 | 21,34 / 27,68 / −9,78 | 20,38 / 26,59 / −9,07 |
| TDs ofensivos | 15 | 0,277 / 0,426 / −0,073 | 0,287 / 0,463 / −0,100 | 0,282 / 0,435 / −0,074 |

Não houve intervalos avaliáveis em nenhum mercado. A única data de teste
não sustenta escolher um modelo, afirmar ganho sobre as médias ou validar
cobertura. A Semana 11 usa evidências semanais de roster e os dois kickoffs
corrigidos disponíveis após as capturas. Os resultados unitários com mais
datas de calibração vêm de fixtures explicitamente sintéticas.

## Reproduzir e consumir

```bash
python -m nfl_betting.projection --season 2026 --features /BUILD_PRE_W10 --features /BUILD_17NOV --labels /BUILD_17NOV --fold 10@2026-11-16T23:00:00Z --fold 11@2026-11-17T22:28:00Z --evidence /ROSTER_W11 --evidence /KICKOFF_W11 --output /PASTA/NOVO_RELATORIO.json
```

O JSON `1.5.0` separa `folds`, `projections`, `evaluations` e
`metrics_by_market`. Cada fold registra hashes, cutoff, fontes e auditoria
dos mercados. A projeção inclui vínculos de roster e calendário, amostra
treinada e valores usados por jogo. Métricas vêm por modelo e por coorte
comum. O CLI abre cada catálogo somente para leitura e cria o relatório
sem substituir um arquivo existente. O dashboard permanece fora desse fluxo.

Na reprodução, o build pré-W10 tem ID
`20261116T223853.798034Z-c42926123911446fbeb78d05c1635302` e SHA-256
`73cf381f6da8d445c262cce0006875c450cef666269b31c66e4718605fccd426`.
O build posterior tem ID `20261117T222708.323142Z-6ffe0b929aa3432b9feb9de6df65d10a`
e SHA-256 `efc826db3cd4aa94ef60512eb80e724a82a35c2df01cc4227362dffb568260ec`.

## Critérios propostos para aprovação futura

1. Colecionar capturas pré-jogo versionadas, com roster e inativos oficiais,
   e fixar a coorte e a definição de cada alvo antes do backtest. Separar
   treino, calibração e holdout por data e agrupar comparações por jogo.
2. Para cada mercado, reservar um holdout com pelo menos 20 datas e 400
   pares jogador–mercado, com mínimo de 50 eventos e 50 não eventos por
   limiar probabilístico avaliado. Exigir que o limite superior do IC de 95%
   da diferença modelo menos baseline seja negativo tanto em Brier como em
   log loss. Estimar os intervalos em blocos por data e fixar o baseline
   antes do holdout. Reportar curvas de calibração, também por faixa de
   probabilidade e recência.
3. Exigir cobertura observada compatível com o nível nominal dos intervalos
   dentro de ±5 pontos percentuais, com incerteza por blocos e diagnóstico
   por mercado. Comparar também a largura dos intervalos. Só projetar efeitos
   de adversário após ganho repetido em folds separados com amostra suficiente
   e validação no holdout.

Esses critérios ainda não foram atingidos e nenhuma probabilidade foi
estimada nesta etapa.
