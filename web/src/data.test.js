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
