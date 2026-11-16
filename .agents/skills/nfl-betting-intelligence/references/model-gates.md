# Preparação da Task 5 — ainda sem treinamento

Definir e versionar antes de ajustar: target, unidade jogador-jogo, mercado,
cutoff exato, coorte elegível, fontes/snapshots, versão de liquidação, baseline,
features e regra de disponibilidade. Null/zero e ST-only precisam política.

Registrar para cada feature: source/event_time/available_at, IDs, lookback,
shift, missingness, revisões e transformações ajustadas só no treino. Snapshot
coletado em novembro não prova disponibilidade em setembro. Sem vintages
pré-jogo, classificar estudo retrospectivo exploratório.

Fixar folds cronológicos agrupados por partida; ambos os lados e jogadores da
mesma partida ficam no mesmo fold. Train labels devem estar disponíveis antes
do primeiro cutoff de teste. Tuning e calibração só em folds internos anteriores;
reservar holdout final. Testar perturbação futura e cardinalidade de joins.

Comparar baselines no mesmo conjunto elegível; guardar todos os folds e falhas.
Métricas: Brier, Log Loss, MAE targets/jardas, curvas e contagem por bin, intervalos
por blocos de jogos, drift por semana/posição/mercado. ECE agregado não basta.
Preservar resultados negativos e controlar escolha de jogadores/zeros.

Simulação correlacionada exige modelo conjunto identificável, seeds, cenários,
limites matemáticos, validação fora da amostra e sensibilidade; produto de
marginais ou blend arbitrário não prova dependência. Remoção de vig normaliza
preços de um mercado completo; não demonstra qualidade de um modelo.

Nenhuma skill ou checklist certifica calibração por si só. Registro de modelo e
critérios de aprovação permanecem por implementar e revisar. Resultado atual:
NO_BET, financial_approved=false, statistical_approved=false.
