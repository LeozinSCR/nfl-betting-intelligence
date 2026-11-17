# MNF — Chargers @ Ravens — 16/11/2026

**Pesquisa descritiva; NO_BET. Sem probabilidade calibrada, EV afirmativo ou aprovação financeira.**

Modo: `PRE_GAME_RESEARCH`. Cutoff **2026-11-17T00:36:04+00:00** (21h36m04 de 16/11 em São Paulo); kickoff **01h15 UTC / 22h15 BRT**.
Snapshot `20261117T003403.829042Z-d5b317a4722848c7a32cc88e1edadc6b`; banco `PARTIAL`. Manifesto SHA `b6ba517750ec598f1ab41c29feb06261e5cc307e731c452fb233e3a631b0260d`.
Código base `338fb63d4e4d1cc2037cecd46c4b55345d81c065`, dirty=True; o JSON fixa hashes de cada arquivo executado e do gerador. Geração 2026-11-17T00:50:24.134398+00:00.

## Leitura prioritária

Brissett estreia por Baltimore: não há uma partida dele no ataque BAL na amostra. As séries com Lamar, Huntley e Fagnano não devem ser transportadas como se o regime fosse igual. Isso reduz a confiança em Flowers, Andrews e Henry, inclusive quando o volume histórico é alto. A instabilidade de BAL não exclui automaticamente os jogadores LAC.

Herbert oferece continuidade de QB, mas a ausência de McConkey e a volta de Njoku mudam a distribuição dos targets. Examinar Harris/Johnston e os TEs sem assumir que todos absorverão os alvos vagos. O backfield LAC divide oportunidades entre Hampton, Vidal e Mitchell; volume agregado não pertence integralmente ao titular.

## QBs, inativos e linha ofensiva

Herbert: elegível pelo roster ACT + lista oficial de inativos, previsto como QB LAC no calendário. O clube informou exames negativos na mão esquerda após W9. Elegibilidade não garante ausência de limitação nem snaps. Brissett: estreia anunciada pelo clube. Lamar Jackson e Tyler Huntley: IR oficial, excluídos. McConkey: inativo oficial. Njoku: explicitamente ativo após ativação da IR, mas função/minutos ainda incertos.

- **LAC**: Ladd McConkey, Kendall Williamson, Isas Waxter, Bud Dupree, Brenen Thompson, Justin Eboigbe.
- **BAL**: Elijah Sarratt, Jaylinn Hawkins, Chandler Rivers, Emery Jones Jr., Aeneas Peebles, Kedon Slovis (emergency third QB).

OL BAL: clube informou que Cam Jurgens segue center; Ryan Neuzil chega para profundidade/backup, com possível treino em guard. Emery Jones está inativo. O levantamento de snaps W8/W9 está no JSON, preservando IDs PFR não resolvidos. OL LAC: participação de Pipkins permanece PENDENTE nesta V1; não estar na lista de inativos não comprova ativação da IR. Awosika e mudanças recentes exigem cuidado; não há rating de pass-block ou titulares completos confirmados.

**Conflitos preservados:** o calendário NFLverse ainda lista Huntley como QB BAL e o roster lista Njoku RES. As publicações oficiais mais recentes substituem esses campos somente na camada de contexto deste relatório; nenhum registro canônico/histórico foi reescrito.

Fontes primárias lidas antes do cutoff:

