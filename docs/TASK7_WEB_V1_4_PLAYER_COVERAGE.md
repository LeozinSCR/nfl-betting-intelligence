# V1.4 — roster semanal com cutoff verificável

O exportador preserva o DuckDB de origem em modo somente leitura. Cada
captura guarda o corpo original em `source.bin` e um manifesto em diretório
exclusivo. A exportação lê somente capturas anexadas com `--evidence` e
`available_at <= cutoff`. O cabeçalho HTTP `Last-Modified` é registrado como
metadado da fonte. A disponibilidade local começa após capturar, verificar
e gravar os bytes. O roster exportado registra GSIS, equipe, semana, fonte,
hash, captura, disponibilidade, cutoff e, no fallback, idade em semanas.

## Operação local

Execute pela raiz com o pacote Python instalado. Mantenha os diretórios de
evidência fora de `web/public` e selecione explicitamente as pastas impressas.

```bash
python -m nfl_betting.temporal_roster roster --season 2026 --output /PASTA/EVIDENCIAS
python -m nfl_betting.temporal_roster kickoff --output /PASTA/EVIDENCIAS
python -m nfl_betting.web_export --database /PASTA/CATALOGO --output /PASTA/EXPORT --season 2026 --week 11 --cutoff CORTE_ISO_COM_FUSO --evidence /PASTA/ROSTER --evidence /PASTA/KICKOFF
python -m nfl_betting.web_export --validate-export /PASTA/EXPORT/snapshots/DESTINATION
```

Use o primeiro cutoff real após o fim das capturas, anterior ao kickoff dos
jogos que pretende analisar. O modo padrão exige roster da semana exata por
equipe. `--allow-roster-fallback` habilita `PROVISIONAL_ROSTER` e escreve em
pasta distinta. Esse modo usa a lista inteira mais recente da equipe até o
corte, inclusive ao retornar de um bye. Cada escolha registra a semana de
origem e a idade. Vínculo com a equipe, inativos e QB titular seguem
`UNVERIFIED`. Linhas `CUT`, vínculos encerrados por evento comprovado e
identidades restantes duplicadas são excluídos. O filtro compara IDs GSIS
exatos pela liga inteira.

Para transações revistas, a captura opcional aceita
`transactions --season 2026 --output /PASTA/EVIDENCIAS --url URL_OFICIAL --reviewed /PASTA/reviewed.json`.
A URL deve apontar para NFL League Transactions. O JSON tem `source_sha256`
dos bytes revisados e `records` com `player_id` (GSIS resolvido),
`from_team`, `to_team` (um deles pode ser null), `effective_at_utc` e
`published_at_utc` com fuso. A captura recusa divergência dos bytes
revisados. Um operador deve comprovar ID e datas antes de criar a entrada.
Datas individuais ausentes ou identidade por nome deixam a transação fora
da evidência. Um evento só tem efeito no cutoff se já estava disponível e
efetivo. Este fluxo preserva a decisão `NO_BET` e pressupõe revisão e
permissão de uso da fonte.

A correção de horário é específica para o comunicado NFL de 09/11/2026.
PIT–PHI passa a 18h00 UTC e JAX–NYG passa a 21h25 UTC de 22/11. A hora
individual de publicação do comunicado fica desconhecida. O exportador usa
a disponibilidade da captura e guarda `canonical_kickoff_utc` ao lado da
correção e sua proveniência. Sem evidência admissível no corte, os jogos
continuam no calendário com `KICKOFF_UNVERIFIED` e ficam fora das métricas
pré-jogo. O mesmo kickoff efetivo controla a seleção de partidas históricas.
[Comunicado oficial da NFL](https://media.nfl.com/news-and-releases/week-11-schedule-change--jaguars-giants-to-4-25-p-m--et--steeler)

## Validação real

Catálogo `20261116T223853.798034Z-c42926123911446fbeb78d05c1635302`
e SHA-256 `73cf381f6da8d445c262cce0006875c450cef666269b31c66e4718605fccd426`.
Roster NFLverse capturado em 17/11 às 19h04min22s de São Paulo, com 2.084
linhas W11 para 26 equipes e SHA-256
`e4f81f1adc7243e64290a1fff42309ed8f866628db22738ca0017633904d7751`.
Comunicado capturado em 17/11 às 19h04min23s de São Paulo, com SHA-256
`13c5b402cb235d958e082279490c281fb37fd07a41370bc6b45fa54ca084e8f7`.
As capturas e os JSONs de validação foram escritos fora do repositório.
[Roster semanal NFLverse](https://github.com/nflverse/nflverse-data/releases/tag/weekly_rosters)

| Rodada e corte em São Paulo | Jogos com props / no calendário | Jogadores avaliados | Jogadores com props | Cenários |
| --- | ---: | ---: | ---: | ---: |
| W10 · 16/11 20h00 · roster exato do catálogo | 1 / 14 | 48 | 27 | 176 |
| W11 · 16/11 20h00 · modo estrito | 0 / 13 | 0 | 0 | 0 |
| W11 · 16/11 20h00 · fallback provisório | 11 / 13 | 548 | 297 | 1.937 |
| W11 · 17/11 19h05 · novo roster exato e horários corrigidos | 13 / 13 | 651 | 355 | 2.302 |

Na W10, o jogo com cenários foi LAC–BAL. Os demais 13 jogos tinham resultado no
cutoff. Na W11, a comparação por confronto é a seguinte.

| W11 visitante–mandante | Roster exato, jogadores / cenários | Fallback provisório, jogadores / cenários |
| --- | ---: | ---: |
| IND–HOU | 25 / 158 | 25 / 158 |
| ARI–KC | 25 / 177 | 25 / 177 |
| BAL–CAR | 29 / 184 | 29 / 184 |
| JAX–NYG | 26 / 167 | Horário bloqueado |
| MIA–BUF | 29 / 180 | 29 / 180 |
| NO–CHI | 25 / 170 | 25 / 170 |
| TB–DET | 24 / 154 | 24 / 154 |
| TEN–DAL | 23 / 158 | 23 / 158 |
| NYJ–LAC | 26 / 174 | 26 / 174 |
| LV–DEN | 28 / 184 | 28 / 184 |
| PIT–PHI | 32 / 198 | Horário bloqueado |
| MIN–SF | 34 / 213 | 34 / 213 |
| CIN–WAS | 29 / 185 | 29 / 185 |

Os cenários são limiares estatísticos e incluem zero odds verificadas e
zero modelos aprovados. O roster exato melhora a cobertura de associação
semanal. A participação oficial continua desconhecida. O catálogo base ainda
é parcial e seu histórico não inclui o resultado de LAC–BAL W10. Não houve
transação real com GSIS e timestamps individuais verificados nesta entrega.
Transferências e demais condições adversas foram exercitadas com fixtures
offline sintéticas. A correção dos dois kickoffs fica em evidência separada
enquanto o catálogo histórico conserva os horários originais.
