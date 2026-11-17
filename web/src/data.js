export const EMPTY_DATA = {
  status: 'UNAVAILABLE', games: [], props: [], matchups: [], players: [],
  generated_at_utc: null, cutoff_utc: null, decision: 'NO_BET'
};

export function validQuote(quote, now = new Date()) {
  if (!quote || typeof quote !== 'object') return false;
  return typeof quote.decimal_odds === 'number'
    && Number.isFinite(quote.decimal_odds)
    && quote.decimal_odds > 1
    && typeof quote.bookmaker === 'string'
    && quote.bookmaker.length > 0
    && typeof quote.provider === 'string'
    && quote.provider.length > 0
    && Boolean(quote.observed_at_utc || quote.observed_at)
    && Boolean(quote.valid_until_utc || quote.valid_until)
    && new Date(quote.valid_until_utc || quote.valid_until) > now;
}

export function approvedEv(prop, now = new Date()) {
  const probability = prop?.model?.probability;
  if (prop?.model?.validated !== true || !validQuote(prop?.quote, now)
      || prop?.quote?.verified !== true || typeof probability !== 'number'
      || !Number.isFinite(probability) || probability < 0 || probability > 1) return null;
  return probability * prop.quote.decimal_odds - 1;
}

export function qualityScore(prop) {
  const score = prop?.quality?.evidence_completeness_score;
  return typeof score === 'number' && Number.isFinite(score) ? score : -1;
}

export function filterProps(props, filters) {
  const search = (filters.search || '').trim().toLocaleLowerCase('pt-BR');
  return (props || []).filter((prop) => {
    if (filters.gameId && prop.game_id !== filters.gameId) return false;
    if (filters.team && prop.team !== filters.team) return false;
    if (filters.position && prop.position !== filters.position) return false;
    if (filters.market && prop.market !== filters.market) return false;
    if (filters.tdOnly && prop.market !== 'anytime_td') return false;
    if (search && ![prop.player_name, prop.team, prop.market]
      .join(' ').toLocaleLowerCase('pt-BR').includes(search)) return false;
    // The minimum price applies only to records that actually have a price.
    // Unquoted descriptive analyses remain explorable by design.
    if (validQuote(prop.quote) && prop.quote.decimal_odds < filters.minOdds) return false;
    if (filters.onlyQuoted && !validQuote(prop.quote)) return false;
    return true;
  });
}

export function sortProps(props, sortBy) {
  return [...props].sort((a, b) => {
    if (sortBy === 'ev') {
      const aev = approvedEv(a);
      const bev = approvedEv(b);
      if (aev !== null || bev !== null) return (bev ?? -Infinity) - (aev ?? -Infinity);
    }
    return qualityScore(b) - qualityScore(a)
      || (b?.history?.season?.n || 0) - (a?.history?.season?.n || 0)
      || String(a.player_name || '').localeCompare(String(b.player_name || ''), 'pt-BR');
  });
}

export function hasApprovedEv(props) {
  return (props || []).some((prop) => approvedEv(prop) !== null);
}