- [lac_inactives](https://www.chargers.com/news/ravens-inactives-week-10-2026), publicação 2026-11-16T15:45:00-08:00; consulta anterior ou igual ao cutoff.
- [bal_inactives](https://www.baltimoreravens.com/news/ravens-inactives-chagers-shakeup-defense-practice-squad-nick-vannett-chris-moore-chandler-rivers), publicação 2026-11-16T18:57:00-05:00; consulta anterior ou igual ao cutoff.
- [bal_ir](https://www.baltimoreravens.com/news/lamar-jackson-tyler-huntley-injured-reserve-austin-reed-adisa-isaac-jake-moody), publicação 2026-11-05T16:35:00-05:00; consulta anterior ou igual ao cutoff.
- [herbert_update](https://www.chargers.com/news/justin-herbert-ladd-mcconkey-update-jim-harbaugh-trade-deadline), publicação 2026-11-09T16:30:00-08:00; consulta anterior ou igual ao cutoff.
- [lac_injury](https://www.chargers.com/news/chargers-vs-ravens-injury-report-ladd-mcconkey-daiyan-henley-2026), publicação 2026-11-15T11:45:00-08:00; consulta anterior ou igual ao cutoff.
- [bal_ol](https://www.baltimoreravens.com/news/ryan-neuzil-cam-jurgens-role-jaylinn-hawkins-returns-ravens-new-kicker-search), publicação 2026-11-11T17:54:00-05:00; consulta anterior ou igual ao cutoff.

## Shortlist de pesquisa para leitura rápida

Johnston receiving yards **Over24.5 hipotético** é a hipótese descritiva mais consistente nesta grade:5/7 na temporada e3/3 L3, com snap share alto. Harris receptions **Over2.5 hipotético** merece monitoramento pela ausência McConkey, mas há apenas2 jogos com participação na janelaL3. Nenhum desses limiares foi verificado como oferta atual.

Henry mantém prioridade na investigação de **Anytime TD** (16 carries dentro da5 e9 TDs observados), mas suas linhas publicadas de70+/80+ rush têm0/3 L3. Hampton é candidato de TD pelo papel acumulado, porém seu cenário rush Over24.5 passou só1/3 L3: classificado NEUTRO pelo guard de deterioração recente. Flowers e Andrews completam a shortlist de TD por targets na red zone, com ressalva explícita da estreia de Brissett; quatro nomes não significam quatro aprovações.

Game script é condicional: se LAC ficar atrás, pode haver mais passes sem melhorar eficiência; se BAL controlar o placar, carries Henry podem crescer, mas isso não é previsão do resultado. EPA/play L3: LAC≈-0.303 e BAL≈-0.290; EPA/dropback BAL L3≈-0.353. Henry70+ e Herbert200+ publicados são NEUTROS, não oportunidades de EV comprovado.


## Ataques: temporada, últimas 5 e últimas 3 partidas

EPA usa jogadas de scrimmage sem kneels/spikes/anuladas/dois pontos. Dropback inclui sacks/scrambles; rush EPA exclui scrambles. Success=EPA>0. Explosive=20+ em passe/10+ em corrida. Neutral pass=share de dropbacks, downs1/2, Q1–Q3, placar pré-jogada ±7. Pace abaixo é proxy do relógio, não métrica ajustada oficial. Denominadores e semanas no JSON.

|Time|Janela / jogos|EPA/play|EPA/DB|EPA/rush|Success|Explosive|Neutral pass (n)|Pace s (pares)|Pass att / rush plays / targets|Sacks / DB|QB hits|RZ plays|
|---|---|---|---|---|---|---|---|---|---|---|---|---|
|LAC|season / 8|-0.24|-0.24|-0.25|35.1%|7.9%|40.0% (200)|35.00 (352)|241 / 224 / 234|31.0 / 295|55.0|59|
|LAC|last5 / 5|-0.27|-0.30|-0.24|32.0%|7.2%|39.3% (107)|35.00 (227)|153 / 143 / 148|23.0 / 191|35.0|29|
|LAC|last3 / 3|-0.30|-0.28|-0.34|30.7%|5.8%|43.9% (57)|36.00 (138)|98 / 77 / 96|14.0 / 119|19.0|20|
|BAL|season / 9|-0.02|0.04|-0.08|44.1%|9.7%|49.5% (198)|39.00 (362)|245 / 258 / 240|23.0 / 289|51.0|83|
|BAL|last5 / 5|-0.17|-0.19|-0.15|38.1%|6.1%|49.1% (106)|39.00 (206)|142 / 136 / 138|16.0 / 168|38.0|40|
|BAL|last3 / 3|-0.29|-0.35|-0.21|35.9%|3.0%|54.8% (62)|39.00 (113)|79 / 79 / 76|9.0 / 92|22.0|20|

Contagens de passe acima excluem sacks; rush plays incluem scrambles. QB hits não são pressão: pressure rate, routes run, TPRR e YPRR não disponíveis. Para QBs, passing yards/attempts/completions vêm do feed semanal; métricas por QB e semana constam no JSON.

## Defesa contra posições

|Defesa|Posição|Jogos totais defesa|Targets|Recepções|Rec yds/jogo|Carries|Rush yds/jogo|TDs rush+rec|
|---|---|---|---|---|---|---|---|---|
|BAL|RB|9|50|36|17.22|204|81.56|9|
|BAL|TE|9|55|41|52.22|0|0.00|6|
|BAL|WR|9|169|110|172.44|5|1.78|7|
|LAC|RB|8|43|27|21.50|201|105.50|9|
|LAC|TE|8|46|33|51.12|1|0.00|1|
|LAC|WR|8|135|92|157.88|4|5.62|12|

Agregados descritivos por posição, sem ajuste por força do adversário, alinhamento ou defensor individual. As jardas de lateral são preservadas sem criar target. Snaps ofensivos não são routes.

## Ranking de hipóteses de player props

Linhas PUBLISHED são observações da página pública DraftKings, não Quotes executáveis. As demais são **cenários hipotéticos**, não mercados oferecidos. Frequência = hit/n em partidas com participação ofensiva confirmada; não é probabilidade futura nem calibrada. Temporada pode incluir ARI para Brissett; L5/L3 usam jogos de sua equipe atual, sem inventar amostra BAL. A rubrica FAVORÁVEL é apenas um filtro descritivo transparente (n>=5, frequência>=70%, sem guard de regime/função ou deterioração L3<50%), não teste de significância.

|#|Jogador / time|Mercado / linha|Origem|Temporada: distribuição e frequência|L5 hits/n|L3 hits/n|Classificação|
|---|---|---|---|---|---|---|---|
|1|Quentin Johnston / LAC|rec_yards Over 24.5|HIPOTÉTICA|n=7; média 37.14; mediana 40.00; faixa 7.00–58.00; 5/7 (71.4%)|4/4|3/3|FAVORÁVEL|
|2|Derrick Henry / BAL|rec_yards Over 24.5|HIPOTÉTICA|n=9; média 8.33; mediana 6.00; faixa 0.00–19.00; 0/9 (0.0%)|0/5|0/3|NEUTRO|
|3|Derrick Henry / BAL|receptions Over 2.5|HIPOTÉTICA|n=9; média 1.33; mediana 1.00; faixa 0.00–3.00; 1/9 (11.1%)|0/5|0/3|NEUTRO|
|4|Derrick Henry / BAL|rush_yards 70+|DK publicada|n=9; média 76.56; mediana 68.00; faixa 45.00–144.00; 4/9 (44.4%)|1/5|0/3|NEUTRO|
|5|Derrick Henry / BAL|rush_yards 80+|DK publicada|n=9; média 76.56; mediana 68.00; faixa 45.00–144.00; 3/9 (33.3%)|1/5|0/3|NEUTRO|
|6|Devontez Walker / BAL|rec_yards Over 24.5|HIPOTÉTICA|n=8; média 9.38; mediana 0.00; faixa 0.00–47.00; 1/8 (12.5%)|0/5|0/3|NEUTRO|
|7|Devontez Walker / BAL|receptions Over 2.5|HIPOTÉTICA|n=8; média 0.50; mediana 0.00; faixa 0.00–2.00; 0/8 (0.0%)|0/5|0/3|NEUTRO|
|8|Ja'Kobi Lane / BAL|rec_yards Over 24.5|HIPOTÉTICA|n=5; média 17.80; mediana 13.00; faixa 0.00–40.00; 2/5 (40.0%)|2/4|1/3|NEUTRO|
|9|Ja'Kobi Lane / BAL|receptions Over 2.5|HIPOTÉTICA|n=5; média 1.80; mediana 1.00; faixa 0.00–4.00; 2/5 (40.0%)|2/4|1/3|NEUTRO|
|10|Jacoby Brissett / BAL|completions Over 18.5|HIPOTÉTICA|n=8; média 24.12; mediana 25.50; faixa 10.00–38.00; 6/8 (75.0%)|0/0|0/0|NEUTRO|
|11|Jacoby Brissett / BAL|pass_attempts Over 29.5|HIPOTÉTICA|n=8; média 38.12; mediana 36.00; faixa 23.00–52.00; 6/8 (75.0%)|0/0|0/0|NEUTRO|
|12|Jacoby Brissett / BAL|pass_yards Over 199.5|HIPOTÉTICA|n=8; média 214.88; mediana 245.00; faixa 95.00–292.00; 5/8 (62.5%)|0/0|0/0|NEUTRO|
|13|Jacoby Brissett / BAL|rush_yards Over 24.5|HIPOTÉTICA|n=8; média 10.88; mediana 10.50; faixa 2.00–19.00; 0/8 (0.0%)|0/0|0/0|NEUTRO|
|14|Josh Cuevas / BAL|rec_yards Over 24.5|HIPOTÉTICA|n=9; média 14.89; mediana 14.00; faixa 0.00–44.00; 3/9 (33.3%)|3/5|1/3|NEUTRO|
|15|Josh Cuevas / BAL|receptions Over 2.5|HIPOTÉTICA|n=9; média 1.11; mediana 1.00; faixa 0.00–4.00; 1/9 (11.1%)|1/5|0/3|NEUTRO|
|16|Justice Hill / BAL|rec_yards Over 24.5|HIPOTÉTICA|n=9; média 12.33; mediana 10.00; faixa 0.00–26.00; 1/9 (11.1%)|1/5|1/3|NEUTRO|
|17|Justice Hill / BAL|receptions Over 2.5|HIPOTÉTICA|n=9; média 2.22; mediana 2.00; faixa 0.00–4.00; 4/9 (44.4%)|4/5|3/3|NEUTRO|
|18|Justice Hill / BAL|rush_yards Over 24.5|HIPOTÉTICA|n=9; média 26.67; mediana 15.00; faixa 0.00–85.00; 3/9 (33.3%)|2/5|1/3|NEUTRO|
|19|Mark Andrews / BAL|rec_yards Over 24.5|HIPOTÉTICA|n=9; média 26.33; mediana 24.00; faixa 4.00–49.00; 4/9 (44.4%)|1/5|0/3|NEUTRO|
|20|Mark Andrews / BAL|receptions Over 2.5|HIPOTÉTICA|n=9; média 3.44; mediana 3.00; faixa 1.00–6.00; 7/9 (77.8%)|3/5|2/3|NEUTRO|
|21|Rashod Bateman / BAL|rec_yards Over 24.5|HIPOTÉTICA|n=9; média 32.67; mediana 33.00; faixa 0.00–88.00; 5/9 (55.6%)|2/5|1/3|NEUTRO|
|22|Rashod Bateman / BAL|receptions Over 2.5|HIPOTÉTICA|n=9; média 2.22; mediana 2.00; faixa 0.00–7.00; 2/9 (22.2%)|1/5|0/3|NEUTRO|
|23|Zay Flowers / BAL|rec_yards 70+|DK publicada|n=8; média 76.75; mediana 75.00; faixa 0.00–150.00; 4/8 (50.0%)|1/5|1/3|NEUTRO|
|24|Zay Flowers / BAL|receptions Over 2.5|HIPOTÉTICA|n=8; média 5.38; mediana 5.50; faixa 0.00–8.00; 7/8 (87.5%)|4/5|2/3|NEUTRO|
|25|Charlie Kolar / LAC|rec_yards Over 24.5|HIPOTÉTICA|n=6; média 21.50; mediana 20.50; faixa 0.00–37.00; 2/6 (33.3%)|2/4|1/3|NEUTRO|
|26|Charlie Kolar / LAC|receptions Over 2.5|HIPOTÉTICA|n=6; média 2.17; mediana 3.00; faixa 0.00–3.00; 4/6 (66.7%)|3/4|2/3|NEUTRO|
|27|Derius Davis / LAC|rec_yards Over 24.5|HIPOTÉTICA|n=8; média 2.62; mediana 0.00; faixa 0.00–15.00; 0/8 (0.0%)|0/5|0/3|NEUTRO|
|28|Derius Davis / LAC|receptions Over 2.5|HIPOTÉTICA|n=8; média 0.25; mediana 0.00; faixa 0.00–1.00; 0/8 (0.0%)|0/5|0/3|NEUTRO|
|29|Justin Herbert / LAC|completions Over 18.5|HIPOTÉTICA|n=8; média 18.00; mediana 18.00; faixa 13.00–24.00; 4/8 (50.0%)|3/5|2/3|NEUTRO|
|30|Justin Herbert / LAC|pass_attempts Over 29.5|HIPOTÉTICA|n=8; média 29.38; mediana 29.00; faixa 23.00–37.00; 4/8 (50.0%)|3/5|2/3|NEUTRO|
|31|Justin Herbert / LAC|pass_yards 200+|DK publicada|n=8; média 198.88; mediana 198.50; faixa 121.00–257.00; 4/8 (50.0%)|2/5|2/3|NEUTRO|
|32|Justin Herbert / LAC|rush_yards Over 24.5|HIPOTÉTICA|n=8; média 23.75; mediana 21.50; faixa 2.00–54.00; 4/8 (50.0%)|3/5|1/3|NEUTRO|
|33|KeAndre Lambert-Smith / LAC|rec_yards Over 24.5|HIPOTÉTICA|n=3; média 27.33; mediana 32.00; faixa 0.00–50.00; 2/3 (66.7%)|2/3|2/3|NEUTRO|
|34|KeAndre Lambert-Smith / LAC|receptions Over 2.5|HIPOTÉTICA|n=3; média 2.00; mediana 1.00; faixa 0.00–5.00; 1/3 (33.3%)|1/3|1/3|NEUTRO|
|35|Keaton Mitchell / LAC|rec_yards Over 24.5|HIPOTÉTICA|n=8; média 12.88; mediana 16.00; faixa -5.00–34.00; 1/8 (12.5%)|1/5|1/3|NEUTRO|
|36|Keaton Mitchell / LAC|receptions Over 2.5|HIPOTÉTICA|n=8; média 2.25; mediana 3.00; faixa 0.00–5.00; 5/8 (62.5%)|4/5|2/3|NEUTRO|
|37|Keaton Mitchell / LAC|rush_yards Over 24.5|HIPOTÉTICA|n=8; média 22.25; mediana 17.50; faixa 4.00–52.00; 3/8 (37.5%)|2/5|1/3|NEUTRO|
|38|Kimani Vidal / LAC|rec_yards Over 24.5|HIPOTÉTICA|n=8; média 7.00; mediana 6.50; faixa -1.00–19.00; 0/8 (0.0%)|0/5|0/3|NEUTRO|
|39|Kimani Vidal / LAC|receptions Over 2.5|HIPOTÉTICA|n=8; média 1.25; mediana 1.00; faixa 0.00–3.00; 1/8 (12.5%)|1/5|1/3|NEUTRO|
|40|Kimani Vidal / LAC|rush_yards Over 24.5|HIPOTÉTICA|n=8; média 20.25; mediana 22.00; faixa 0.00–57.00; 3/8 (37.5%)|3/5|1/3|NEUTRO|
|41|Omarion Hampton / LAC|rec_yards Over 24.5|HIPOTÉTICA|n=8; média 7.88; mediana 6.50; faixa 0.00–21.00; 0/8 (0.0%)|0/5|0/3|NEUTRO|
|42|Omarion Hampton / LAC|receptions Over 2.5|HIPOTÉTICA|n=8; média 1.38; mediana 1.50; faixa 0.00–4.00; 1/8 (12.5%)|1/5|1/3|NEUTRO|
|43|Omarion Hampton / LAC|rush_yards Over 24.5|HIPOTÉTICA|n=8; média 46.12; mediana 44.00; faixa 18.00–94.00; 6/8 (75.0%)|3/5|1/3|NEUTRO|
|44|Oronde Gadsden II / LAC|rec_yards Over 24.5|HIPOTÉTICA|n=8; média 21.50; mediana 17.50; faixa 0.00–52.00; 3/8 (37.5%)|2/5|1/3|NEUTRO|
|45|Oronde Gadsden II / LAC|receptions Over 2.5|HIPOTÉTICA|n=8; média 2.38; mediana 2.00; faixa 0.00–5.00; 3/8 (37.5%)|3/5|2/3|NEUTRO|
|46|Quentin Johnston / LAC|receptions Over 2.5|HIPOTÉTICA|n=7; média 1.86; mediana 1.00; faixa 1.00–4.00; 2/7 (28.6%)|1/4|1/3|NEUTRO|
|47|Tre Harris / LAC|rec_yards Over 24.5|HIPOTÉTICA|n=7; média 37.43; mediana 31.00; faixa 6.00–76.00; 4/7 (57.1%)|2/4|1/2|NEUTRO|
|48|Tre Harris / LAC|receptions Over 2.5|HIPOTÉTICA|n=7; média 3.00; mediana 3.00; faixa 1.00–6.00; 5/7 (71.4%)|3/4|2/2|NEUTRO|
|49|David Njoku / LAC|rec_yards Over 24.5|HIPOTÉTICA|n=2; média 33.50; mediana 33.50; faixa 9.00–58.00; 1/2 (50.0%)|0/0|0/0|DADOS INSUFICIENTES|
|50|David Njoku / LAC|receptions Over 2.5|HIPOTÉTICA|n=2; média 3.00; mediana 3.00; faixa 1.00–5.00; 1/2 (50.0%)|0/0|0/0|DADOS INSUFICIENTES|
|51|Lamar Jackson / BAL|completions Over 18.5|HIPOTÉTICA|n=5; média 13.60; mediana 15.00; faixa 0.00–21.00; 1/5 (20.0%)|0/1|0/1|EVITAR|
|52|Lamar Jackson / BAL|pass_attempts Over 29.5|HIPOTÉTICA|n=5; média 19.40; mediana 20.00; faixa 1.00–31.00; 1/5 (20.0%)|0/1|0/1|EVITAR|
|53|Lamar Jackson / BAL|pass_yards Over 199.5|HIPOTÉTICA|n=5; média 193.40; mediana 222.00; faixa 0.00–324.00; 3/5 (60.0%)|0/1|0/1|EVITAR|
|54|Lamar Jackson / BAL|rush_yards Over 24.5|HIPOTÉTICA|n=5; média 28.80; mediana 34.00; faixa 0.00–50.00; 3/5 (60.0%)|0/1|0/1|EVITAR|
|55|Ladd McConkey / LAC|rec_yards Over 24.5|HIPOTÉTICA|n=6; média 47.67; mediana 50.50; faixa 0.00–86.00; 4/6 (66.7%)|1/3|1/2|EVITAR|
|56|Ladd McConkey / LAC|receptions Over 2.5|HIPOTÉTICA|n=6; média 2.83; mediana 3.50; faixa 0.00–5.00; 4/6 (66.7%)|1/3|1/2|EVITAR|

### Evidência individual: volume, participação e riscos

- **Justin Herbert (LAC, QB, GSIS 00-0036355)** — ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES; W6: 0 tgt/5 car, 100.0% snaps; W8: 0 tgt/4 car, 100.0% snaps; W9: 0 tgt/1 car, 79.0% snaps. RZ temporada: {'targets_inside20': 1, 'carries_inside20': 5, 'carries_inside5': 2, 'td_events': 0}. Favorece: Herbert tem continuidade de titular e algum volume em eventual placar adverso. Risco: 200+ em4/8; protecao/pass efficiency baixa e distribuicao sem McConkey; mao esquerda exige ressalva. McConkey fora e Njoku retorna: targets e snaps podem mudar; conferir função, sem somar ganhos projetados dos recebedores.
- **Jacoby Brissett (BAL, QB, GSIS 00-0033119)** — STARTER_OFFICIAL; sem participação ofensiva recente na equipe atual. RZ temporada: {'targets_inside20': 0, 'carries_inside20': 0, 'carries_inside5': 0, 'td_events': 0}. Favorece: Historico ARI oferece contexto descritivo de passes, nao projecao BAL. Risco: Zero jogos BAL; mediana ARI245 nao pode ser transferida como parametro calibrado. Nova distribuição com Brissett; nenhum jogo BAL com ele. Comparar splits de QB no JSON sem atribuição causal.
- **Lamar Jackson (BAL, QB, GSIS 00-0034796)** — IR_OFFICIAL; W8: 0 tgt/0 car, 2.0% snaps. RZ temporada: {'targets_inside20': 0, 'carries_inside20': 5, 'carries_inside5': 2, 'td_events': 1}. Favorece: Historico Lamar preservado para comparar regimes. Risco: IR OFICIAL: nao elegivel hoje; Brissett substitui, sem transportar mobilidade/eficiencia. Nova distribuição com Brissett; nenhum jogo BAL com ele. Comparar splits de QB no JSON sem atribuição causal.
- **Derrick Henry (BAL, RB, GSIS 00-0032764)** — ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES; W7: 2 tgt/17 car, 51.0% snaps; W8: 2 tgt/11 car, 45.0% snaps; W9: 0 tgt/17 car, 50.0% snaps. RZ temporada: {'targets_inside20': 1, 'carries_inside20': 40, 'carries_inside5': 16, 'td_events': 9}. Favorece: Henry concentra carries de goal line; revisar TD antes de jardas altas. Risco: 70+/80+ rush: nenhuma ultrapassagem L3; Brissett e game script mudam oportunidades. Nova distribuição com Brissett; nenhum jogo BAL com ele. Comparar splits de QB no JSON sem atribuição causal.
- **Justice Hill (BAL, RB, GSIS 00-0034975)** — ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES; W7: 4 tgt/3 car, 46.0% snaps; W8: 8 tgt/3 car, 49.0% snaps; W9: 3 tgt/9 car, 52.0% snaps. RZ temporada: {'targets_inside20': 2, 'carries_inside20': 1, 'carries_inside5': 0, 'td_events': 1}. Favorece: Hill participa do passe e teve nove carries em W9. Risco: Henry concentra goal line; nova hierarquia com Brissett ainda nao observada. Nova distribuição com Brissett; nenhum jogo BAL com ele. Comparar splits de QB no JSON sem atribuição causal.
- **Zay Flowers (BAL, WR, GSIS 00-0039064)** — ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES; W7: 11 tgt/0 car, 85.0% snaps; W8: 5 tgt/0 car, 82.0% snaps; W9: 6 tgt/3 car, 66.0% snaps. RZ temporada: {'targets_inside20': 7, 'carries_inside20': 1, 'carries_inside5': 0, 'td_events': 3}. Favorece: Flowers lidera targets e jardas BAL; volume pode sustentar recepcoes curtas. Risco: QB estreante no sistema; volume/jardas nao implicam touchdown. Nova distribuição com Brissett; nenhum jogo BAL com ele. Comparar splits de QB no JSON sem atribuição causal.
- **Rashod Bateman (BAL, WR, GSIS 00-0036550)** — ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES; W7: 4 tgt/0 car, 73.0% snaps; W8: 3 tgt/0 car, 76.0% snaps; W9: 2 tgt/0 car, 62.0% snaps. RZ temporada: {'targets_inside20': 3, 'carries_inside20': 0, 'carries_inside5': 0, 'td_events': 1}. Favorece: Oportunidades historicas preservadas por ID. Risco: Amostra/papel secundario; zeros e snaps nao provam volume futuro. Nova distribuição com Brissett; nenhum jogo BAL com ele. Comparar splits de QB no JSON sem atribuição causal.
- **Ja'Kobi Lane (BAL, WR, GSIS 00-0040870)** — ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES; W7: 5 tgt/0 car, 69.0% snaps; W8: 1 tgt/0 car, 65.0% snaps; W9: 0 tgt/0 car, 57.0% snaps. RZ temporada: {'targets_inside20': 6, 'carries_inside20': 0, 'carries_inside5': 0, 'td_events': 0}. Favorece: Oportunidades historicas preservadas por ID. Risco: Amostra/papel secundario; zeros e snaps nao provam volume futuro. Nova distribuição com Brissett; nenhum jogo BAL com ele. Comparar splits de QB no JSON sem atribuição causal.
- **Devontez Walker (BAL, WR, GSIS 00-0039792)** — ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES; W7: 0 tgt/0 car, 30.0% snaps; W8: 0 tgt/0 car, 16.0% snaps; W9: 0 tgt/0 car, 27.0% snaps. RZ temporada: {'targets_inside20': 1, 'carries_inside20': 0, 'carries_inside5': 0, 'td_events': 1}. Favorece: Oportunidades historicas preservadas por ID. Risco: Amostra/papel secundario; zeros e snaps nao provam volume futuro. Nova distribuição com Brissett; nenhum jogo BAL com ele. Comparar splits de QB no JSON sem atribuição causal.
- **Mark Andrews (BAL, TE, GSIS 00-0034753)** — ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES; W7: 4 tgt/0 car, 57.0% snaps; W8: 4 tgt/0 car, 57.0% snaps; W9: 2 tgt/2 car, 57.0% snaps. RZ temporada: {'targets_inside20': 7, 'carries_inside20': 0, 'carries_inside5': 0, 'td_events': 1}. Favorece: Andrews tem targets na red zone e uso como TE principal. Risco: Targets RZ nao se converteram regularmente em TD; disputa alvos com Flowers e outros TEs. Nova distribuição com Brissett; nenhum jogo BAL com ele. Comparar splits de QB no JSON sem atribuição causal.
- **Josh Cuevas (BAL, TE, GSIS 00-0040887)** — ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES; W7: 3 tgt/0 car, 22.0% snaps; W8: 2 tgt/0 car, 25.0% snaps; W9: 0 tgt/0 car, 16.0% snaps. RZ temporada: {'targets_inside20': 2, 'carries_inside20': 0, 'carries_inside5': 0, 'td_events': 1}. Favorece: Oportunidades historicas preservadas por ID. Risco: Amostra/papel secundario; zeros e snaps nao provam volume futuro. Nova distribuição com Brissett; nenhum jogo BAL com ele. Comparar splits de QB no JSON sem atribuição causal.
- **Omarion Hampton (LAC, RB, GSIS 00-0040666)** — ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES; W6: 4 tgt/7 car, 50.0% snaps; W8: 3 tgt/9 car, 30.0% snaps; W9: 0 tgt/13 car, 40.0% snaps. RZ temporada: {'targets_inside20': 0, 'carries_inside20': 18, 'carries_inside5': 4, 'td_events': 3}. Favorece: Hampton lidera carries LAC na temporada e tem uso de goal line. Risco: Cenario24.5 passou apenas1/3 L3; divide trabalho com Vidal/Mitchell; game script desfavoravel pode reduzir corridas. McConkey fora e Njoku retorna: targets e snaps podem mudar; conferir função, sem somar ganhos projetados dos recebedores.
- **Kimani Vidal (LAC, RB, GSIS 00-0039391)** — ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES; W6: 4 tgt/7 car, 37.0% snaps; W8: 2 tgt/8 car, 46.0% snaps; W9: 3 tgt/7 car, 39.0% snaps. RZ temporada: {'targets_inside20': 2, 'carries_inside20': 2, 'carries_inside5': 0, 'td_events': 2}. Favorece: Vidal tem participacao recente e oportunidades de passe. Risco: Backfield triplo; TDs observados sem carries dentro da5 nao comprovam papel de goal line. McConkey fora e Njoku retorna: targets e snaps podem mudar; conferir função, sem somar ganhos projetados dos recebedores.
- **Keaton Mitchell (LAC, RB, GSIS 00-0038454)** — ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES; W6: 1 tgt/2 car, 25.0% snaps; W8: 3 tgt/4 car, 31.0% snaps; W9: 4 tgt/7 car, 25.0% snaps. RZ temporada: {'targets_inside20': 2, 'carries_inside20': 5, 'carries_inside5': 0, 'td_events': 1}. Favorece: Mitchell teve aumento recente de carries/targets. Risco: Rodizio com Hampton/Vidal e ausencia de papel comprovado de goal line. McConkey fora e Njoku retorna: targets e snaps podem mudar; conferir função, sem somar ganhos projetados dos recebedores.
- **Quentin Johnston (LAC, WR, GSIS 00-0038544)** — ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES; W6: 3 tgt/0 car, 82.0% snaps; W8: 4 tgt/0 car, 82.0% snaps; W9: 4 tgt/1 car, 83.0% snaps. RZ temporada: {'targets_inside20': 0, 'carries_inside20': 0, 'carries_inside5': 0, 'td_events': 1}. Favorece: Johnston tem snap share recente alto e jardas L3 acima do cenario24.5. Risco: Poucas recepcoes e distribuicao de jardas volatil; ultimo TD longo nao e repetivel por suposicao. McConkey fora e Njoku retorna: targets e snaps podem mudar; conferir função, sem somar ganhos projetados dos recebedores.
- **Tre Harris (LAC, WR, GSIS 00-0040727)** — ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES; W8: 3 tgt/0 car, 51.0% snaps; W9: 7 tgt/0 car, 83.0% snaps. RZ temporada: {'targets_inside20': 4, 'carries_inside20': 0, 'carries_inside5': 0, 'td_events': 0}. Favorece: Harris jogou60 snaps e recebeu7 targets em W9; McConkey fora abre hipotese de volume. Risco: So duas participacoes na janelaL3; Njoku pode absorver parte dos alvos. McConkey fora e Njoku retorna: targets e snaps podem mudar; conferir função, sem somar ganhos projetados dos recebedores.
- **KeAndre Lambert-Smith (LAC, WR, GSIS 00-0040184)** — ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES; W6: 9 tgt/0 car, 87.0% snaps; W8: 0 tgt/0 car, 3.0% snaps; W9: 4 tgt/0 car, 56.0% snaps. RZ temporada: {'targets_inside20': 2, 'carries_inside20': 0, 'carries_inside5': 0, 'td_events': 0}. Favorece: Lambert-Smith teve snaps e quatro targets em W9. Risco: Papel oscilante; nao presumir absorcao integral dos alvos McConkey. McConkey fora e Njoku retorna: targets e snaps podem mudar; conferir função, sem somar ganhos projetados dos recebedores.
- **Derius Davis (LAC, WR, GSIS 00-0038573)** — ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES; W6: 0 tgt/1 car, 7.0% snaps; W8: 0 tgt/0 car, 5.0% snaps; W9: 2 tgt/0 car, 7.0% snaps. RZ temporada: {'targets_inside20': 1, 'carries_inside20': 0, 'carries_inside5': 0, 'td_events': 1}. Favorece: Oportunidades historicas preservadas por ID. Risco: Amostra/papel secundario; zeros e snaps nao provam volume futuro. McConkey fora e Njoku retorna: targets e snaps podem mudar; conferir função, sem somar ganhos projetados dos recebedores.
- **Ladd McConkey (LAC, WR, GSIS 00-0039915)** — INACTIVE_OFFICIAL; W6: 1 tgt/0 car, 12.0% snaps; W8: 6 tgt/0 car, 90.0% snaps. RZ temporada: {'targets_inside20': 2, 'carries_inside20': 0, 'carries_inside5': 0, 'td_events': 1}. Favorece: Historico preservado para auditoria. Risco: INATIVO OFICIAL: excluir hoje; W9 ativo sem jogar mostra limite de roster. McConkey fora e Njoku retorna: targets e snaps podem mudar; conferir função, sem somar ganhos projetados dos recebedores.
- **Oronde Gadsden II (LAC, TE, GSIS 00-0040189)** — ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES; W6: 5 tgt/0 car, 49.0% snaps; W8: 5 tgt/0 car, 48.0% snaps; W9: 3 tgt/0 car, 46.0% snaps. RZ temporada: {'targets_inside20': 6, 'carries_inside20': 0, 'carries_inside5': 0, 'td_events': 1}. Favorece: Gadsden tem alvos na red zone e snaps ofensivos recentes. Risco: Retorno Njoku pode reduzir papel; targets RZ nao garantem TD. McConkey fora e Njoku retorna: targets e snaps podem mudar; conferir função, sem somar ganhos projetados dos recebedores.
- **Charlie Kolar (LAC, TE, GSIS 00-0038046)** — ELIGIBLE_ROSTER_PLUS_OFFICIAL_INACTIVES; W6: 6 tgt/0 car, 66.0% snaps; W8: 4 tgt/0 car, 62.0% snaps; W9: 3 tgt/1 car, 65.0% snaps. RZ temporada: {'targets_inside20': 2, 'carries_inside20': 0, 'carries_inside5': 0, 'td_events': 0}. Favorece: Kolar tem snaps e targets recentes comprovados. Risco: Snaps podem ser bloqueio; Njoku/Gadsden concorrem; nao tratar snap share como routes. McConkey fora e Njoku retorna: targets e snaps podem mudar; conferir função, sem somar ganhos projetados dos recebedores.
- **David Njoku (LAC, TE, GSIS 00-0033885)** — ACTIVE_EXPLICIT_OFFICIAL; sem participação ofensiva recente na equipe atual. RZ temporada: {'targets_inside20': 1, 'carries_inside20': 0, 'carries_inside5': 0, 'td_events': 0}. Favorece: Njoku explicitamente ativo apos IR; pode modificar distribuicao de TE. Risco: Amostra curta e retorno sem limite de snaps/rotas confirmado; evitar extrapolar. McConkey fora e Njoku retorna: targets e snaps podem mudar; conferir função, sem somar ganhos projetados dos recebedores.

### Mudanças de QB observadas

|Time|Semana|QB|Dropbacks|EPA/DB|Pass yds|Sacks|
|---|---|---|---|---|---|---|
|BAL|1|L.Jackson|26|0.38|324|2.0|
|BAL|1|None|3|1.18|—|0.0|
|BAL|2|L.Jackson|33|0.10|235|3.0|
|BAL|2|None|4|0.08|—|0.0|
|BAL|3|L.Jackson|20|0.60|186|0.0|
|BAL|3|None|2|0.34|—|0.0|
|BAL|4|L.Jackson|22|0.53|222|2.0|
|BAL|4|T.Huntley|9|0.03|63|0.0|
|BAL|4|None|2|0.42|—|0.0|
|BAL|5|T.Huntley|35|-0.08|201|3.0|
|BAL|5|Z.Flowers|1|-0.72|—|1.0|
|BAL|5|None|2|-0.54|—|0.0|
|BAL|6|T.Huntley|34|0.14|165|3.0|
|BAL|6|None|4|0.18|—|0.0|
|BAL|7|T.Huntley|38|0.09|298|4.0|
|BAL|7|None|2|0.12|—|0.0|
|BAL|8|L.Jackson|1|-0.57|—|0.0|
|BAL|8|T.Huntley|5|-1.86|0|1.0|
|BAL|8|J.Fagnano|24|-0.43|91|3.0|
|BAL|8|None|1|-0.21|—|0.0|
|BAL|9|D.Henry|1|-1.20|-3|0.0|
|BAL|9|J.Fagnano|19|-0.82|60|1.0|
|BAL|9|None|1|1.00|—|0.0|
|LAC|1|J.Herbert|30|-0.19|209|3.0|
|LAC|1|None|5|-0.21|—|0.0|
|LAC|2|J.Herbert|30|-0.02|192|3.0|
|LAC|2|None|1|-0.26|—|0.0|
|LAC|3|J.Herbert|36|-0.18|226|2.0|
|LAC|3|None|2|0.02|—|0.0|
|LAC|4|J.Herbert|35|-0.23|189|4.0|
|LAC|4|T.Harris|1|-0.57|—|0.0|
|LAC|4|None|5|0.09|—|0.0|
|LAC|5|J.Herbert|28|-0.57|121|5.0|
|LAC|5|None|3|0.07|—|0.0|
|LAC|6|J.Herbert|41|-0.41|204|4.0|
|LAC|6|None|3|0.45|—|0.0|
|LAC|8|J.Herbert|33|-0.49|257|2.0|
|LAC|8|None|3|-0.04|—|0.0|
|LAC|9|J.Herbert|31|-0.10|193|8.0|
|LAC|9|D.Uiagalelei|7|0.16|24|0.0|
|LAC|9|None|1|0.31|—|0.0|

Targets por QB nos passes direcionados (mesmas exclusões PBP):

|Recebedor BAL|QB|Targets|Recepções|Jardas|
|---|---|---|---|---|
|Derrick Henry|L.Jackson|6|6|35|
|Derrick Henry|T.Huntley|7|5|34|
|Derrick Henry|J.Fagnano|1|1|6|
|Mark Andrews|L.Jackson|23|17|143|
|Mark Andrews|T.Huntley|14|9|61|
|Mark Andrews|J.Fagnano|6|5|33|
|Zay Flowers|D.Henry|1|1|-3|
|Zay Flowers|L.Jackson|20|16|353|
|Zay Flowers|T.Huntley|34|24|255|
|Zay Flowers|J.Fagnano|9|2|9|

Distribuição de targets por receiver ID/passser ID está no JSON. W8 BAL tem apenas um snap ofensivo de Lamar na fonte; não agrupar W8 inteiro como regime Lamar. Comparações são amostras desiguais, sem ajuste pelo adversário. Brissett tem histórico ARI separado, não há split pós-estreia BAL antes deste jogo.

## Anytime TD: ordem por oportunidades, sem quatro aprovações forçadas

Ordenação exploratória por 2×carries dentro da5 + targets dentro da20 + TDs observados. Não é xTD ou probabilidade; TD baixo/alto não altera automaticamente elegibilidade. Preferir revisar a posição na goal line, volume e qualidade do ataque.

|#|Jogador|Time|RZ targets / carries / GL<=5 (temporada)|TDs / jogos com TD / n|L3 RZ tgt/car/GL|Preço publicado DK|Classificação|
|---|---|---|---|---|---|---|---|
|1|Derrick Henry|BAL|1 / 40 / 16|9 / 6 / 9|0 / 8 / 1|-155|NEUTRO|
|2|Omarion Hampton|LAC|0 / 18 / 4|3 / 3 / 8|0 / 4 / 0|295|NEUTRO|
|3|Zay Flowers|BAL|7 / 1 / 0|3 / 3 / 8|2 / 0 / 0|165|NEUTRO|
|4|Mark Andrews|BAL|7 / 0 / 0|1 / 1 / 9|2 / 0 / 0|350|NEUTRO|
|5|Oronde Gadsden II|LAC|6 / 0 / 0|1 / 1 / 8|3 / 0 / 0|não observado|NEUTRO|
|6|Ja'Kobi Lane|BAL|6 / 0 / 0|0 / 0 / 4|3 / 0 / 0|não observado|NEUTRO|
|7|Justin Herbert|LAC|1 / 5 / 2|0 / 0 / 8|0 / 0 / 0|600|NEUTRO|
|8|Kimani Vidal|LAC|2 / 2 / 0|2 / 2 / 6|1 / 1 / 0|não observado|NEUTRO|
|9|Rashod Bateman|BAL|3 / 0 / 0|1 / 1 / 9|0 / 0 / 0|não observado|NEUTRO|
|10|Tre Harris|LAC|4 / 0 / 0|0 / 0 / 7|1 / 0 / 0|340|NEUTRO|
|11|Josh Cuevas|BAL|2 / 0 / 0|1 / 1 / 5|1 / 0 / 0|não observado|NEUTRO|
|12|Justice Hill|BAL|2 / 1 / 0|1 / 1 / 9|2 / 1 / 0|não observado|NEUTRO|
|13|Keaton Mitchell|LAC|2 / 5 / 0|1 / 1 / 8|1 / 2 / 0|não observado|NEUTRO|
|14|Charlie Kolar|LAC|2 / 0 / 0|0 / 0 / 5|2 / 0 / 0|não observado|NEUTRO|
|15|Derius Davis|LAC|1 / 0 / 0|1 / 1 / 5|1 / 0 / 0|não observado|NEUTRO|
|16|Devontez Walker|BAL|1 / 0 / 0|1 / 1 / 5|0 / 0 / 0|não observado|NEUTRO|
|17|KeAndre Lambert-Smith|LAC|2 / 0 / 0|0 / 0 / 2|2 / 0 / 0|não observado|DADOS INSUFICIENTES|
|18|David Njoku|LAC|1 / 0 / 0|0 / 0 / 2|0 / 0 / 0|750|DADOS INSUFICIENTES|
|19|Quentin Johnston|LAC|0 / 0 / 0|1 / 1 / 7|0 / 0 / 0|450|NEUTRO|
|20|Ladd McConkey|LAC|2 / 0 / 0|1 / 1 / 6|0 / 0 / 0|não observado|EVITAR|

Henry é o primeiro nome para investigar pela utilização próxima à end zone. As demais opções devem ser comparadas pela tabela: uso RZ, divisão de backfield, retorno de Njoku e troca de QB em BAL impedem transformar a shortlist em aprovações. Flowers/Andrews competem por chances de passe; Henry/Flowers/Andrews compartilham dependência do ataque BAL. Hampton/Vidal/Mitchell dividem jogo corrido LAC. Nenhuma multiplicação de marginais ou probabilidade conjunta foi calculada.

## Mercado observado e limites de execução

Stake: consulta pública única em 2026-11-17T00:35:36.827632+00:00; 14 eventos, 1 correspondente(s) a LAC–BAL. Mercados efetivamente retornados: 1st Half - 1x2, 1st Half - Asian Handicap, 1st Half - Asian Total, 1st Quarter - 1x2, 1st Quarter - Draw No Bet, 1st Quarter - Handicap, 1x2, 2nd Quarter - 1x2, 2nd Quarter - Draw No Bet, 2nd Quarter - Handicap, 3rd Quarter - 1x2, 3rd Quarter - Draw No Bet, 3rd Quarter - Handicap, 4th Quarter - 1x2, 4th Quarter - Draw No Bet, 4th Quarter - Handicap, Baltimore Ravens Total (Incl. Overtime), Halftime/Fulltime, Handicap (Incl. Overtime), Los Angeles Chargers Total (Incl. Overtime), Total (Incl. Overtime), Winner (Incl. Overtime). **Player props/Anytime TD não demonstrados** nessa resposta; não usar endpoints privados.

[Página pública DraftKings](https://dknetwork.draftkings.com/draftkings-sportsbook-player-props/) observada antes do cutoff; refresh anunciado de5min, porém sem timestamp individual/valid_until. Preços abaixo são indicativos publicados, com bookmaker correto; não são Stake, não comprovam disponibilidade atual/SGP e não passam sozinhos no contrato Quote.

|Jogador|Mercado / linha|Odd americana publicada|Bookmaker|
|---|---|---|---|
|Derrick Henry|rush_yards 70+|-180|DraftKings|
|Derrick Henry|rush_yards 80+|-119|DraftKings|
|Zay Flowers|rec_yards 70+|-143|DraftKings|
|Justin Herbert|pass_yards 200+|-115|DraftKings|
|Derrick Henry|anytime_td Anytime TD|-155|DraftKings|
|Zay Flowers|anytime_td Anytime TD|165|DraftKings|
|Omarion Hampton|anytime_td Anytime TD|295|DraftKings|
|Mark Andrews|anytime_td Anytime TD|350|DraftKings|
|Quentin Johnston|anytime_td Anytime TD|450|DraftKings|
|Tre Harris|anytime_td Anytime TD|340|DraftKings|
|David Njoku|anytime_td Anytime TD|750|DraftKings|
|Justin Herbert|anytime_td Anytime TD|600|DraftKings|

Não foi calculado EV: não há probabilidades calibradas. Frequências históricas e probabilidades implícitas de preço não substituem isso. Sem validade temporal individual não se libera cotação para execução. Linhas reais publicadas e cenários hipotéticos ficam separados nos CSVs.

## Limitações, decisão e reprodução

- Snapshot cobre W1–W9 e W10 parcial (jogo-alvo excluído). Números de LAC usam8 jogos, BAL9; janelas são últimas partidas, não simplesmente semanas consecutivas.
- Condicionar à participação ofensiva causa seleção: não mede chance de estar ativo/jogar. Missing/sem snaps não vira zero; zeros apenas com identidade e PBP completo. McConkey foi ativo sem jogar em W9, e está fora hoje.
- Lesões/inativos são observações manuais oficiais desta sessão, sem adapter produtivo. Disponibilidade para jogar não garante função ou ausência de mudança de última hora.
- Modelos legados, probabilidades históricas e Masters não foram alterados; nenhuma pendência de identidade não relacionada bloqueou a análise. Nenhum modelo treinado/promovido.
- Best Parlay não montada: um jogo não atende quatro jogos. TD Parlay permitiria>=2 TDs estruturalmente, mas shortlist não é uma combinada aprovada; nenhuma foi montada. Stake total R$0 de limite R$50.

Reproduzir em diretório novo (não sobrescrever os quatro relatórios):

```bash
python -m nfl_betting.mnf_preview --database /BUILD --observations reports/mnf_2026_11_16_support/pregame_observations.json --stake-folder /STAKE_RUN --out /NOVA_PASTA
python -m unittest discover -s tests -v
python tools/verify_history.py
```

O JSON contém vetores observados, denominadores, chaves, métricas, versões, hashes, conflitos e fontes. Reexecutar depois do kickoff muda explicitamente o modo para publicação posterior com dados pré-kickoff congelados; não representa nova análise pré-jogo.
