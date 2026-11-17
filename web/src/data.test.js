import test from 'node:test';
import assert from 'node:assert/strict';
import { approvedEv, filterProps, hasApprovedEv, sortProps, validQuote } from './data.js';

const base = {
  id: 'p1', player_name: 'Atleta', team: 'LAC', position: 'WR', market: 'rec_yards',
  quality: { evidence_completeness_score: 80 }, model: { validated: false, probability: null },
  quote: null
};

test('estado sem odds continua explorável', () => {
  const result = filterProps([base], { minOdds: 1.5 });
  assert.equal(result.length, 1);
  assert.equal(approvedEv(base), null);
  assert.equal(hasApprovedEv(result), false);
});

test('filtro mínimo só remove cotações abaixo do limite', () => {
  const quote = {
    decimal_odds: 1.4, bookmaker: 'Casa', provider: 'Feed', verified: true,
    observed_at: '2026-11-16T20:00:00Z', valid_until: '2099-11-16T20:05:00Z'
  };
  assert.equal(filterProps([base, { ...base, id: 'p2', quote }], { minOdds: 1.5 }).length, 1);
});

test('EV permanece bloqueado sem modelo validado e quote verificada', () => {
  const quote = {
    decimal_odds: 2, bookmaker: 'Casa', provider: 'Feed', verified: true,
    observed_at: '2026-11-16T20:00:00Z', valid_until: '2099-11-16T20:05:00Z'
  };
  assert.equal(validQuote(quote, new Date('2026-11-16T20:01:00Z')), true);
  assert.equal(approvedEv({ ...base, quote, model: { validated: false, probability: 0.6 } }), null);
  assert.ok(Math.abs(approvedEv({ ...base, quote, model: { validated: true, probability: 0.6 } }) - 0.2) < 1e-12);
});

test('ordenação padrão usa completude, não frequência como probabilidade', () => {
  const low = { ...base, id: 'low', quality: { evidence_completeness_score: 20 } };
  assert.equal(sortProps([low, base], 'quality')[0].id, 'p1');
});

const away = { ...base, id: 'away', game_id: 'g1', team: 'LAC' };
const home = {
  ...base, id: 'home', game_id: 'g1', team: 'BAL', player_name: 'Outro atleta',
  position: 'RB', market: 'rush_yards'
};
const gameProps = [
  away, home, { ...away, id: 'other-game', game_id: 'g2' },
  { ...home, id: 'team-prefix', team: 'BAL-FORA' }
];

test('Geral preserva os dois times do confronto e os segmentos usam o código exato', () => {
  const ids = (team) => filterProps([away, home, gameProps[2]], { gameId: 'g1', team })
    .map((prop) => prop.id);
  assert.deepEqual(ids(''), ['away', 'home']);
  assert.deepEqual(ids('LAC'), ['away']);
  assert.deepEqual(
    filterProps(gameProps, { gameId: 'g1', team: 'BAL' }).map((prop) => prop.id),
    ['home']
  );
});

test('equipe combina com busca, posição, mercado, TD e filtros de cotação', () => {
  const quote = (decimal_odds) => ({
    decimal_odds, bookmaker: 'Casa', provider: 'Feed',
    observed_at: '2026-11-16T20:00:00Z', valid_until: '2099-11-16T20:05:00Z'
  });
  const records = [
    ...gameProps,
    { ...home, id: 'quoted', quote: quote(1.8) },
    { ...home, id: 'low-price', quote: quote(1.4) },
    { ...home, id: 'wrong-position', position: 'WR', quote: quote(1.8) },
    { ...home, id: 'wrong-market', market: 'anytime_td', quote: quote(1.8) },
    { ...home, id: 'wrong-search', player_name: 'Jogador', quote: quote(1.8) },
    { ...home, id: 'wrong-team', team: 'LAC', quote: quote(1.8) }
  ];
  const filters = {
    gameId: 'g1', team: 'BAL', search: ' OUTRO ', position: 'RB',
    market: 'rush_yards', minOdds: 1.5, onlyQuoted: true
  };
  assert.deepEqual(filterProps(records, filters).map((prop) => prop.id), ['quoted']);
  assert.deepEqual(filterProps(records, { ...filters, tdOnly: true }), []);
});

test('confronto sem props fica vazio e um novo confronto aceita Geral', () => {
  assert.deepEqual(filterProps(gameProps, { gameId: 'g3', team: '' }), []);
  assert.deepEqual(
    filterProps(gameProps, { gameId: 'g2', team: '' }).map((prop) => prop.id),
    ['other-game']
  );
});
