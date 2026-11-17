import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  ArrowDown, ArrowLeft, BarChart3, CalendarDays, ChartNoAxesCombined,
  ChevronRight, Database, Filter, Info, RefreshCw, Search, ShieldAlert, Ticket, Trophy
} from 'lucide-react';
import './style.css';
import { EMPTY_DATA, approvedEv, filterProps, hasApprovedEv, snapshotFreshness, sortProps, validQuote } from './data.js';
import { HistoryDistribution, isNumber, Metric, number, ObservedFrequency, percent } from './HistoryPanel.jsx';
import GameAnalysis from './GameAnalysis.jsx';
import CoveragePanel from './CoveragePanel.jsx';

const MARKET_LABEL = {
  receptions: 'Recepções', rec_yards: 'Jardas recebidas', rush_yards: 'Jardas corridas',
  pass_yards: 'Jardas passadas', pass_attempts: 'Tentativas de passe',
  completions: 'Passes completos', anytime_td: 'Anytime TD'
};
const STATUS_LABEL = {
  FINAL: 'Final', SCHEDULED: 'Agendado no cutoff',
  SCHEDULED_AT_CUTOFF: 'Agendado no cutoff', RESULT_RECORDED: 'Resultado registrado',
  STARTED_STATUS_UNKNOWN: 'Sem resultado no cutoff', KICKOFF_UNVERIFIED: 'Horário em verificação'
};
const DEFAULT_FILTERS = { search: '', position: '', market: '', minOdds: 1.5, onlyQuoted: false };
const PROP_PAGE_SIZE = 48;

const datetime = (value, includeYear = true) => value && Number.isFinite(Date.parse(value))
  ? new Date(value).toLocaleString('pt-BR', {
    timeZone: 'America/Sao_Paulo', day: '2-digit', month: '2-digit',
    year: includeYear ? 'numeric' : undefined, hour: '2-digit', minute: '2-digit'
  }) : 'Não disponível';
const gameStatus = (game) => STATUS_LABEL[game.status] || 'Status indisponível';
const lineLabel = (prop) => prop.market === 'anytime_td' ? 'Marca TD'
  : `${prop.side === 'under' ? 'Under' : 'Over'} ${number(prop.line, 1)}`;

