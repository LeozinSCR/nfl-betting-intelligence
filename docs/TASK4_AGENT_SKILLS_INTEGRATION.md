# Task 4 — Agent Skills e infraestrutura de pesquisa

16/11/2026, America/Sao_Paulo. Base: PR #3 aberto, draft e sem merge,
`codex/canonical-database-2026-11-16`, SHA
`5db23551462408399f6b17a37737ab5704e732d9`; encadeado ao PR #2.
Trabalho isolado em `codex/agent-skills-infrastructure-2026-11-16`.
Foram lidos os seis documentos solicitados, módulos, SQL, manifests, catálogo,
testes e workflows. Auditorias e evidências anteriores permanecem intactas.

## 1. Inventário e revisão das candidatas

Repositórios públicos foram clonados somente para inspeção, sem executar
instaladores. `reports/task4_2026-11-16/external_inventory.json` fixa commits,
SHA-256 de cada SKILL.md, licença, scripts auxiliares e imports inspecionados.
Os nove SKILL.md abaixo foram lidos integralmente. Outros diretórios dos
repositórios não são implicitamente aprovados.

| Origem / commit | Candidatas | Resultado |
|---|---|---|
| [Machina Sports](https://github.com/machina-sports/sports-skills/tree/edc22197fb05a00bbf07fe224457fb9466b247c6) `edc2219` | nfl-data; betting | Inspecionadas; não instaladas/ativadas |
| [WalrusQuant](https://github.com/WalrusQuant/sports-analytic-skills/tree/0f90d2463b7d4c793821cce71fc82d06fcb06a3c) `0f90d24` | validation-design; feature-rules; leakage-audit; calibration-check; statistical-modeling; simulation-sports | Repositório **disponível**, sports-ds 0.12.0; metodologia aproveitada como referência, runtime não adotado |
| [Crawlora](https://github.com/Crawlora-org/crawlora-skills/tree/250c4b400989c7f4976e9505ff4fd4f04b52cda2) `250c4b4` | sports-betting-research | Helper/rotas revistos; não integrado por falta de cobertura/autenticação demonstrada |

## 2. Licenças, segurança e dependências

Os três repositórios usam MIT; hashes das licenças estão no inventário.
MIT cobre código, não concede direitos sobre dados ESPN, NFLverse ou bookmakers.
Não houve cópia de código externo para o runtime nem novo pacote no lock.

Machina 0.40.6: requests/feedparser e extras NFL nflreadpy/pyarrow/pandas;
Python >=3.9.10, provider diferente em 3.9. Nosso Python 3.12 suporta o extra
moderno, mas instalar `all` agregaria dependências e superfícies de trading
Kalshi/Polymarket desnecessárias. Import do pacote raiz carrega muitos módulos;
por isso o ensaio isolou arquivos de cálculo revisados, sem importar o pacote.
O loader NFLverse já usa nossa fonte; sua conversão pandas adicionaria custo
sem demonstrar nova cobertura. O fallback de temporada implícita e a instrução
de match por nome+equipe da skill são incompatíveis com nossos contratos.

Walrus declara Python >=3.10 e dependências amplas, sem versões exatas:
numpy, pandas, scipy, scikit-learn, statsmodels, matplotlib, polars, pyarrow e
nflreadpy. Os helpers leem tabelas fornecidas pelo usuário e podem gravar
relatórios/ajustar modelos. Não executar os caminhos de ajuste nesta tarefa.
Ajuda/import de 12 scripts foi ensaiada com Python 3.12, `-I -S`, ambiente sem
credenciais e audit hook negando rede, processos e escrita. Onze passaram;
`feature-rules/scripts/legality_report.py --help` falhou por importar pandas
antes de tratar argumentos. Falha preservada, sem instalação automática.

Crawlora: bash+curl, chave `CRAWLORA_API_KEY` obrigatória, host fixo
api.crawlora.net, GET e allowlist, arquivo temporário de autenticação modo 600,
sem chave na linha de processo. Helpers rejeitam método/body/path traversal;
não foram adotadas rotas de conta, execução, carteira ou pagamento. API SaaS
continua sujeita a termos e créditos próprios, distintos da licença MIT.

O probe público ESPN retornou HTTP 200 antes da conclusão da revisão de termos.
A página de [termos Disney](https://disneytermsofuse.com/english/) consultada
contém restrições a extração por scripts/robôs e uso de conteúdo para IA.
**Conector ESPN rejeitado para integração recorrente**; não houve novas chamadas
após essa constatação, redistribuição do corpo bruto ou incorporação ao banco.
Resposta pública bem-sucedida não é autorização de uso recorrente. A revisão não
certifica direitos de redistribuição ou contratos comerciais de qualquer fonte.

## 3. Comparativo funcional e ganho demonstrado

| Capacidade | Externa | Infraestrutura / decisão |
|---|---|---|
| Calendário/rosters/stats/PBP NFL | Machina ESPN + nflverse | NFLverse canônico já implementado; sem ganho de cobertura demonstrado |
| ESPN injuries/depth chart/news | Machina | Sem integração: termos, IDs distintos e timestamp precisam revisão |
| Conversão de odds e de-vig proporcional | Machina betting | Aritmética conferida em fixtures; sem incorporar runtime ou chamar resultado de probabilidade calibrada |
| EV/Kelly | Machina | EV exploratório já existe em rules.py; Kelly/alocação e recomendação automática rejeitados |
| Dependência/parlays | Machina | Produto das marginais + blend positivo até min(p); não estima correlação nem suporta dependência negativa; rejeitado para o protocolo |
| Record/replay | Machina `_replay.py` | SHA de corpo/Parquet e miss offline; falhas transitórias não são gravadas. Nosso manifesto já retém erros, corpos, cobertura e código; manter implementação existente |
| Features/leakage/walk-forward | Walrus | Adotadas como referências metodológicas nos gates da skill; matrizes/helpers produtivos adiados |
| Calibração/Brier/Log Loss | Walrus | Cálculo puro conferido; helper retorna manual-review-required, não aprovação; avaliação real depende da Task 5 |
| Modelos GLM / simulação | Walrus | Guias úteis; scripts não executados para ajuste/simulação. Simulador usa jogos independentes; não comprova SGP correlacionada |
| Odds multi-book/props | Crawlora | Catálogo documenta FanDuel player/props e DraftKings mercados; não comprova NFL/Anytime TD na resposta real |
| Snapshot/consulta local | Skill interna | Oito tarefas fixas, bounded, parametrizadas, read_only, recibo de snapshot; zero dependência nova |

Não foi demonstrado ganho estatístico, lucro ou nova base por instalar skills.
Ganho operacional medido: 8 consultas controladas, 23 testes novos, consulta
real de 15 jogos reproduzível e bundle local de 30 arquivos verificado.

## 4. Adoção e rejeições

Adotada **uma skill operacional própria** em
`.agents/skills/nfl-betting-intelligence/SKILL.md`, com referências de consultas
/gates metodológicos e helper mínimo. O formato usa frontmatter `name` e
`description`, referências relativas e scripts delegando ao pacote instalado;
não depende de MCP externo ou gerenciador de skills de outro fornecedor.
Descoberta da skill pelo cliente Codex pode exigir nova sessão; helper/import,
frontmatter e uso local foram testados, sem afirmar ativação automática na UI.

Nenhuma skill externa foi instalada, vendorizada ou habilitada no runtime.
Walrus serviu de referência metodológica para a Task 5. Math/replay Machina não
justificaram duplicação; loader NFL é redundante e ESPN não foi aprovado.
Crawlora fica pendente de chave, termos/custo por endpoint e cobertura real;
não sugerir compra como consequência automática desta avaliação.

## 5. Testes reais e evidências

- Baseline: **59/59** testes anteriores passaram antes das alterações.
- Suíte ampliada: **82/82**, Python 3.12.14; includes fronteiras de consulta,
  SQL injection, snapshot/cutoff, truncamento, no network, skill helper,
  envelopes temporais, ausência de origem, payload adulterado, NO_BET,
  archive/relocation/tampering e falhas parciais de publicação.
- `pip check`, `tools/verify_history.py` e actionlint passaram; nenhum hash
  histórico mudou. Dependências do runtime não foram ampliadas.
- `external_math_probe.json`: conversões para sete odds decimais e quatro
  entradas inválidas; de-vig sintético 1.90/1.90 -> 0.5/0.5; Walrus Brier 0.025
  em quatro casos sintéticos, bins totalizam quatro e verdict manual review.
  Processo `-I -S`, sem credenciais, rede/processos/escrita negados; bloqueio de
  rede explicitamente testado. **Não são odds NFL nem avaliação de modelo.**
- `external_import_probes.json`: onze helps OK, um erro pandas retido. Não
  comprova execução completa de construção de features, backtest, GLM ou MC.
- Consulta real via **helper da skill**, 16/11 às 20:05:10 BRT de cutoff:
  games 2026 REG W9 -> **15 linhas**. Snapshot
  `20261116T223417.397919Z-bad6b6c4485f4a3a8e7f08f03e046808`;
  recibo completo `internal_skill_real_query.json` inclui hashes e código dirty
  durante desenvolvimento. Não atribuir execução a um commit posterior.
- ESPN W9 ->15 eventos e 15 pares de equipes coincidem com calendário canônico;
  sem join de atletas ou substituição de fonte. Somente diagnóstico agregado
  e hash de resposta versionados em `public_source_probes.json`.
- Crawlora helper sem chave termina antes do curl, exit1; GET público de
  `/espn/scoreboard?sport=football&league=nfl` sem autenticação -> **401**.
  Site docs/pricing ->200. Pricing anuncia 2.000 créditos/mês gratuitos,
  menor plano pago $9/mês/20.000 créditos e cobrança ponderada por endpoint em
  respostas 2xx. Isso é anúncio consultado, não custo efetivo medido desta rota.
  Não houve cadastro, fornecimento de chave, compra ou resposta de props/TD.
- Arquivo local independente: exportação de raw+canonical validou ligação dos
  manifests e hashes declarados, copiou **30 arquivos**, verificou catálogo
  e relocação. Digest em `local_archive_verification.json`. Scratch local
  **não é armazenamento durável contratado**.

Procedimento reproduzível: README/OPERATIONS, mesmos commits externos e script
`reports/task4_2026-11-16/external_readonly_probe.py` (ajustar apenas paths dos
clones revisados). Não rodar scripts externos recém-atualizados sem nova revisão.

## 6. Arquitetura da skill e integração DuckDB

`SKILL.md -> scripts/query.py -> nfl_betting.research -> canonical.open_database`
abre catálogo materializado somente leitura após hash. Query catalog permite
somente games/players/snaps/usage/teams/injuries/matchups/identities, parâmetros
SQL, season/week/type/cutoff explícitos, limite máximo 500, total e truncamento.
Cada resposta tem snapshot ID, SHA de manifesto/DB, fingerprint do código,
cutoff e decision=NO_BET; não há SQL livre nem API externa no caminho.

`available_at <= cutoff` é obrigatório. Fonte capturada em novembro não pode
ser consultada antes da coleta para simular setembro. CLI é descritiva: ainda
não produz matriz de features/registro de projeções. Filtros impossíveis falham;
auditoria antiga não possui season_type e esse limite é explícito. Semanas,
IDs e equipes não são preenchidos por futuras linhas ou similaridade de nome.

A skill documenta QB/lesões/posição, snaps vs routes, red zone, dois pontos e
laterais, dependência, odds verificadas e gates de modelo. Construção de
parlays continua exclusivamente pelos validadores de rules.py: Best <=R$35,
>=4 jogos/2 props cada/8 legs; TD <=R$15, >=4 em múltiplos jogos ou2 em único;
total <=R$50 e zero permitido. Validar estrutura não muda aprovação financeira.

`pregame.py` fornece contrato de envelope para inativos/status/depth/QB/market/
quote: origem HTTPS sem credenciais, captura/validade/publicação quando
conhecida, ID, payload hash e cutoff anterior ao kickoff. Quotes delegam ao
contrato existente. Envelope válido **não autentica fato ou fornecedor**;
retorna facts_verified=false/NO_BET. Adapters permanecem UNCONFIGURED; ainda
faltam validação de equipes/IDs do fornecedor, inativos oficiais, assinatura
/proveniência confiável e consultas reais antes de uso produtivo.

## 7. Identidades e persistência

Consulta real da auditoria retém **2.619 linhas PENDING**:
2.598 SNAP_ID_UNRESOLVED (PFR ausente no roster), 11 ROSTER_GSIS_MISSING,
10 STATS_GSIS_MISSING. `identity_classification.json` fixa snapshot/hash e
classificação. **Zero resoluções novas**; não apareceu crosswalk temporal
adicional confiável. Nenhuma exclusão, alteração retroativa ou matching por nome.

`python -m nfl_betting.archive export --raw RAW --canonical BUILD --destination NOVO`
verifica hashes/ligação e exporta cópia exclusiva; `verify --folder ARCHIVE
--expected-catalog SHA` verifica a cópia, recusando adulterações/paths inseguros.
Transportar o digest por canal independente; hashes não são assinaturas. Não
substitui política de backup, autenticação de fornecedor ou storage remoto.

Proposta durável: object storage privado S3/compatível com versionamento,
retenção/lifecycle explícitos, criptografia, bloqueio contra exclusão e catálogo
append-only. Chave por season/run/content SHA; publicar índice somente depois
de verificar todos os objetos e fazer restore em outro ambiente. Git recebe
índices/manifests pequenos, não raws/DB grandes. Actions exporta bundle e
escreve nele via OIDC restrito ao repositório/ref/environment/prefixo; sem chave
permanente nem permissão de apagar versões. Administrador define provedor,
bucket, orçamento, IAM/OIDC, retenção, acesso e revisão dos termos de dados.
**Nenhum bucket, identidade cloud ou job de upload durável foi criado.**

## 8. Workflow semanal e permissões

PR #3 registrou falha real “GitHub Actions is not permitted to create or approve
pull requests”. Nesta tarefa a criação de PR do bot foi removida, assim como
contents/write e pull-requests/write; fica **contents: read**. Não se alterou
Settings para contornar a restrição.

Diagnósticos/manifests/raw/banco/logs continuam no artefato 90 dias. Nova etapa
`publish_refresh.py` grava recibo e `GITHUB_STEP_SUMMARY` com URL efetiva do
artefato e outcomes; PR_OUTCOME=NOT_REQUESTED é explícito. Outro artefato
preserva o recibo após upload. Falhas de instalação/teste/ingestão/build/upload
/recibo continuam fatais após guardar evidências; PARTIAL de dados não vira
aprovação. Links/status são sanitizados, sem inserir exceptions/segredos no
Markdown. A publicação padrão **não exige ação administrativa adicional**.

Ensaio remoto da alteração será registrado em `workflow_validation.json` antes
de concluir o PR. Agenda só roda na branch padrão após integração; nenhuma
branch foi integrada. Para reativar PRs automáticos no futuro, administrador
precisaria autorizar a política de criação de PRs e revisar permissões do token;
isso é opcional, não requisito da alternativa implementada.

## 9. Limitações remanescentes

NFLverse continua fonte canônica testada com seis feeds; snapshot aqui consultado
W1–W9 completos e W10 13/14, não dados em tempo real. Sleeper não ganhou
conector novo: ID disponível vem do roster NFLverse. Stake mantém a evidência
anterior de mercados de equipes, **sem cobertura demonstrada de player props
ou Anytime TD**. Odds de FanDuel/DraftKings não são preços Stake.

Persistem 2.619 pendências, ausência de vintages pré-jogo, titulares/inativos,
routes, preços utilizáveis, modelos calibrados e arquivo cloud durável.
Helpers externos não demonstram nova base ou validação. Falha grave antes do
checkout/Python ou cancelamento do runner pode impedir diagnóstico do job.
Não foram treinados modelos, recomendadas/executadas apostas, movimentados
recursos ou atualizados Masters. Nenhum modelo promovido; NO_BET.

## 10. Proposta para a Task 5

1. Fixar contrato temporal/coorte e adquirir snapshots realmente pré-jogo;
   concluir arquivo durável com restore auditado e IDs pendentes por fonte ID.
2. Implementar catálogo de features com source/event/available_at, shifts,
   políticas null/zero/ST-only, joins e teste de perturbação futura.
3. Fixar folds por jogo cronológicos, embargo, baselines simples, métricas,
   intervalos e holdout final antes de qualquer ajuste.
4. Reconstruir geradores legados e comparar targets/jardas/TD fora da amostra;
   versionar todos os resultados, inclusive negativos, com Brier/Log Loss/MAE,
   bins, incerteza e segmentos, sem autorização automática.
5. Só após evidência suficiente, avaliar calibração aninhada e dependências
   conjuntas/SGP com limites e sensibilidade; registro e revisão explícita de
   modelo, separado da validade estrutural e de qualquer execução financeira.
