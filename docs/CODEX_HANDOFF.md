> Documento histórico da migração. O original permanece no ZIP. Para a implementação executável da Tarefa 2 e estado atualizado das fontes, consultar README.md, docs/TASK2_IMPLEMENTATION.md e docs/DATA_SOURCES.md. As tarefas e alegações abaixo não comprovam execução atual.

# Contexto para iniciar o projeto no Codex

Você é o engenheiro de dados, analista quantitativo e revisor de qualidade de um sistema NFL de player props. Prioridade: **reprodutibilidade, validade prospectiva, checks de lesão, equivalência de linhas, honestidade estatística, sourcing**. Não fabrique stats, odds, acesso a APIs, probabilidade calibrada ou performance de investimentos.

## Histórico
Foram realizadas 33 fases em ChatGPT. Há Master V1.1 (Phase33) com 22 abas, PBP 2026, stats semanal até W9 e um piloto W10. Base revisada após encontrar 57 discrepâncias por 2-point-conversions. Backtests indicaram que modelos complexos de TD e parlays não superam robustamente baselines. Modelos ainda exploratórios. Dados do piloto incluem apostas *não executadas*; não tratar watchlists como stake real.

## Regras do usuário, obrigatórias
- Orçamento padrão por rodada: R$50, dividido R$35 Best Parlay, R$15 TD Parlay, mas nunca obrigar apostar.
- Best Parlay: no mínimo 4 jogos **distintos**, ao menos 2 player props **por cada jogo**, portanto mínimo absoluto de 8 legs. Pode adicionar games e legs apenas com ganho evidenciado; nunca montar 4 legs em 2 jogos.
- TD Parlay: quando dia tem 2+ partidas, 4+ Anytime TDs em jogos diferentes, distribuídos 1–2 por jogo; dia com somente 1 partida, 2 TDs.
- Mercado elegível precisa existir e ter odd real da Stake ou ser reportado como análise sem EV. Priorizar odds/edge, não linhas artificiais de 1.10. Prioridade exploratória de 1.6-2.1, mas maximizar robustez ajustada ao preço, não odds em si.
- Nunca escolher jogador IR/OUT. Verificar estabilidade de QB, OL, usage, mudanças de roster e adversário. Times instáveis podem ser excluídos como fonte de seleção sem excluir automaticamente seus adversários.
- Relatórios: ranking e probabilidade/intervalos com critérios claros, cenário base e contra, matchup, por que acerta e perde; elegibilidade; odds e horário; correlações; retorno e risco; fonte verificável.

## Tarefas imediatas
1. Execute suite de testes e revise este scaffold; abra PR 1 com reorganização técnica sem mudar o baseline.
2. Teste `nflreadpy` para 2026 (weekly/PBP/snaps/injuries/rosters), apresente cobertura e discrepâncias; confira atribuição da semana e tudo que foi corrigido.
3. Faça pipeline com DuckDB/Parquet e evidência timestamped; compare baselines W8-W9 vs walkforward W10+ sem leakage.
4. Integre odds read-only apenas se a API Stake estiver de fato acessível, testando cobertura de todos os mercados e respeitando rate limits; adicione fonte alternativa licenciada quando necessário.
5. Atualize a rotina agendada com PR, logs e status; se houver falha, faça PR com diagnóstico e sem dados falsos.
6. Estabeleça critérios de aprovação quantitativa por mercado; sem evidência, `NO_BET`.
7. Desenhe painel mobile responsivo ou markdown report revisável via GitHub Mobile.

## Limitações e exceções
- `Stake` conector original apenas sintaxe testada e acesso não confirmado.
- Excel legado é referência, não código-fonte das projeções; trabalhar com scripts e tabelas versionadas.
- A fonte de snaps de 2026 não foi importada no histórico, precisa ser testada novamente.
- Algumas probabilidades e dados anteriores tiveram erros e inconsistências; reproduzir antes de confiar. Não presumir que tudo no Master é validado.
