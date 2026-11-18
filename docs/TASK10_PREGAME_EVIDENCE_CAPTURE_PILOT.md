# V1.7 — Piloto manual de captura pré-jogo

`nfl_betting.pregame_capture` planeja uma janela de até 30 minutos de
diferença entre kickoffs. O cutoff padrão é K−135 minutos. O planejador lê
um catálogo canônico existente e compara IDs, times e horário com uma
evidência oficial já capturada, revisada e autorizada. A segunda conferência
usa o calendário do novo build. Divergências conhecidas bloqueiam o plano
ou excluem o jogo no recibo. Um kickoff remarcado requer nova verificação
do calendário e novo plano.

## Entrada oficial autorizada

O piloto recebe um diretório com `source.bin` (bytes do calendário oficial
capturados com autorização), `authorization.bin` (comprovante conferido pelo
operador) e `manifest.json`. O arquivo JSON contém:

- `schema_version` igual a 1, `season`, `week`, `source_url` HTTPS da NFL,
  `source_version`, `reviewed_by` e `capture_authorized: true`.
- `sha256` de `source.bin`, `authorization_sha256`, `started_at_utc`,
  `finished_at_utc`, `available_at_utc` e `published_at_utc` quando a hora
  de publicação da versão é comprovada. Use `null` quando desconhecida.
- `games` com `game_id` canônico, `away_team`, `home_team` e
  `kickoff_utc` ISO com offset para cada jogo revisado.
- `public_redistribution_authorized: true` somente quando houver permissão
  para expor o conteúdo integral do pacote em um repositório público,
  inclusive o comprovante de autorização.

Os hashes vinculam os documentos revisados aos bytes arquivados. A
transcrição do calendário e o significado da autorização dependem da
revisão humana. A coleta automática usa exclusivamente o coletor NFLverse
já existente. Inativos e titularidade permanecem sem verificação oficial.

## Um único piloto real, local e R$ 0 adicional

Após autorização específica do operador, use o ambiente já instalado,
espere a janela de trabalho e confirme o calendário oficial imediatamente
antes de planejar. Se IND–HOU W11 estiver confirmado às 22h15 de São Paulo,
o cutoff K−135 será 20h00. Começar perto de 19h07 deixa margem para construir
e selar o pacote. Datas e horários do plano são derivados do arquivo,
inclusive quando o kickoff em UTC cai no dia seguinte.

```powershell
$v17Ref = 'C:/CAMINHO/BUILD_CANONICO_EXISTENTE'
$v17Official = 'C:/CAMINHO/CALENDARIO_REVISADO_E_AUTORIZADO'
$v17Plan = 'C:/CAMINHO/NOVO_PLANO_W11_IND_HOU'
$v17Bundle = 'C:/CAMINHO/NOVO_BUNDLE_W11_IND_HOU'
python -B -m nfl_betting.pregame_capture plan --catalog $v17Ref --official $v17Official --season 2026 --week 11 --game 2026_11_IND_HOU --lead-minutes 135 --output $v17Plan
if ($LASTEXITCODE -ne 0) { throw 'Plano recusado' }
python -B -m nfl_betting.pregame_capture capture --plan $v17Plan --output $v17Bundle --authorized
```

Para agrupar jogos da mesma janela, repita `--game` ao planejar. A captura
faz uma única coleta das seis fontes e constrói um catálogo novo em área
temporária. Calendário, roster, PBP, snaps e estatísticas são obrigatórios.
Falha em lesões pode produzir catálogo parcial. São exigidos roster da semana
para as equipes e captura, build e selo até cada cutoff. Um runner que
começa após o primeiro cutoff encerra a janela antes de baixar dados.

O `index.json` registra recibos `ELIGIBLE` ou `EXCLUDED` por
`game_id@cutoff`. Contém a proveniência oficial, janelas e hashes de cada
fonte, disponibilidade do build, versão do código, ID da execução e
`NO_BET`. A função de verificação recalcula os recibos. O horário de captura
observado pelo processo e a disponibilidade do build são registrados
separadamente. A V1.7 depende do relógio confiável do executor e de um digest
obtido por canal independente. SHA-256 assegura integridade dos bytes.