function readGameId() {
  try {
    return decodeURIComponent(location.hash.match(/^#\/game\/(.+)$/)?.[1] || '');
  } catch {
    return '';
  }
}

function useHashGame() {
  const [gameId, setGameId] = useState(readGameId);
  useEffect(() => {
    const change = () => setGameId(readGameId());
    addEventListener('hashchange', change);
    return () => removeEventListener('hashchange', change);
  }, []);
  return gameId;
}

function focusSection(id) {
  const element = document.getElementById(id);
  element?.focus({ preventScroll: true });
  element?.scrollIntoView();
}

function App() {
  const [data, setData] = useState(EMPTY_DATA);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState('games');
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [sortBy, setSortBy] = useState('quality');
  const gameId = useHashGame();
  const title = useRef(null);
  const previousRoute = useRef(null);

  useEffect(() => {
    let active = true;
    const base = import.meta.env.BASE_URL || '/';
    fetch(`${base}data/slate.json`, { cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        if (!Array.isArray(payload.games) || !Array.isArray(payload.props) || !Array.isArray(payload.matchups)
          || ('player_coverage' in payload && !Array.isArray(payload.player_coverage))) {
          throw Error('Contrato de dados inválido');
        }
        if (active) setData({ ...EMPTY_DATA, ...payload });
      })
      .catch((reason) => { if (active) setError(String(reason.message || reason)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const game = data.games.find((item) => item.game_id === gameId);
  const matchup = data.matchups.find((item) => item.game_id === gameId);
  const quoted = data.props.filter((prop) => validQuote(prop.quote)).length;
  const freshness = snapshotFreshness(data);
  const route = gameId || view;
  useEffect(() => {
    if (previousRoute.current && previousRoute.current !== route) {
      title.current?.focus({ preventScroll: true });
      scrollTo(0, 0);
    }
    previousRoute.current = route;
  }, [route]);

  const navigate = (nextView) => {
    if (location.hash) {
      history.pushState(null, '', `${location.pathname}${location.search}`);
      dispatchEvent(new HashChangeEvent('hashchange'));
    }
    setView(nextView);
  };

  return <div className="shell">
    <a className="skip" href="#conteudo" onClick={(event) => {
      event.preventDefault();
      focusSection('conteudo');
    }}>Pular para o conteúdo</a>
    <header className="top"><div className="top-inner">
      <button className="brand" onClick={() => navigate('games')} aria-label="NFL Intelligence, página inicial">
        <span className="brandicon"><ChartNoAxesCombined size={23} /></span>
        <span><b>NFL Intelligence</b><small>Pesquisa de player props</small></span>
      </button>
      <nav className="main-nav" aria-label="Navegação principal">
        <Nav active={Boolean(game) || view === 'games'} icon={CalendarDays} label="Jogos" onClick={() => navigate('games')} />
        <Nav active={!game && view === 'props'} icon={BarChart3} label="Props" onClick={() => navigate('props')} />
        <Nav active={!game && view === 'td'} icon={Trophy} label="Touchdowns" onClick={() => navigate('td')} />
      </nav>
      <button type="button" className="refresh" onClick={() => location.reload()} aria-label="Atualizar snapshot" title="Atualizar snapshot"><RefreshCw size={18} /></button>
    </div></header>
    <main id="conteudo" tabIndex={-1}>
      <section className="hero" aria-labelledby="page-title">
        <div className="hero-copy">
          {game && <button className="back" onClick={() => navigate('games')}><ArrowLeft size={16} /> Todos os jogos</button>}
          {!game && <p className="eyebrow">{data.season && data.week ? `Temporada ${data.season} · Semana ${data.week}` : 'Calendário NFL'}</p>}
          <h1 id="page-title" tabIndex={-1} ref={title}>{game ? `${game.away_team} × ${game.home_team}`
            : view === 'props' ? 'Scanner de player props' : view === 'td' ? 'Análise de Anytime TD' : 'Jogos e evidências'}</h1>
          <p className="hero-description">{game ? `${datetime(game.kickoff_utc)} · ${gameStatus(game)}`
            : 'Explore confrontos e evidências históricas de player props.'}</p>
          {game?.kickoff_evidence && <p className="hero-description">
            Horário corrigido pela NFL · horário no catálogo {datetime(game.canonical_kickoff_utc)}.
          </p>}
          {game && <a className="jump" href="#props-title" onClick={(event) => {
            event.preventDefault();
            focusSection('props-title');
          }}>Ver props do confronto <ArrowDown size={16} /></a>}
        </div>
        <div className="hero-side">
          <small><Database size={15} /> {data.source_snapshot_id ? 'Snapshot congelado' : 'Snapshot indisponível'}</small>
          <span>Cutoff · horário de Brasília</span><b>{datetime(data.cutoff_utc)}</b>
          {data.source_available_at_utc && <span className="snapshot-meta">Coleta {datetime(data.source_available_at_utc)}</span>}
          {freshness === 'STALE' && <span className="snapshot-state">Desatualizado</span>}
          {freshness === 'UNKNOWN' && <span className="snapshot-meta">Idade do snapshot indisponível</span>}
          {game && ['FINAL', 'RESULT_RECORDED'].includes(game.status) && isNumber(game.away_score) && isNumber(game.home_score) &&
            <span className="snapshot-meta">Placar registrado · {game.away_score} – {game.home_score}</span>}
        </div>
      </section>
      <section className="notice" aria-live="polite">
        <ShieldAlert size={19} /><div><b>NO_BET</b>
          <span>{error ? `Feed indisponível (${error}).` : loading ? 'Carregando snapshot local…'
            : 'Frequência histórica é descritiva. O EV exige modelo validado e cotação verificável dentro da validade.'}</span>
        </div>
      </section>
      {!game && <section className="stats" aria-label="Resumo do snapshot">
        <Stat label="Jogos no snapshot" value={data.games.length} icon={CalendarDays} />
        <Stat label="Cenários de props" value={data.props.length} icon={BarChart3} />
        <Stat label="Cotações válidas" value={quoted} icon={Ticket} />
      </section>}
      {!game && isNumber(data.counts?.scheduled_games_at_cutoff) && <p className="micro snapshot-coverage">
        Cobertura no cutoff · {data.counts.scheduled_games_with_analysis}/{data.counts.scheduled_games_at_cutoff} confrontos agendados com análise de equipes · {data.counts.games_with_props} com props · {data.counts.players_assessed > 0
          ? `${data.counts.players}/${data.counts.players_assessed} jogadores avaliados com cenários`
          : 'sem roster elegível para avaliar jogadores'}
      </p>}
      {game && <GameAnalysis game={game} matchup={matchup} />}
      {!game && view === 'games' && <Games games={data.games} week={data.week} />}
      <PropsExplorer key={game?.game_id || 'scanner'} game={game} records={data.props}
        filters={filters} setFilters={setFilters} sortBy={sortBy} setSortBy={setSortBy}
        tdOnly={!game && view === 'td'} cutoff={data.cutoff_utc} coverage={data.player_coverage} />
      <Provenance data={data} />
    </main>
    <footer>Pesquisa quantitativa · nenhuma aposta é executada · custo adicional R$ 0</footer>
  </div>;
}

function Stat({ label, value, icon: Icon }) {
  return <div className="stat"><span className="stat-icon"><Icon size={20} /></span><div>
    <small>{label}</small><strong>{number(value, 0)}</strong>
  </div></div>;
}

function Nav({ active, icon: Icon, label, onClick }) {
  return <button onClick={onClick} aria-current={active ? 'page' : undefined}><Icon size={19} />{label}</button>;
}

function Games({ games, week }) {
  return <section className="section" aria-labelledby="games-title">
    <div className="sectionhead">
      <h2 id="games-title"><CalendarDays size={20} /> Jogos da rodada</h2>
      <span className="hint">{week ? `Semana ${week}` : 'Rodada não publicada'}</span>
    </div>
    {games.length ? <div className="games">{games.map((game) =>
      <a key={game.game_id} className="game card" href={`#/game/${encodeURIComponent(game.game_id)}`}>
        <span className="game-date">{datetime(game.kickoff_utc, false)}</span>
        <span className={`status ${['FINAL', 'RESULT_RECORDED'].includes(game.status) ? 'final' : ''}`}>{gameStatus(game)}</span>
        <span className="gameTeams"><b>{game.away_team}</b><span>×</span><b>{game.home_team}</b></span>
        <ChevronRight size={18} aria-hidden="true" />
        {game.status === 'SCHEDULED_AT_CUTOFF' && game.coverage && <span className="game-coverage">
          {game.coverage.matchup_status === 'AVAILABLE' ? 'Com análise de equipes' : 'Sem análise de equipes'}
          {' · '}{game.coverage.prop_scenarios > 0 ? `${game.coverage.prop_scenarios} cenários` : 'Sem props'}
        </span>}
      </a>
    )}</div> : <Empty icon={CalendarDays} title="Nenhum jogo publicado" />}
  </section>;
}

function TeamSelector({ game, team, onChange }) {
  const options = [['', 'Geral'], [game.away_team, 'Visitante'], [game.home_team, 'Mandante']];
  return <fieldset className="team-selector">
    <legend>Equipe</legend>
    <div className="segments">{options.map(([value, label]) => <label key={label}>
      <input type="radio" name="prop-team" value={value}
        aria-label={value ? `${value}, time ${label.toLowerCase()}` : label}
        checked={team === value} onChange={() => onChange(value)} />
      <span>{value ? <><b>{value}</b><small>{label}</small></> : <b>{label}</b>}</span>
    </label>)}</div>
  </fieldset>;
}

function PropsExplorer({ game, records, filters, setFilters, sortBy, setSortBy, tdOnly, cutoff, coverage }) {
  // The game-keyed explorer remounts whenever navigation changes the matchup.
  const [team, setTeam] = useState('');
  const [limit, setLimit] = useState(PROP_PAGE_SIZE);
  const gameId = game?.game_id;
  const scoped = useMemo(() => filterProps(records, {
    ...filters, market: tdOnly ? '' : filters.market, gameId, team, tdOnly
  }),
    [records, filters, gameId, team, tdOnly]);
  const availableEv = hasApprovedEv(scoped);
  const order = availableEv ? sortBy : 'quality';
  const props = useMemo(() => sortProps(scoped, order), [scoped, order]);
  useEffect(() => setLimit(PROP_PAGE_SIZE), [filters, team, tdOnly, order]);
  const hasGameProps = !game || records.some((prop) => prop.game_id === gameId);
  const title = game ? 'Props deste confronto' : tdOnly ? 'Cenários de Anytime TD' : 'Hipóteses estatísticas';
  const change = (key, value) => setFilters((current) => ({ ...current, [key]: value }));

  return <section className="section" aria-labelledby="props-title">
    <div className="sectionhead">
      <h2 id="props-title" tabIndex={-1}><Filter size={20} /> {title}</h2>
      <span className="hint" role="status">{number(props.length, 0)} {props.length === 1 ? 'cenário' : 'cenários'}</span>
    </div>
    <div className="filters card">
      {game && <TeamSelector game={game} team={team} onChange={setTeam} />}
      <div className="filter-fields">
        <label className="search">Buscar
          <span><Search size={17} /><input value={filters.search} onChange={(event) => change('search', event.target.value)}
            placeholder="Atleta, time ou mercado" type="search" /></span>
        </label>
        <label>Posição<select value={filters.position} onChange={(event) => change('position', event.target.value)}>
          <option value="">Todas</option>{['QB', 'RB', 'WR', 'TE'].map((position) => <option key={position}>{position}</option>)}
        </select></label>
        {!tdOnly && <label>Mercado<select value={filters.market} onChange={(event) => change('market', event.target.value)}>
          <option value="">Todos</option>{Object.entries(MARKET_LABEL).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select></label>}
        <label>Odd mínima<select value={filters.minOdds} onChange={(event) => change('minOdds', Number(event.target.value))}>
          {[1.5, 1.6, 1.7, 1.8, 2, 2.5, 3].map((value) => <option key={value} value={value}>{number(value, 2)}</option>)}
        </select></label>
        <label>Ordenar<select value={order} onChange={(event) => setSortBy(event.target.value)}>
          <option value="quality">Completude</option><option value="ev" disabled={!availableEv}>EV validado</option>
        </select></label>
      </div>
      <div className="filter-meta">
        <label className="check"><input type="checkbox" checked={filters.onlyQuoted}
          onChange={(event) => change('onlyQuoted', event.target.checked)} /> Somente com odds</label>
        <span>A odd mínima só se aplica a cenários cotados.</span>
      </div>
    </div>
    {game && <CoveragePanel game={game} players={coverage.filter((player) => player.game_id === gameId)}
      team={team} marketLabels={MARKET_LABEL} />}
    {props.length ? <>
      <div className="proplist">{props.slice(0, limit).map((prop) => <Prop key={prop.id} prop={prop} cutoff={cutoff} />)}</div>
      {props.length > limit && <button className="load-more" onClick={() => setLimit((n) => n + PROP_PAGE_SIZE)}>
        Mostrar mais cenários ({limit} de {props.length})
      </button>}
    </>
      : <Empty icon={Info} title={hasGameProps ? 'Nenhum cenário neste filtro' : 'Sem props pré-jogo publicadas'}>
        {hasGameProps ? 'Experimente ajustar os filtros.' : !game?.coverage && 'O snapshot não traz cenários elegíveis para este confronto.'}
      </Empty>}
  </section>;
}

function Prop({ prop, cutoff }) {
  const [open, setOpen] = useState(false);
  const quoteOk = validQuote(prop.quote);
  const ev = approvedEv(prop);
  const history = prop.history || {};
  const defense = prop.context?.defense_vs_position;
  const market = MARKET_LABEL[prop.market] || prop.market;
  const unit = prop.market?.endsWith('_yards') ? 'jardas' : prop.market === 'anytime_td' ? 'TD por jogo' : market?.toLowerCase();
  const completeness = prop.quality?.evidence_completeness_score;
  return <article className="card prop">
    <h3 className="prop-heading"><button className="prophead" onClick={() => setOpen(!open)} aria-expanded={open}>
      <span className="position">{prop.position || '—'}</span>
      <span className="propname"><b>{prop.player_name}</b><small>{prop.team} × {prop.opponent} · {market}
        {prop.roster_evidence?.status === 'PROVISIONAL_ROSTER' && ` · Roster provisório S${prop.roster_evidence.source_week}`}
      </small></span>
      <span className="line"><b>{lineLabel(prop)}</b><small>{prop.line_kind === 'ANALYTICAL_THRESHOLD_NOT_BOOK_OFFER' ? 'Limiar analítico' : 'Cenário de TD'}</small></span>
      <span className={`price ${quoteOk ? '' : 'missing'}`}><b>{quoteOk ? number(prop.quote.decimal_odds, 2) : 'Sem odd'}</b>
        {quoteOk && <small>{prop.quote.bookmaker}</small>}
      </span>
      <ChevronRight className={open ? 'rotated' : ''} size={19} aria-hidden="true" />
    </button></h3>
    <div className="summarymetrics">
      <ObservedFrequency history={history} />
      <div className="summary-gates">
        <Metric label="Completude" value={isNumber(completeness) ? `${number(completeness, 0)}/100` : '—'} />
        <Metric label="EV" value={ev === null ? 'Não aprovado' : percent(ev)} />
      </div>
    </div>
    {open && <div className="detail">
      <HistoryDistribution history={history} unit={unit} />
      <div className="evidencegrid">
        <Evidence title="O que sustenta" items={prop.evidence?.favors} positive />
        <Evidence title="O que enfraquece" items={prop.evidence?.weakens} />
      </div>
      <div className="volume"><h4>Volume e função</h4><div className="metrics">
        <Metric label="Jogos" value={number(prop.volume?.games, 0)} />
        <Metric label="Targets/jogo" value={number(prop.volume?.targets_per_game)} />
        <Metric label="Recepções/jogo" value={number(prop.volume?.receptions_per_game)} />
        <Metric label="Corridas/jogo" value={number(prop.volume?.carries_per_game)} />
        <Metric label="Snap share" value={percent(prop.volume?.offensive_snap_share_mean)} />
        <Metric label="Red zone" value={number(prop.volume?.red_zone_opportunities, 0)} />
        <Metric label="Goal line ≤5" value={number(prop.volume?.goal_line_opportunities, 0)} />
      </div>
        {prop.volume?.unavailable_metrics?.routes_run && <p className="micro">Routes run, TPRR e YPRR indisponíveis no catálogo.</p>}
        {prop.volume?.unavailable_metrics?.red_zone_opportunities && <p className="micro">Red zone e goal line sem observações de campo completas.</p>}
      </div>
      {defense && <div className="volume"><h4>Defesa de {prop.opponent} contra {defense.position}</h4>
        <div className="metrics">
          <Metric label="Jogos com evento da posição" value={number(defense.games_with_position_events, 0)} />
          <Metric label="Targets cedidos/jogo" value={number(defense.targets_allowed_per_game)} />
          <Metric label="Recepções cedidas/jogo" value={number(defense.receptions_allowed_per_game)} />
          <Metric label="Jardas recebidas cedidas/jogo" value={number(defense.receiving_yards_allowed_per_game)} />
        </div>
      </div>}
      <div className="prop-source micro">
        <p><b>{prop.decision || 'NO_BET'}</b> · Disponibilidade oficial {prop.eligibility?.status === 'UNVERIFIED' ? 'não verificada' : prop.eligibility?.status || 'indisponível'} · Cutoff {datetime(cutoff)}</p>
        {prop.roster_evidence && <p>Roster · {prop.roster_evidence.provider} · Semana {prop.roster_evidence.source_week} · Disponível {datetime(prop.roster_evidence.available_at_utc)}</p>}
        {prop.sources?.length > 0 && <p>Fonte dos dados: {prop.sources.map(({ provider, table }) => `${provider} (${table})`).join(' · ')}</p>}
        {quoteOk && <p>Cotação: {prop.quote.bookmaker} · {prop.quote.provider} · Capturada {datetime(prop.quote.observed_at_utc || prop.quote.observed_at)} · Válida até {datetime(prop.quote.valid_until_utc || prop.quote.valid_until)}</p>}
      </div>
    </div>}
  </article>;
}

function Evidence({ title, items = [], positive }) {
  return <div className={positive ? 'evidence positive' : 'evidence'}><h4>{title}</h4>
    {items.length ? <ul>{items.map((item, index) => <li key={index}>{item}</li>)}</ul>
      : <p className="micro">Evidência indisponível.</p>}
  </div>;
}

function Empty({ icon: Icon, title, children }) {
  return <div className="empty"><Icon size={22} /><b>{title}</b>{children && <p>{children}</p>}</div>;
}

function Provenance({ data }) {
  return <section className="section" aria-labelledby="source-title">
    <div className="sectionhead"><h2 id="source-title"><Database size={20} /> Transparência dos dados</h2></div>
    <div className="card provenance"><dl>
      <div><dt>Snapshot</dt><dd>{data.source_snapshot_id || 'Não publicado'}</dd></div>
      <div><dt>Banco SHA-256</dt><dd>{data.database_sha256 || '—'}</dd></div>
      <div><dt>Cutoff</dt><dd>{datetime(data.cutoff_utc)}</dd></div>
      <div><dt>Disponibilidade da fonte</dt><dd>{datetime(data.source_available_at_utc)}</dd></div>
      <div><dt>Publicado</dt><dd>{datetime(data.generated_at_utc || data.published_at_utc)}</dd></div>
      <div><dt>Estado</dt><dd>{data.status}</dd></div>
      <div><dt>Identidades pendentes</dt><dd>{data.pending_identity_audit_rows ?? '—'}</dd></div>
    </dl><p>Fonte estatística: NFLverse via catálogo canônico. O snapshot é congelado. Odds de outras casas são identificadas pelo bookmaker.</p></div>
  </section>;
}

if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  addEventListener('load', () => navigator.serviceWorker.register(`${import.meta.env.BASE_URL || '/'}sw.js`).catch(() => {}));
}
createRoot(document.getElementById('root')).render(<App />);
