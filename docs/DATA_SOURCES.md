# Fontes externas: estado documentado e limites

Atualização de documentação: 16/11/2026, Tarefa 2. As sondagens reais abaixo são da **auditoria inicial**, registradas em `CODEX_INITIAL_AUDIT_EVIDENCE.json`; não são novas consultas desta etapa nem prova de dados em tempo real. Os testes desta etapa são offline.

| Fonte | Estado do código | Última evidência verificável | Pendência |
|---|---|---|---|
| NFLverse / nflreadpy | CLI instalada, seis loaders, snapshots e contratos mínimos | Na auditoria: schedules 272; stats 10.376; PBP 26.071; snaps 13.913; injuries 3.168; rosters 24.565. W10 parcial, 13/14 jogos com placar/PBP | Reconciliação, cobertura por jogo e snapshots pré-jogo; origem resolvida/publicação por fonte |
| Sleeper | Nenhum adaptador implementado; cadastro não é feed oficial de inativos | Na auditoria: GET público retornou HTTP 200 e 12.229 jogadores | Adaptador com cache diário, crosswalk temporal e licenciamento conforme uso |
| NFL oficial | Referências/documentação; sem scraping | Termos consultados; nenhum injury report/inativo individual foi revalidado | Mecanismo permitido/licenciado e validação pré-jogo |
| Stake | Exportador público read-only experimental, sem conta/apostas | Na auditoria: 14 partidas e 498 seleções de equipes; **zero player props e Anytime TD observados** | Cobertura desses mercados não demonstrada; IDs de jogador/linha, validade, suspensão, preços de SGP e cota horária compartilhada |
| The Odds API | Candidata documentada; sem adaptador/chave/consulta autenticada | Documentação de props/alternativas/histórico localizada na auditoria | Licença/plano e resposta real. Manter bookmaker original; nunca chamar preço de outra casa de Stake |

A presença de `props: true` na resposta Stake não prova que player props vieram em `offers`. Não inventar endpoints privados nem contornar bloqueios. O exportador preserva o JSON bruto, rejeita preços não finitos/tipos inválidos e não preenche expiração que não veio da fonte. CSV exportado não satisfaz sozinho o contrato de Quote e não libera EV/aposta.

## Documentação e licença

- [nflreadpy](https://nflreadpy.nflverse.com/api/load_functions/): código MIT. [NFLverse](https://github.com/nflverse) / [dados](https://github.com/nflverse/nflverse-data/blob/main/LICENSE.md): maioria CC-BY 4.0, FTN com condições específicas CC-BY-SA 4.0; verificar por dataset e preservar atribuição.
- [Sleeper](https://docs.sleeper.com/) / [cadastro público](https://api.sleeper.app/v1/players/nfl): API sem token, uso gratuito não comercial; uso comercial exige licença própria. Cache do cadastro, no máximo uma captura diária. Status não substitui inativo oficial.
- [NFL termos](https://www.nfl.com/legal/terms): acesso público não autoriza coleta sistemática ou redistribuição. Não há conector oficial implementado nesta entrega.
- [Stake API](https://sportsbook-api.stake.com/): auditoria encontrou limite documentado de quatro chamadas/hora sem chave. O limite do script é por processo e não coordena várias execuções/IPs. Não rodar repetidamente. Chaves só por mecanismo oficial e variáveis de ambiente; não usar cookies ou tokens pessoais.
- [The Odds API](https://the-odds-api.com/liveapi/guides/v4/): acesso/plano, licença e mercados ainda precisam ser verificados com resposta real.

Não presumir APIs ESPN estáveis/oficiais. Não há autorização de redistribuição ampla inferida da conectividade dos endpoints.

## Identidade e qualidade

GSIS/PFR/Sleeper precisam de tabela temporal versionada; nomes não bastam. Separar snaps ofensivos, defensivos e special teams, jogadores inativos, ativos sem snaps ofensivos, ativos com zero oportunidades e desconhecidos. Não transformar ausência em zero. Targets/carries convencionais excluem conversões de dois pontos. Routes/TPRR/YPRR continuam não verificados no histórico.

Fonte atualizada não substitui os arquivos congelados W1–W9/W10 parcial nem corrige retroativamente previsões. Novas coletas ficam separadas, com hashes e diagnósticos, até reconciliação revisada. Ver `OPERATIONS.md` e `VALIDATION_CONTRACT.md`.

## Evidência adicional da Tarefa 3

A coleta real de 16/11/2026 foi repetida de ponta a ponta com captura dos corpos HTTP, origem resolvida, headers disponíveis e hashes. A cobertura segue W1–W9 e 13/14 jogos W10, com 149 resultados. Crosswalk usa GSIS/PFR/Sleeper do roster por semana/equipe; não há consulta nova à API Sleeper nem à Stake. Ver `TASK3_DATA_RECONCILIATION.md` para 89 aliases resolvidos, 325 identidades recuperadas e 2.619 pendências mantidas. Essa evidência de coleta é distinta das sondagens da auditoria inicial descritas acima.


## Revisão de skills externas (Task 4)

Machina/Walrus/Crawlora foram inspecionados, sem instalação produtiva ou
substituição NFLverse. ESPN respondeu à consulta pública W9, mas seu conector
recorrente não foi adotado após revisão dos termos. Crawlora sem chave retornou
401; catálogo não comprova props NFL/Anytime TD, timestamps ou custo efetivo de
uma cotação. Sleeper/Stake permanecem com o estado documentado; nenhum novo
adapter pré-jogo ou cobertura Stake de player props foi demonstrado. Evidências,
commits, licenças e limites em `TASK4_AGENT_SKILLS_INTEGRATION.md`.
