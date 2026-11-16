# Catálogo de consultas

`python -m nfl_betting.research --help` funciona sem rede. A instalação editable
pela raiz é obrigatória para o helper. `nfl-research` é a mesma interface.

| task | Tabela | Uso |
|---|---|---|
| games | games | calendário/resultado; team filtra mandante ou visitante |
| players | player_week | posição QB, participação, oportunidades; filtro GSIS |
| snaps | snap_counts | offense/defense/ST separados; não routes |
| usage | offensive_opportunities | eventos, yardline e classificação |
| teams | team_week | agregados de equipe/EPA/success rate |
| injuries | injuries | relatório semanal; não inativos |
| matchups | defensive_matchups | defesa/posição; team filtra defense |
| identities | reconciliation_audit | somente PENDING; preserva evidência original |

Todas exigem season/week/cutoff aware; opcionais team/player-id; limite 1..500,
contagem total e flag truncated. Filtros inexistentes são rejeitados. Auditoria
não possui season_type no schema legado: o filtro não se aplica nessa tarefa;
ela deve ser usada para diagnóstico de registros, nunca seleção de atletas.
Consultas retornam apenas available_at <=cutoff; snapshot tardio não reconstitui
pré-jogo passado. NÃO alterar available_at para obter linhas.

Registrar JSON completo da resposta, incluindo hash do manifesto/DB e código.
O próprio manifesto não é assinatura criptográfica: transportar seu digest por
canal independente ao arquivar. Valores de publicação desconhecidos seguem null.
Para projeções, depth charts, inativos e cotações: interface futura sem adapter
produtivo; `pregame.unavailable` devolve UNCONFIGURED/NO_BET.
