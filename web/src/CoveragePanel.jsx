import React from 'react';

const REASONS = {
  AVAILABLE: 'Há cobertura para os jogadores avaliados.',
  PARTIAL: 'Parte do roster ou dos jogadores avaliados está sem cobertura.',
  KICKOFF_UNAVAILABLE: 'O horário de início está indisponível.',
  KICKOFF_CONFLICT: 'Horários divergentes sem correção oficial disponível até o cutoff.',
  PREGAME_NOT_VERIFIABLE: 'O snapshot não comprova um cutoff anterior ao início deste jogo.',
  NO_COMPLETE_TEAM_HISTORY: 'Sem histórico completo de equipes disponível até o cutoff.',
  NO_WEEKLY_ROSTER: 'Sem roster canônico da semana até o cutoff.',
  NO_RESOLVED_OFFENSIVE_ROSTER: 'Sem jogadores ofensivos com equipe e identidade reconciliadas.',
  NO_REMAINING_ROSTER_CANDIDATES: 'Nenhum candidato restou após verificar dispensas e vínculos encerrados.',
  INSUFFICIENT_PLAYER_COVERAGE: 'Nenhum jogador avaliado tem a amostra mínima para uma análise.',
  NO_CONFIRMED_OFFENSIVE_HISTORY: 'Sem participação ofensiva histórica confirmada',
  NO_METRIC_OBSERVATIONS: 'Sem valores observados para a métrica',
  INSUFFICIENT_OBSERVATIONS: 'Amostra insuficiente',
  NOT_MATERIALIZED: 'Métrica individual indisponível no catálogo'
};

export function coverageReason(code) {
  return REASONS[code];
}

export default function CoveragePanel({ game, players, team, marketLabels }) {
  const coverage = game.coverage;
  if (!coverage) return null;
  const gaps = players.filter((player) => (!team || player.team === team) &&
    Object.values(player.markets).some(({ status }) => status !== 'AVAILABLE' && status !== 'NOT_APPLICABLE_POSITION'));
  const missingTeams = coverage.roster_teams?.length
    ? [game.away_team, game.home_team].filter((code) => !coverage.roster_teams.includes(code)) : [];
  const rosterSources = Object.entries(coverage.roster_evidence || {})
    .filter(([code]) => !team || team === code);
  const exclusions = coverage.roster_exclusions || {};

  return <div className="coverage-panel card">
    <b>Cobertura pré-jogo</b>
    <p>{coverageReason(coverage.props_status)}</p>
    {coverage.roster_candidates > 0 && <p>{coverage.players_with_props}/{coverage.roster_candidates} jogadores avaliados com cenários no confronto.</p>}
    {coverage.unresolved_roster_rows > 0 && <p>{coverage.unresolved_roster_rows} registros ofensivos sem identidade ou equipe inequívoca.</p>}
    {exclusions.CUT > 0 && <p>{exclusions.CUT} registros marcados como dispensados.</p>}
    {exclusions.ENDED_TEAM_MEMBERSHIP > 0 && <p>{exclusions.ENDED_TEAM_MEMBERSHIP} vínculos encerrados por transação verificada.</p>}
    {missingTeams.length > 0 && <p>Sem roster para {missingTeams.join(' e ')}.</p>}
    {rosterSources.map(([code, evidence]) => <p key={code}>
      <strong>{code}</strong> · {evidence.status === 'PROVISIONAL_ROSTER'
        ? `Roster provisório da Semana ${evidence.source_week} (${evidence.age_weeks} sem.); vínculo atual não verificado.`
        : `Roster da Semana ${evidence.source_week} · ${evidence.provider}.`}
    </p>)}
    {gaps.length > 0 && <details><summary>Lacunas por jogador ({gaps.length})</summary>
      <ul>{gaps.map((player) => <li key={player.player_id}>
        <strong>{player.display_name || player.player_id} · {player.team}</strong>
        <ul>{Object.entries(player.markets)
          .filter(([, detail]) => detail.status !== 'AVAILABLE' && detail.status !== 'NOT_APPLICABLE_POSITION')
          .map(([market, { n, status }]) => <li key={market}>
            {marketLabels[market] || market} · {coverageReason(status)}{n > 0 && ` (n = ${n})`}
          </li>)}</ul>
      </li>)}</ul>
    </details>}
  </div>;
}
