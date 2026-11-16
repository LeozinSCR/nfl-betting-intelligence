# Tarefa 2 — estrutura executável e testes

Data: 16/11/2026. Base: `codex/initial-audit-2026-11-16`, commit `7d2bedaeb3d9747e6cead758fbab6c1a3a12bc24`. O PR #1 foi conferido aberto, draft e sem merge antes do trabalho. Esta branch é `codex/executable-structure-2026-11-16`; o PR da etapa aponta à branch da auditoria para isolar a revisão. Nenhuma alteração é feita na branch do PR #1.

## Resultado

Os 30 arquivos do ZIP foram extraídos na raiz. `pyproject.toml` configura o pacote em src/, instalação editable e CLI `nfl-ingest`. Ambiente de referência Python 3.12/Linux; dependências runtime/build fixadas com hashes, sem resolução adicional na instalação do pacote. Procedimento local completo no README.

Código/documentação evoluídos divergem do scaffold original; este permanece integral no ZIP e em `docs/FILE_MANIFEST.json`. O verificador histórico confirma o ZIP, manifesto e 19 entradas totais: ZIP, dois documentos de auditoria, dois Masters, 13 CSVs e relatório W10. Não foram corrigidos retrospectivamente valores, previsões, planilhas ou resultados. Nota de inventário: há 13 CSVs no ZIP; a menção a 14 CSVs no texto da auditoria inicial era um erro de contagem. O inventário por caminho e a auditoria original foram preservados.

As regras agora retornam erros estruturados em vez de tupla e exigem calendário e evidências temporais de disponibilidade. Bloqueiam desconhecidos/inativos/OUT/IR, mercados não individuais, duplicatas/contradições, jogos fora da data ou já iniciados, equipes incompatíveis e instabilidade explicitamente avaliada. Best exige 8 legs/4 jogos/2 props por jogo e teto 35; TD exige 4 em múltiplos jogos ou 2 em jogo único e teto 15. Total 50 e alocações zero são permitidos. A preferência de uma ou duas TDs por jogo gera aviso quando excedida, preservando a regra de negócio sem proibir expansões justificadas.

Probabilidades e odds rejeitam NaN/infinito/strings/booleanos e limites inválidos; probabilidades conjuntas respeitam Fréchet, incluindo regressão para o erro histórico. Quote exige origem HTTPS, provider/bookmaker, identificadores, correspondência à seleção, disponibilidade e validade/freshness. Shortlists podem omitir odds; cotações presentes nunca são ignoradas. EV é somente aritmética exploratória, com probabilidade de push explícita e decisão NO_BET. As antigas flags de aprovação foram removidas. Não há aprovação automática, construtor de apostas ou execução financeira.

A CLI de ingestão usa diretórios exclusivos e manifestos com checkpoints atômicos; mantém êxitos parciais e erros de import/rede/schema/escrita com exit 2. Contratos mínimos e ano são conferidos. O workflow coleta outcomes/logs e diagnóstico inclusive sem manifesto, publica artefato por 90 dias e propõe apenas diagnóstico em PR. Depois reprova o job caso alguma etapa tenha falhado. Não atualiza o Master/CSV nem faz merge. Workflows de testes/coleta e ações externas estão versionados, com SHAs de ações verificados.

O exportador Stake mantém snapshots por execução, filtra odds inválidas e conserva origem/horários/JSON integral do evento. Não preenche expiração ou mapeamento ausentes. É read-only e seus CSVs não são Quotes aprovadas. Documentação corrigiu caminhos, localização do relatório W10 e alegações obsoletas sobre a conectividade da API.

## Verificações locais

Ambiente criado do zero em `.venv`, Python 3.12.14. Instalação:

```text
python -m pip install --require-hashes -r requirements.lock         OK
python -m pip install --no-deps --no-build-isolation -e .           OK
python -m pip check                                               No broken requirements found
python -m unittest discover -s tests -v                           39 testes, OK
python tools/verify_history.py                                    SHA-256 OK
python -m compileall -q src tools tests                           OK
python -m nfl_betting.ingest_nflverse --help                       exit 0
nfl-ingest --help                                                 exit 0
python tools/stake_odds.py --help                                 exit 0
actionlint 1.7.12 -shellcheck= .github/workflows/*.yml              exit 0
```

Os testes cobrem estrutura, limites monetários, calendário São Paulo/UTC, partidas iniciadas, lesões/status desconhecidos, duplicatas, linhas/mercados, origem/freshness e binding de quote, odds/probabilidades inválidas, Fréchet, separação da aprovação financeira, import/rede/schema/ano/escrita com falha, êxito parcial, diretórios exclusivos, ausência/corrupção/ambiguidade de manifesto, integridade histórica e exportação/cota local Stake sem HTTP.

Todas as respostas, preços e falhas injetados nos testes são sintéticos. Nenhuma nova chamada NFLverse/Sleeper/Stake foi necessária nesta etapa; os estados reais documentados vêm da evidência original da auditoria. Não apresentar os resultados offline como certificação dos provedores ou de CI remoto. Actionlint verificou os dois workflows localmente; shellcheck não foi usado. A execução remota de Actions e permissões efetivas de upload/criação de PR continuam sujeitas à configuração do GitHub; não foram acionadas manualmente nesta tarefa.

Dados históricos têm CRLF e uma linha final em branco no relatório original. `.gitattributes` preserva esses bytes e exclui esse material histórico da checagem de whitespace. Não foi aplicada formatação para “corrigir” dados legados.

## Pendências que bloqueiam a operação

1. Recuperar dados brutos/geradores históricos e reconciliar 89 registros sem correspondência e 325 identidades/posições incompletas. As inconsistências de QA e a probabilidade conjunta inválida seguem preservadas e documentadas, não reparadas silenciosamente.
2. Backtesting cronológico reproduzível, elegibilidade pré-jogo sem viés de participação, calibração por mercado/faixa e validação conjunta de combinadas completas. Nenhum modelo foi promovido.
3. Integração de inativos oficiais, crosswalk temporal GSIS/PFR/Sleeper, autenticidade e completude das evidências de calendário/disponibilidade. Os validadores locais não autenticam URLs nem substituem os adaptadores de fontes.
4. Stake **ainda não demonstrou cobertura de player props ou Anytime TD**. Faltam binding canônico, política verificável de validade e liquidação/void/SGP, rate limiter persistente entre execuções e eventual alternativa licenciada identificada por bookmaker. Não há adaptador Sleeper implementado.
5. Ativar/revisar workflows na branch padrão após aprovação humana, verificar permissões de Actions/PR e disponibilizar armazenamento durável além dos 90 dias. Coleta técnica não certifica rodada completa ou fonte atualizada; reconciliar antes de qualquer atualização do Master.

O projeto ficou executável/testável para pesquisa no ambiente de referência. Continua sem prontidão para operação financeira, sem apostas reais e sem merge automático.
