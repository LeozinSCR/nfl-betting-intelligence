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
- Upload `always()` preserva dados brutos, manifestos, diagnóstico e logs por **90 dias**, antes da tentativa de PR. O job termina falhando se instalação, testes ou ingestão falharem. Falha do próprio upload/PR também mantém o job vermelho.
- O PR propõe apenas `reports/latest_nflverse_ingestion.json`. Não propõe atualização automática dos históricos ou modelos e não faz auto-merge. A branch `automation/nflverse-weekly` é reutilizada; uma execução posterior pode atualizar o PR existente. Cada run mantém artefato separado e link para logs.
- Permissões necessárias: contents/write e pull-requests/write; habilitar “Allow GitHub Actions to create and approve pull requests” quando a política da organização permitir. Sem isso, o artefato/log ainda existe, mas a criação de PR pode falhar. Não declarar publicação bem-sucedida sem URL real.
- Ações de terceiros fixadas em SHAs verificados; atualizar esses SHAs somente com revisão. Jobs têm timeout e a coleta semanal não é cancelada por outra execução.

A retenção de Actions **não é arquivo permanente**. Transferência para armazenamento durável e catálogo de snapshots ainda são pendências. Falhas graves anteriores ao checkout/Python, cancelamento forçado ou indisponibilidade do próprio GitHub podem impedir o diagnóstico dentro do job; verificar a execução no GitHub.

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

## Tarefa 3: construção e reconciliação canônica

`nfl-canonical` / `python -m nfl_betting.canonical` faz a coleta e construção em pastas exclusivas, ou recebe `--snapshot` para reprocessar uma coleta específica. URLs/headers/corpos HTTP são capturados na sessão do loader, sem cache; versões e hashes acompanham o run. Resultados futuros/inconsistência de calendário, chaves duplicadas, identidade ambígua e adulteração de hashes bloqueiam o build. Falha da fonte injuries permite banco vazio tipado e PARTIAL, com diagnóstico; fontes essenciais ausentes resultam ERROR. Exit 2 permanece em erro de coleta ao vivo, mesmo que seja possível preservar um banco parcial.

O workflow semanal tem etapa `canonical` independente para aproveitar evidência parcial da coleta. Os artefatos incluem o catálogo, 14 Parquets, auditoria completa e raw HTTP, por 90 dias. O diagnóstico diferencia PARTIAL de ERROR; PARTIAL não significa nenhuma aprovação. O recibo posterior às etapas de upload/PR guarda URLs e outcomes efetivos, inclusive se a política do GitHub bloquear a criação de PR. O job não encobre essa falha. Os dois manifests de diagnóstico podem ser propostos em PR; não há mudança no Master.

Consultar `docs/TASK3_DATA_RECONCILIATION.md` e `reports/task3_2026-11-16/evidence_index.json` para a execução real, pendências e evidência de validação remota. As evidências históricas anteriores permanecem preservadas; os novos manifests não substituem os originais.
