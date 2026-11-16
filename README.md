# NFL Betting Intelligence

Projeto Python de pesquisa auditável de player props NFL. **Não há modelo aprovado, execução de apostas ou integração operacional de player props Stake.** Validação estrutural e aritmética de EV não constituem aprovação estatística ou financeira.

A migração original está preservada em `NFL_Codex_GitHub_Migration_Starter.zip`. Os arquivos foram extraídos para a raiz; CSVs, Masters e relatório histórico permanecem idênticos aos originais. A auditoria inicial está em [docs/CODEX_INITIAL_AUDIT.md](docs/CODEX_INITIAL_AUDIT.md); ela descreve o estado anterior à extração. O manifesto original descreve o ZIP, não os hashes do código atual.

## Instalação e testes pela raiz

Ambiente de referência: **Python 3.12, Linux x86-64**. Requer internet para instalar dependências; os testes são offline. Não é necessário fornecer odds, tokens ou acessar APIs para executá-los.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pip check
python -m unittest discover -s tests -v
python tools/verify_history.py
python -m nfl_betting.ingest_nflverse --help
nfl-ingest --help
```

`requirements.lock` fixa dependências diretas, transitivas e build backend, com hashes. `requirements.txt` inclui esse lock. A instalação usa o backend já fixado, sem resolver novas dependências. `pyproject.toml` instala `nfl_betting` a partir de `src/`; os imports novos usam `nfl_betting`, não `src.nfl_betting`. O antigo caminho de módulo `python -m src.nfl_betting.ingest_nflverse` permanece possível na raiz, mas os contratos das funções de regras mudaram: consulte [VALIDATION_CONTRACT.md](docs/VALIDATION_CONTRACT.md).

Para atualizar o lock intencionalmente (revisar diff e repetir testes; não faz parte da rotina semanal), use uv 0.13.6:

```bash
uv pip compile pyproject.toml requirements-build.in --generate-hashes --python-version 3.12 --output-file requirements.lock
```

## Estrutura

| Caminho | Finalidade |
|---|---|
| `src/nfl_betting/` | Coletor NFLverse e regras estruturais/numéricas |
| `tests/` | Testes offline com fixtures sintéticas e verificações dos históricos |
| `tools/stake_odds.py` | Exportador read-only experimental, sem cobertura comprovada de player props |
| `tools/refresh_diagnostics.py` | Diagnóstico de CI, inclusive sem manifesto de ingestão |
| `tools/verify_history.py` | SHA-256 dos históricos, auditoria e manifesto original |
| `legacy/` | Master Phase33 (22 abas) e Phase32 preservados |
| `data/processed/`, `data/reference/` | Histórico congelado W1–W9, W10 parcial; não são dados atuais |
| `reports/W10_206_selections.md` | Relatório histórico exploratório, não apostas executadas |
| `docs/` | Auditoria, fontes, contratos, operação e preservação |
| `.github/workflows/` | Testes offline e coleta semanal com diagnóstico/PR |

## Coleta independente

```bash
python -m nfl_betting.ingest_nflverse --season 2026 --out data/raw_auto
# Para uma sondagem menor, sem modificar o histórico:
python -m nfl_betting.ingest_nflverse --season 2026 --sources schedules --out data/raw_auto
```

Cada execução grava em `data/raw_auto/2026/<timestamp-uuid>/`. O manifesto registra início/fim, versões, contratos mínimos de schema, semanas observadas, hashes e erros por fonte. Exit 0 significa coleta sem falhas técnicas; **não certifica semana completa, reconciliação ou prontidão de modelos**. Exit 2 indica falha, com respostas parciais preservadas quando possível. Se nem o diretório puder ser criado, a CLI retorna erro em stderr; o workflow registra a ausência de manifesto. Não grava em `legacy/` ou substitui CSVs existentes. As URLs resolvidas de download e timestamps de publicação permanecem pendentes, explicitamente null.

## Regras e limites

- Best Parlay: teto R$35, mínimo de quatro jogos, duas player props por cada jogo e oito legs. Pode expandir; não há preenchimento automático de seleções.
- TD Parlay: teto R$15, quatro Anytime TDs em múltiplos jogos ou dois em dia de jogo único. Uma ou duas por jogo é preferência; excesso gera aviso, sem impor limite não solicitado.
- Total máximo R$50; zero é permitido. Não há obrigação de apostar.
- Sem fontes válidas de disponibilidade de jogador/mercado, calendário e contexto, a seleção é reprovada. OUT/IR/inativo/desconhecido bloqueiam. A avaliação de estabilidade aplica-se à equipe selecionada.
- Shortlists podem omitir odds; cotações fornecidas são sempre verificadas estruturalmente. Para calcular EV exploratório, origem, identidade, validade temporal e probabilidade explícita de push são obrigatórias.
- `ValidationResult.valid` significa somente estrutura válida. `decision` permanece `NO_BET`; `financial_approved` e `statistical_approved` permanecem False. Não existe executor financeiro.

## APIs e automação

O [estado das fontes](docs/DATA_SOURCES.md) diferencia sondagens da auditoria e implementação atual. Na última evidência registrada, NFLverse respondeu às seis fontes e Sleeper ao cadastro; a Stake retornou somente mercados de equipes, sem player props ou Anytime TD. Nenhuma nova sondagem é feita pelos testes.

O workflow semanal propõe um diagnóstico revisável, inclusive em erro, e mantém o job vermelho se a ingestão falhar. Não faz merge, não atualiza o Master e não executa apostas. Requer que os workflows sejam integrados à branch padrão e que Actions permita criação de PRs. Detalhes de retenção, permissões e reprodução de falhas estão em [OPERATIONS.md](docs/OPERATIONS.md).

`NFL_historical_sources_2026.zip`, PBP/weekly originais e geradores dos modelos continuam ausentes. Persistem a falha histórica de probabilidade conjunta, inconsistências de QA e falta de backtesting/calibração suficientes. Consulte [TASK2_IMPLEMENTATION.md](docs/TASK2_IMPLEMENTATION.md) para evidências desta etapa.

Nunca commitar credenciais. Snaps novos precisam de crosswalk temporal PFR/GSIS/Sleeper; não substituem routes run nem comprovam inativos oficiais.
