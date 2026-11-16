# Stake — exportador experimental somente leitura

Consulta apenas os endpoints públicos já presentes no pacote original, documentados em [sportsbook-api.stake.com](https://sportsbook-api.stake.com/). Não acessa conta, saldo ou execução de apostas.

A auditoria de 16/11/2026 conseguiu obter esportes/torneios/partidas e 498 seleções de equipes em 14 partidas. **Player props e Anytime TD não foram observados.** Essa evidência é pontual e não comprova integração operacional ou dados em tempo real; testes desta etapa são sintéticos, sem novas consultas.

A partir da raiz, com Python 3.12:

```bash
python tools/stake_odds.py --help
# Consulta real opcional, respeitando o orçamento de chamadas compartilhado:
python tools/stake_odds.py --out data/odds_snapshots
```

Cada execução cria subpasta exclusiva `<out>/stake-<timestamp>-<uuid>/`, evitando sobrescrever respostas anteriores. Saídas: `stake_raw.json`, `stake_offers.csv` e, em coleta normalizada, `stake_normalization.json`. Em falha, respostas já recebidas ficam preservadas; se nenhuma resposta chegou, consultar stderr/exit 1. Exit 0 descreve exportação, nunca cobertura aprovada ou sinal de aposta.

O CSV guarda URL, provedor/casa, captura, `lastUpdatedAt` quando disponível, kickoff e JSON do evento. Odds string, booleanas, ≤1 e não finitas são rejeitadas para diagnóstico de normalização; o JSON bruto preserva a resposta original. Disponibilidade exige oferta open e seleção explicitamente available=True. IDs continuam externos: não há mapeamento de jogador, linha, lado ou equivalência de jogo canônico. `binding_status=UNMAPPED_RESEARCH_ONLY`; `valid_until` fica vazio porque a fonte não forneceu expiração. Uma camada posterior deve estabelecer binding e validade com evidência antes de passar por `validate_quote`; não preencher com dados inventados.

Sem chave: cota documentada de até quatro requisições/hora; o script usa até três e lê só a primeira página. `--max-requests` controla **apenas esta execução**, não as chamadas de outras execuções. IDs retornados anteriormente podem ser passados por `--sport-id`/`--tournament-id` para economizar chamadas. Sem NFL na primeira página, preservar JSON e investigar quando a cota permitir; não fabricar ID. Uma chave oficial pode ser lida de `SPORTSBOOK_API_KEY` localmente, mas não há SLA ou cota de chave presumidos pelo projeto. Paginação completa, rate limiter persistente e backoff continuam pendentes.

Não fornecer credenciais/cookies no chat. Não renomear odds de outra casa como Stake. Não usar JSON bruto ou CSV não mapeado como Quote pronta ou como autorização financeira.
