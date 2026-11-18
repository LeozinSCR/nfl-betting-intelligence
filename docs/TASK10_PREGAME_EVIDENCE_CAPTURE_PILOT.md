# V1.7 — Piloto manual de captura pré-jogo

`nfl_betting.pregame_capture` planeja uma janela de até 30 minutos de
diferença entre kickoffs. O cutoff padrão é K−135 minutos. O planejador lê
um catálogo canônico existente e compara IDs, times e horário com uma
evidência selecionada em `plan --official` ou `plan --licensed`. A segunda conferência
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

## Calendário NFLverse licenciado para uso local

`plan --licensed` seleciona `NFLVERSE_LICENSED`. O
[ativo `games.parquet` da release `schedules`](https://github.com/nflverse/nflverse-data/releases/tag/schedules)
segue a [declaração CC BY 4.0 do NFLverse](https://github.com/nflverse#licensing)
e a [licença vinculada à tag](https://github.com/nflverse/nflverse-data/blob/ab1331c85fd222ce953fe61363b099c0629de0a1/LICENSE.md).
Credite NFLverse e Lee Sharpe. A URL é mutável. A versão identifica os bytes
originais do HTTP 200 por `sha256:<digest>` e pelo manifesto de captura,
com horários UTC observados. Last-Modified e a data da release ficam
distintos da publicação comprovada de uma versão específica.

O [upstream `nfldata`](https://github.com/nflverse/nfldata) carece de licença
própria identificada, e o parquet inclui linhas e odds. Antes de copiar
bytes, revise a base que permite retenção local do arquivo integral e dos
brutos do piloto, incluindo as versões coletadas no dia e uma cópia offline
privada. Em caso de dúvida sobre o escopo, interrompa. Documente a base real
em `retention.txt` (UTF-8) com referência verificável. O operador revisa os
direitos. O código valida o vínculo e a integridade da evidência. Use um
diretório privado fora de pastas sincronizadas.

A conferência humana registra URL, responsável, kickoff observado e horário
da observação. Preencha o horário de publicação só quando verificável.
Quando somente a data for conhecida, use `null`. A consulta segue os
[termos da NFL](https://www.nfl.com/legal/terms/). O modo licenciado arquiva
essa observação factual, sem copiar HTML, PDF ou imagens da NFL.

### Preparação em PowerShell

Execute da raiz do projeto, depois de confirmar a base de retenção. Use o
manifesto original e o corpo HTTP de um snapshot já preservado. O parquet
transformado pelo coletor tem outro hash. Confira o calendário oficial
imediatamente antes de preencher os dados da observação.

```powershell
$raw = Read-Host 'Diretório privado do snapshot bruto existente'
$rights = Read-Host 'Caminho do retention.txt revisado'
$basis = Read-Host 'Referência verificável da base de retenção'
$reviewer = Read-Host 'Nome do revisor'
$rightsReviewed = [DateTimeOffset]::UtcNow.ToString('o')
$officialUrl = Read-Host 'URL NFL consultada para IND @ HOU'
$observedKickoff = Read-Host 'Kickoff observado, em ISO 8601 com offset'
$observedAt = [DateTimeOffset]::UtcNow.ToString('o')

$origin = Join-Path $raw 'manifest.json'
$schedule = (Get-Content -LiteralPath $origin -Raw | ConvertFrom-Json).sources.schedules
$bodies = @($schedule.http_responses | Where-Object { $_.status_code -eq 200 })
if ($bodies.Count -ne 1) { throw 'Esperado um corpo HTTP 200 de schedules.' }
$body = Join-Path $raw $bodies[0].path
$digest = (Get-FileHash -LiteralPath $body -Algorithm SHA256).Hash.ToLowerInvariant()
if ($digest -ne $bodies[0].sha256) { throw 'SHA-256 do corpo divergente.' }
$inputDir = Join-Path $env:LOCALAPPDATA 'NFL-Pregame\2026-11-IND-HOU\licensed-input'
if (Test-Path -LiteralPath $inputDir) { throw 'Escolha uma nova pasta de evidência.' }
New-Item -ItemType Directory -Path $inputDir -ErrorAction Stop | Out-Null
Copy-Item -LiteralPath $body -Destination (Join-Path $inputDir 'source.parquet')
Copy-Item -LiteralPath $origin -Destination (Join-Path $inputDir 'origin.json')
Copy-Item -LiteralPath $rights -Destination (Join-Path $inputDir 'retention.txt')
$manifest = @{
    schema_version = 1
    season = 2026
    week = 11
    sha256 = $digest
    source_version = "sha256:$digest"
    origin_sha256 = (Get-FileHash -LiteralPath $origin -Algorithm SHA256).Hash.ToLowerInvariant()
    license = @{
        id = 'CC-BY-4.0'
        url = 'https://creativecommons.org/licenses/by/4.0/'
        declaration_url = 'https://github.com/nflverse/nflverse-data/blob/ab1331c85fd222ce953fe61363b099c0629de0a1/LICENSE.md'
        attribution = @('NFLverse', 'Lee Sharpe')
    }
    local_retention = @{
        scope = 'LOCAL_PILOT_RAW_ARCHIVE'
        basis_reference = $basis
        reviewed_by = $reviewer
        reviewed_at_utc = $rightsReviewed
        sha256 = (Get-FileHash -LiteralPath $rights -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    official_observations = @(@{
        game_id = '2026_11_IND_HOU'
        source_url = $officialUrl
        reviewed_by = $reviewer
        kickoff_utc = $observedKickoff
        observed_at_utc = $observedAt
        published_at_utc = $null
    })
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $inputDir 'manifest.json')
```

### Execução local e cópia

Reconfirme o kickoff no dia. Se IND @ HOU continuar em **19/11/2026 às
22h15 de São Paulo**, conclua captura, build e selo até **20h00 (23h00 UTC)**.
Use os comandos a seguir após autorização explícita para uma execução.
Mantenha o relógio sincronizado.

```powershell
$ref = Read-Host 'Diretório do build canônico existente verificado'
$root = Split-Path -Parent $inputDir
$plan = Join-Path $root 'plan-licensed'
$bundle = Join-Path $root 'bundle-licensed-private'
$offline = Join-Path 'C:\Users\leona\Documents' 'NFL-Pregame-Offline\2026-11-IND-HOU-licensed'
.\.venv\Scripts\python.exe -B -m nfl_betting.pregame_capture plan --catalog $ref --licensed $inputDir --season 2026 --week 11 --game 2026_11_IND_HOU --lead-minutes 135 --output $plan
if ($LASTEXITCODE -ne 0) { throw 'Plano recusado.' }
$receipt = .\.venv\Scripts\python.exe -B -m nfl_betting.pregame_capture capture --plan $plan --output $bundle --authorized
$captureStatus = $LASTEXITCODE
$receipt
if ($captureStatus -ne 0) { throw 'Captura recusada. Preserve o diagnóstico privado.' }
$indexDigest = ($receipt | ConvertFrom-Json).index_sha256
# Guarde esse digest original em um registro separado da cópia.
.\.venv\Scripts\python.exe -B -m nfl_betting.pregame_capture verify --folder $bundle --expected-index $indexDigest
if ($LASTEXITCODE -ne 0) { throw 'Verificação recusada.' }
New-Item -ItemType Directory -Path (Split-Path -Parent $offline) -Force | Out-Null
.\.venv\Scripts\python.exe -B -m nfl_betting.pregame_capture restore --folder $bundle --expected-index $indexDigest --output $offline
if ($LASTEXITCODE -ne 0) { throw 'Restauração recusada.' }
```

O plano e o bundle completos são privados. `verify --calendar-summary`
emite apenas `game_id`, equipes, kickoff dos jogos elegíveis e metadados de
fonte, hora de captura, hash, licença, atribuição e transformações. Use esse
JSON para compartilhamento conforme a licença. Preserve o bundle privado
para restauração offline e `STRICT_AS_OF`. O modo licenciado é recusado em
`capture --for-actions`.

### Remanejamentos

Qualquer divergência resulta em `KICKOFF_CONFLICT_OR_UNVERIFIED`. Para
remanejar um jogo, use novo calendário licenciado, nova observação humana
e `--resolution` com evidência independente no formato oficial autorizado.
Seu manifesto inclui `supersedes_plan_sha256`, o hash do `plan.json`
anterior, cujo diretório entra por `--supersedes`. A resolução deve estar
disponível após o plano anterior e até o novo, que deve preceder o kickoff
antigo e respeitar o cutoff recalculado. A referência pode conter o kickoff
antigo quando coincidir com o plano anterior. O novo build precisa
confirmar o horário revisado. Use novos destinos para plano e captura.

## Um único piloto no modo oficial autorizado

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