## Backup, recuperação e backtest

Anote o `index_sha256` exibido na execução em um registro separado da cópia.
Preserve a árvore completa em armazenamento local existente. Quando um
workflow tiver sido autorizado, use `gh run download RUN_ID --name NOME --dir NOVA_PASTA`
antes da expiração e confira contra o digest guardado no log original. O
mesmo comando de verificação serve para uma cópia entregue offline.

```powershell
$v17Digest = 'SHA256_DO_INDICE_GUARDADO_SEPARADAMENTE'
$v17Backup = 'C:/CAMINHO/NOVA_COPIA_OFFLINE'
python -B -m nfl_betting.pregame_capture verify --folder $v17Bundle --expected-index $v17Digest
python -B -m nfl_betting.pregame_capture restore --folder $v17Bundle --expected-index $v17Digest --output $v17Backup
```

O pacote preserva a evidência autorizada, os dados brutos, o build e os
manifestos pelos hashes do catálogo de arquivo existente. Um pacote tardio
ou incompleto pode conter brutos diagnósticos, sem catálogo elegível.
Se o download estiver indisponível, use a cópia offline validada. Sem os
bytes, a avaliação daquele jogo permanece indisponível.

Quando houver catálogo posterior de resultados, use:

```powershell
python -B -m nfl_betting.backtesting --mode STRICT_AS_OF --season 2026 --as-of DATA_ISO_APOS_RESULTADO --week 11 --lead-minutes 135 --pilot $v17Backup $v17Digest --labels C:/CAMINHO/BUILD_RESULTADOS --output C:/CAMINHO/NOVO_RELATORIO
```

`--pilot` verifica o pacote e admite somente jogos com recibo elegível,
cutoff compatível e calendário correspondente. Pode ser repetido para
combinar janelas. O modo legado da V1.6 continua disponível via `--features`
em execução separada. Resultados são entregues por `--labels`. O selo
posterior ao cutoff e os rótulos tardios ficam fora das features.

## Workflow e condição para automatizar

`pregame_pilot.yml` tem apenas `workflow_dispatch` e um job no runner padrão.
A branch padrão ainda precisa conter o arquivo para habilitar o disparo.
O job exige autorização explícita, `plan_path` relativo ao checkout,
`plan_sha256` independente e a variável `PREGAME_ARTIFACT_BUDGET_VERIFIED=true`,
que só deve ser configurada depois de comprovar margem e bloqueio de gasto
adicional. A variável registra essa confirmação e não altera a cobrança.
Retenção configurável em 1, 3 ou 7 dias, com padrão de 3. O upload ocorre
somente quando todos os recibos da janela estão elegíveis e a redistribuição
foi comprovada.

Um cron futuro depende de autorização, simulação de fila/DST e jogos
remarcados, duração medida do job com folga até o cutoff, monitoramento de
capturas perdidas, teste de restauração e cópia antes da expiração. A
execução local permanece a opção de R$ 0 quando a franquia do GitHub
ou a redistribuição pública estiverem incertas.

## Exemplos sintéticos

| game_id | Kickoff UTC | Cutoff UTC | Fim da captura UTC | Selo UTC | Recibo |
| --- | --- | --- | --- | --- | --- |
| `target` | 01/10/2026 20h00 | 19h00 | 18h40 | 18h55 | `ELIGIBLE` |
| `target` | 01/10/2026 20h00 | 19h00 | 19h01 | 19h02 | `EXCLUDED / LATE_CAPTURE` |
| `target` | 01/10/2026 20h00 | 19h00 | — | 19h00min02s | `EXCLUDED / LATE_START` |

Os exemplos condensam fixtures offline com lead de 60 minutos. Não
representam jogos nem coletas reais.
