import React from 'react';
import { Activity, CircleAlert, Info, UserRoundSearch } from 'lucide-react';
import { WINDOWS, number, percent, RateBar } from './HistoryPanel.jsx';

const TEAM_METRICS = [
  ['epa_per_play', 'EPA por jogada', (value) => number(value, 3)],
  ['success_rate', 'Taxa de sucesso', percent],
  ['offensive_plays_per_game', 'Jogadas por jogo', number],
  ['pass_attempts_per_game', 'Passes por jogo', number],
  ['rush_attempts_per_game', 'Corridas por jogo', number]
];

function TeamPanel({ team, windows }) {
  return <article className="card teampanel">
    <h3>{team}</h3>
    <table className="team-comparison">
      <caption className="sr-only">Indicadores ofensivos do {team} por janela</caption>
      <thead><tr><th scope="col">Indicador</th>{WINDOWS.map(([key, label]) => <th scope="col" key={key}>
        {label}<small>{windows[key]?.games == null ? '—' : `${windows[key].games} jogos`}</small>
      </th>)}</tr></thead>
      <tbody>{TEAM_METRICS.map(([key, label, format]) => <tr key={key}>
        <th scope="row">{label}</th>
        {WINDOWS.map(([window]) => <td key={window}>
          {format(windows[window]?.[key])}
          {key === 'success_rate' && <RateBar value={windows[window]?.[key]} />}
        </td>)}
      </tr>)}</tbody>
    </table>
  </article>;
}

function DefensePanels({ context }) {
  return <div className="defensegrid">{Object.entries(context).map(([team, positions]) =>
    <article className="card defense" key={team}>
      <h3>Defesa {team} por posição</h3>
      <table>
        <thead><tr><th scope="col">Pos.</th><th scope="col">Jogos</th><th scope="col">Targets</th><th scope="col">Rec.</th><th scope="col">Jardas</th></tr></thead>
        <tbody>{Object.values(positions).map((row) => <tr key={row.position}>
          <th scope="row">{row.position}</th><td>{row.games_with_position_events ?? '—'}</td>
          <td>{number(row.targets_allowed_per_game)}</td><td>{number(row.receptions_allowed_per_game)}</td>
          <td>{number(row.receiving_yards_allowed_per_game)}</td>
        </tr>)}</tbody>
      </table>
      <p className="micro">Médias por jogo com evento da posição. Agregado por posição, sem ajuste por adversário.</p>
    </article>
  )}</div>;
}

export default function GameAnalysis({ game, matchup }) {
  return <section className="section" aria-labelledby="match-title">
    <div className="sectionhead"><h2 id="match-title"><Activity size={20} /> Análise do confronto</h2></div>
    {matchup ? <>
      {matchup.summary && <div className="callout"><Info size={18} /><p>{matchup.summary}</p></div>}
      <div className="teamgrid">{[game.away_team, game.home_team].map((team) =>
        matchup.teams?.[team] && <TeamPanel key={team} team={team} windows={matchup.teams[team]} />
      )}</div>
      <DefensePanels context={matchup.defense_vs_position || {}} />
      <div className="pending card"><UserRoundSearch size={20} /><div>
        <b>QBs e inativos: pendentes</b><p>{matchup.injury_note}</p>
      </div></div>
    </> : <div className="empty">
      <CircleAlert /><b>Análise pré-jogo indisponível</b>
      <p>Este snapshot não traz evidências pré-jogo elegíveis para o confronto.</p>
    </div>}
  </section>;
}
