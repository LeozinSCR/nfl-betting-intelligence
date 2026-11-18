# Operação de pesquisa e diagnósticos

## Fluxo local

Instalar com o lock conforme README, executar os testes e a verificação histórica pela raiz. Testes usam fixtures sintéticas e não fazem chamadas de NFLverse, Sleeper ou Stake. A coleta real é uma ação separada:

```bash
python -m nfl_betting.ingest_nflverse --season 2026 --out data/raw_auto
```

A CLI aceita as seis fontes documentadas. Cada execução usa timestamp com microssegundos e UUID, diretório exclusivo e manifesto atualizado atomicamente durante a execução. Ao finalizar, o snapshot não é reutilizado. Fontes que falharam têm tipo/mensagem de exceção; fontes bem-sucedidas conservam arquivos/hashes. Uma falha de import também é registrada. Contratos mínimos cobrem identificadores, ano, semana e alguns campos essenciais; não substituem análise de completude por jogo, reconciliação PBP/weekly, inativos, qualidade e modelos.

`status=OK` significa somente que as fontes solicitadas passaram pela coleta/contratos mínimos. `source_updated_at` e `resolved_download_url` ficam null quando indisponíveis; não se substitui publicação por horário de captura. Manifestos registram versões e documentação do loader. Revisões externas continuam possíveis. Nada é gravado no Master ou sobre os CSVs históricos.

## GitHub Actions

- `tests.yml`: em push/PR, instalação com hashes, pacote local, pip check, suíte offline, integridade histórica e help da CLI. Não coleta dados ao vivo.
- `weekly_refresh.yml`: terça 13:00 UTC (10h São Paulo) e execução manual. Só ganha agendamento após integração à branch padrão e permissões de Actions. Não foi ativado por merge nesta tarefa.
- Instalação/testes/coleta mantêm `outcome` verdadeiro, com `continue-on-error` apenas para permitir coleta do diagnóstico. Dependências das etapas impedem ingestão se os testes falharem.
- `refresh_diagnostics.py`, sem dependências externas, roda com `always()`: inclui status de todas as etapas, run URL, manifesto completo e hash, hashes de logs e diagnóstico explícito `NO_MANIFEST` quando necessário. Manifesto ausente/corrompido/múltiplo resulta em ERROR.
- Upload `always()` preserva brutos, banco, manifests e logs por **90 dias**. A Task 4 remove a tentativa de PR do bot e usa `contents: read`: a restrição que falhou no PR #3 não bloqueia essa alternativa.
- `tools/publish_refresh.py` registra outcomes e URL real do artefato em recibo, publica `GITHUB_STEP_SUMMARY` e declara PR_OUTCOME=NOT_REQUESTED. Um segundo artefato guarda o recibo. Falhas de estágios/upload/publicação/recibo deixam o job vermelho; PARTIAL permanece diagnóstico de dados.
- O padrão não cria branch/PR, não atualiza Master e não exige elevar permissões. Administrador só precisa revisar autorização de PRs do bot se essa opção for reintroduzida no futuro.
- Ações de terceiros fixadas em SHAs verificados; atualizar esses SHAs somente com revisão. Jobs têm timeout e a coleta semanal não é cancelada por outra execução.

A retenção de Actions **não é arquivo permanente**. Transferência para armazenamento durável e catálogo de snapshots ainda são pendências. Falhas graves anteriores ao checkout/Python, cancelamento forçado ou indisponibilidade do próprio GitHub podem impedir o diagnóstico dentro do job; verificar a execução no GitHub.

O [piloto V1.7](TASK10_PREGAME_EVIDENCE_CAPTURE_PILOT.md) acrescenta
planejamento e recibos por jogo, restauração offline e consumo certificado
no `STRICT_AS_OF`. O workflow separado usa disparo manual. A execução local
é o padrão enquanto armazenamento gratuito e redistribuição não estiverem
confirmados.

O modo local `NFLVERSE_LICENSED` usa a release versionada de calendário
NFLverse e registra a conferência humana à parte. Siga o [PowerShell do
piloto licenciado](TASK10_PREGAME_EVIDENCE_CAPTURE_PILOT.md#calendário-nflverse-licenciado-para-uso-local)
após verificar a base de retenção integral dos brutos. Guarde o plano e o
bundle fora de pastas sincronizadas. Para compartilhar somente os fatos
licenciados do calendário, use `verify --calendar-summary`.

## Reproduzir falha de ingestão sem rede

A suíte `test_ingestion.py` injeta loaders com erro de rede/import, tabela vazia, schema inválido, ano errado e falha de escrita. Demonstra que um êxito parcial continua disponível e o exit é 2. `test_no_manifest_setup_or_test_failure_is_auditable` cobre a ausência do próprio manifesto. Para inspecionar manualmente uma dessas falhas sintéticas (fora dos históricos):

```bash
python - <<'PY'
from nfl_betting.ingest_nflverse import collect

def offline(_):
    raise ConnectionError('SYNTHETIC_OFFLINE_TEST')

path, code = collect(2026, 'data/raw_auto', ['pbp'], loaders={'pbp': offline})
print(path.read_text())
raise SystemExit(code)
PY
```

Esse procedimento retorna exit 2 esperado e cria diagnóstico de **teste sintético**, não um incidente observado em NFLverse. Para gerar o resumo de uma execução real, usar diretório contendo apenas esse run:

```bash
python tools/refresh_diagnostics.py --raw-root data/raw_auto --install success --tests success --ingest failure --output reports/local_ingestion_diagnostic.json
```

Na rotina de CI, o checkout é novo e contém uma única coleta. Localmente, diretório com várias coletas é ambíguo e o resumo reprova: copie a árvore `2026/<run-id>/` pretendida para diretório separado antes de resumir. Os outcomes acima são exemplos; nunca declarar `success` sem conferir o exit real.

## Preservação

`docs/FILE_MANIFEST.json` é o manifesto original do ZIP e permanece idêntico. Código/documentação evoluídos na raiz podem divergir legitimamente dele; não regenerar o manifesto para apagar a referência original. `docs/HISTORICAL_PRESERVATION.json` fixa os arquivos históricos, ZIP e auditoria inicial que não devem mudar nesta etapa. `tools/verify_history.py` verifica ambos os conjuntos.

Nenhuma ingestão libera modelos. Persistem NO_BET, backtests sem geradores completos, uma previsão conjunta histórica inválida e cobertura não demonstrada de player props Stake. Operação financeira, liquidação, integração Sleeper, crosswalk temporal e atualização do Master exigem trabalho posterior e revisão.

## Exportação web estática

Selecione um build canônico pelo manifesto e siga o fluxo de geração,
validação e publicação local em [web/README.md](../web/README.md).
`nfl_betting.web_export` arquiva cada combinação de versão, fonte, rodada e
cutoff em pasta exclusiva. Depois da validação e dos testes, o operador pode
atualizar o `slate.json` da raiz. Os arquivos contêm estatísticas derivadas e
diagnósticos de cobertura. EV permanece null e a decisão é NO_BET.

A V1.4 aceita evidências imutáveis selecionadas explicitamente por `--evidence`.
O [relatório da V1.4](TASK7_WEB_V1_4_PLAYER_COVERAGE.md) descreve a captura
separada de roster e horário, a revisão de transações e o fallback opcional.

## Tarefa 3: construção e reconciliação canônica

`nfl-canonical` / `python -m nfl_betting.canonical` faz a coleta e construção em pastas exclusivas, ou recebe `--snapshot` para reprocessar uma coleta específica. URLs/headers/corpos HTTP são capturados na sessão do loader, sem cache; versões e hashes acompanham o run. Resultados futuros/inconsistência de calendário, chaves duplicadas, identidade ambígua e adulteração de hashes bloqueiam o build. Falha da fonte injuries permite banco vazio tipado e PARTIAL, com diagnóstico; fontes essenciais ausentes resultam ERROR. Exit 2 permanece em erro de coleta ao vivo, mesmo que seja possível preservar um banco parcial.

O workflow semanal tem etapa `canonical` independente para aproveitar evidência parcial da coleta. Artefatos retêm 14 Parquets, DB, raws, auditoria e logs por90 dias. A Task 4 substitui a publicação via PR pela alternativa acima; a evidência da falha passada permanece no relatório da Task 3.

Consultar `docs/TASK3_DATA_RECONCILIATION.md` e `reports/task3_2026-11-16/evidence_index.json` para a execução real, pendências e evidência de validação remota. As evidências históricas anteriores permanecem preservadas; os novos manifests não substituem os originais.

## Task 4: skill, consultas e arquivo verificável

Manual: `.agents/skills/nfl-betting-intelligence/SKILL.md`. Após instalar o pacote:

```bash
python -m nfl_betting.research --database /BUILD --task games --season 2026 --week 9 --cutoff 2026-11-16T23:05:10+00:00
python -m nfl_betting.research --help
python -m nfl_betting.archive export --raw /RAW --canonical /BUILD --destination /NOVA_COPIA
python -m nfl_betting.archive verify --folder /NOVA_COPIA --expected-catalog SHA_IMPRESSO_NA_EXPORTACAO
```

O exemplo é pesquisa histórica e não cutoff pré-jogo. Guarde a resposta JSON
com snapshot/hash/código em arquivo novo; não reutilize relatórios antigos.
Arquivo local verificado não é backup remoto durável: persistir o bundle e o
digest independente antes de expirar Actions, com provedor/IAM/retenção definidos
pelo administrador. Não adicionar raws ou DuckDB ao Git. Proposta completa em
`TASK4_AGENT_SKILLS_INTEGRATION.md`. Integrações pré-jogo continuam UNCONFIGURED.
