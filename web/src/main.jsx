import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity, ArrowLeft, BarChart3, CalendarDays, ChartNoAxesCombined,
  ChevronRight, CircleAlert, Database, Filter, Info, RefreshCw, Search,
  ShieldAlert, ShieldCheck, Trophy, UserRoundSearch
} from 'lucide-react';
import './style.css';
import {
  EMPTY_DATA, approvedEv, filterProps, hasApprovedEv, sortProps, validQuote
} from './data.js';

const MARKET_LABEL = {
  receptions: 'Recepções', rec_yards: 'Jardas recebidas', rush_yards: 'Jardas corridas',
  pass_yards: 'Jardas passadas', pass_attempts: 'Tentativas de passe',
  completions: 'Passes completos', anytime_td: 'Anytime TD'
};
const STATUS_LABEL = {
  FINAL: 'Final', SCHEDULED: 'Agendado no cutoff', SCHEDULED_AT_CUTOFF: 'Agendado no cutoff'
};

const number = (value, digits = 1) => typeof value === 'number' && Number.isFinite(value)
  ? value.toLocaleString('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits }) : '—';
const percent = (value, digits = 1) => typeof value === 'number' && Number.isFinite(value)
  ? `${number(value * 100, digits)}%` : '—';
const datetime = (value) => value ? new Date(value).toLocaleString('pt-BR', {
  timeZone: 'America/Sao_Paulo', day: '2-digit', month: '2-digit', year: 'numeric',
  hour: '2-digit', minute: '2-digit'
}) : 'Não disponível';
const lineLabel = (prop) => prop.market === 'anytime_td' ? 'Marca TD' : `${prop.side === 'under' ? 'Under' : 'Over'} ${number(prop.line, 1)}`;

function useHashGame() {
  const read = () => decodeURIComponent(location.hash.match(/^#\/game\/(.+)$/)?.[1] || '');
  const [gameId, setGameId] = useState(read);
  useEffect(() => {
    const change = () => setGameId(read());
    addEventListener('hashchange', change);
    return () => removeEventListener('hashchange', change);
  }, []);
  return gameId;
}

function App() {
  const [data, setData] = useState(EMPTY_DATA);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState('games');
  const [filters, setFilters] = useState({ search: '', position: '', market: '', minOdds: 1.5, onlyQuoted: false });
  const [sortBy, setSortBy] = useState('quality');
  const gameId = useHashGame();
  useEffect(() => {
    let active = true;
    const base = import.meta.env.BASE_URL || '/';
    fetch(`${base}data/slate.json`, { cache: 'no-store' })
      .then((response) => { if (!response.ok) throw Error(`HTTP ${response.status}`); return response.json(); })
      .then((payload) => {
        if (!Array.isArray(payload.games) || !Array.isArray(payload.props) || !Array.isArray(payload.matchups)) throw Error('Contrato de dados inválido');
        if (active) setData({ ...EMPTY_DATA, ...payload });
      })
      .catch((reason) => { if (active) setError(String(reason.message || reason)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const game = data.games.find((item) => item.game_id === gameId);
  const matchup = data.matchups.find((item) => item.game_id === gameId);
  const availableEv = hasApprovedEv(data.props);
  const displayed = useMemo(() => sortProps(filterProps(data.props, {
    ...filters, gameId: gameId || '', tdOnly: view === 'td'
  }), sortBy), [data.props, filters, gameId, view, sortBy]);
  const quoted = data.props.filter((prop) => validQuote(prop.quote)).length;
  const openGame = (id) => { location.hash = `#/game/${encodeURIComponent(id)}`; scrollTo({ top: 0, behavior: 'smooth' }); };
  const closeGame = () => { history.pushState('', document.title, `${location.pathname}${location.search}`); dispatchEvent(new HashChangeEvent('hashchange')); };

  return <div className="shell">
    <a className="skip" href="#conteudo">Pular para o conteúdo</a>
    <header className="top">
      <button className="brand" onClick={() => { closeGame(); setView('games'); }} aria-label="Ir para a página inicial">
        <span className="brandicon"><ChartNoAxesCombined size={23} /></span>
        <span><b>NFL INTELLIGENCE</b><small>BETTING ANALYTICS · RESEARCH</small></span>
      </button>
      <span className="pill muted">V1.1 · dados reais</span>
    </header>
    <main id="conteudo">
      <section className="intro">
        <div><h1>{game ? <><button className="back" onClick={closeGame} aria-label="Voltar aos jogos"><ArrowLeft size={20} /></button>{game.away_team} × {game.home_team}</> : view === 'props' ? 'Scanner de player props' : view === 'td' ? 'Análise de Anytime TD' : 'Jogos e evidências'}</h1><p>Distribuições históricas rastreáveis, contexto e limitações explícitas.</p></div>
        <span className="pill"><ShieldCheck size={14} /> Snapshot auditável</span>
      </section>
      <section className="notice" aria-live="polite"><ShieldAlert size={20} /><div><b>Sem aprovação financeira automática · NO_BET</b><span>{error ? `Feed indisponível: ${error}. A interface continua funcional sem fabricar conteúdo.` : loading ? 'Carregando snapshot local…' : 'Recorrência observada não é probabilidade prospectiva. Sem modelo calibrado e quote válida, EV não é exibido.'}</span></div></section>
      <section className="stats" aria-label="Resumo do snapshot"><Stat label="Jogos da rodada" value={data.games.length} /><Stat label="Cenários estatísticos" value={data.props.length} /><Stat label="Cotações verificadas" value={quoted} /><Stat label="Cutoff do snapshot" value={datetime(data.cutoff_utc)} compact /></section>
      {game ? <GamePage game={game} matchup={matchup} props={displayed} /> : <>
        {view === 'games' && <Games games={data.games} week={data.week} onOpen={openGame} />}
        <PropsSection title={view === 'td' ? 'Candidatos descritivos de TD' : 'Hipóteses estatísticas'} props={displayed} filters={filters} setFilters={setFilters} sortBy={sortBy} setSortBy={setSortBy} availableEv={availableEv} tdOnly={view === 'td'} />
      </>}
      <Provenance data={data} />
    </main>
    <nav className="bottom" aria-label="Navegação principal">
      <Nav active={!game && view === 'games'} icon={<CalendarDays />} label="Jogos" onClick={() => { closeGame(); setView('games'); }} />
      <Nav active={!game && view === 'props'} icon={<BarChart3 />} label="Props" onClick={() => { closeGame(); setView('props'); }} />
      <Nav active={!game && view === 'td'} icon={<Trophy />} label="Touchdowns" onClick={() => { closeGame(); setView('td'); }} />
      <Nav icon={<RefreshCw />} label="Atualizar" onClick={() => location.reload()} />
    </nav>
    <footer>Pesquisa quantitativa · nenhuma aposta é executada · custo adicional R$ 0</footer>
  </div>;
}

function Stat({ label, value, compact }) { return <div className="stat"><small>{label}</small><strong className={compact ? 'compact' : ''}>{value}</strong></div>; }
function Nav({ active, icon, label, onClick }) { return <button className={active ? 'active' : ''} onClick={onClick} aria-current={active ? 'page' : undefined}>{React.cloneElement(icon, { size: 20 })}{label}</button>; }

function Games({ games, week, onOpen }) {
  return <section className="section" aria-labelledby="games-title"><div className="sectionhead"><h2 id="games-title"><CalendarDays size={20} /> Jogos da rodada</h2><span className="hint">{week ? `Semana ${week}` : 'Rodada não publicada'}</span></div>
    {games.length ? <div className="games">{games.map((game) => <button key={game.game_id} className="game card" onClick={() => onOpen(game.game_id)}><span><span className="gameTeams"><b>{game.away_team}</b><i>vs</i><b>{game.home_team}</b></span><small>{datetime(game.kickoff_utc)}</small></span><span className={`status ${game.status === 'FINAL' ? 'final' : ''}`}>{STATUS_LABEL[game.status] || game.status}</span><ChevronRight size={19} aria-hidden="true" /></button>)}</div>
      : <Empty icon={<CalendarDays />} title="Nenhum jogo publicado">A aplicação permanece disponível, mas não cria uma rodada fictícia.</Empty>}
  </section>;
}

function GamePage({ game, matchup, props }) {
  return <><section className="gamehero card"><div><span className="eyebrow">Semana {game.week} · {STATUS_LABEL[game.status] || game.status}</span><h2>{game.away_team} <span>@</span> {game.home_team}</h2><p>{datetime(game.kickoff_utc)}</p></div>{game.status === 'FINAL' && <div className="score"><b>{game.away_score}</b><span>–</span><b>{game.home_score}</b></div>}</section>
    <section className="section" aria-labelledby="match-title"><div className="sectionhead"><h2 id="match-title"><Activity size={20} /> Análise do confronto</h2></div>{matchup ? <><div className="callout"><Info size={18} /><p>{matchup.summary}</p></div><div className="teamgrid">{Object.entries(matchup.teams || {}).map(([team, windows]) => <TeamPanel key={team} team={team} windows={windows} />)}</div><DefensePanels context={matchup.defense_vs_position || {}} /><div className="pending card"><UserRoundSearch size={20} /><div><b>QBs e inativos: pendentes</b><p>{matchup.injury_note}</p></div></div></> : <Empty icon={<CircleAlert />} title="Análise pré-jogo indisponível">O snapshot não reconstrói evidência pré-jogo para partidas já iniciadas ou encerradas.</Empty>}</section>
    <PropsSection title="Props deste confronto" props={props} gameMode /></>;
}

function TeamPanel({ team, windows }) {
  return <article className="card teampanel"><h3>{team}</h3><div className="windowtabs">{[['Temporada', windows.season], ['Últimos 5', windows.last5], ['Últimos 3', windows.last3]].map(([label, values]) => <div key={label} className="window"><b>{label}</b><span>{values.games} jogos</span><Metric label="EPA/play" value={number(values.epa_per_play, 3)} /><Metric label="Success Rate" value={percent(values.success_rate)} /><Metric label="Jogadas/jogo" value={number(values.offensive_plays_per_game)} /><Metric label="Passes/jogo" value={number(values.pass_attempts_per_game)} /><Metric label="Corridas/jogo" value={number(values.rush_attempts_per_game)} /></div>)}</div><p className="micro">EPA/dropback, EPA/rush e pace oficial: não disponíveis neste catálogo.</p></article>;
}

function DefensePanels({ context }) {
  return <div className="defensegrid">{Object.entries(context).map(([team, positions]) => <article className="card defense" key={team}><h3>Defesa {team}</h3><div className="tablewrap"><table><thead><tr><th>Pos.</th><th>Jogos</th><th>Targets</th><th>Rec.</th><th>Jardas</th></tr></thead><tbody>{Object.values(positions).map((row) => <tr key={row.position}><th>{row.position}</th><td>{row.games_with_position_events}</td><td>{number(row.targets_allowed_per_game)}</td><td>{number(row.receptions_allowed_per_game)}</td><td>{number(row.receiving_yards_allowed_per_game)}</td></tr>)}</tbody></table></div><p className="micro">Médias por jogo com evento da posição; não é matchup individual nem ajuste causal.</p></article>)}</div>;
}

function PropsSection({ title, props, filters, setFilters, sortBy, setSortBy, availableEv, tdOnly, gameMode }) {
  const controlled = filters && setFilters;
  return <section className="section" aria-labelledby={`${tdOnly ? 'td' : 'props'}-title`}><div className="sectionhead"><h2 id={`${tdOnly ? 'td' : 'props'}-title`}><Filter size={20} /> {title}</h2><span className="hint">{props.length} cenários</span></div>
    {controlled && <div className="filters card"><label className="search"><Search size={17} /><span className="sr-only">Buscar atleta ou mercado</span><input value={filters.search} onChange={(event) => setFilters({ ...filters, search: event.target.value })} placeholder="Atleta, time ou mercado" /></label><label>Posição<select value={filters.position} onChange={(event) => setFilters({ ...filters, position: event.target.value })}><option value="">Todas</option>{['QB', 'RB', 'WR', 'TE'].map((position) => <option key={position}>{position}</option>)}</select></label>{!tdOnly && <label>Mercado<select value={filters.market} onChange={(event) => setFilters({ ...filters, market: event.target.value })}><option value="">Todos</option>{Object.entries(MARKET_LABEL).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>}<label>Odd mínima<select value={filters.minOdds} onChange={(event) => setFilters({ ...filters, minOdds: Number(event.target.value) })}>{[1.5, 1.6, 1.7, 1.8, 2, 2.5, 3].map((value) => <option key={value} value={value}>{number(value, 2)}</option>)}</select></label><label>Ordenar<select value={sortBy} onChange={(event) => setSortBy(event.target.value)}><option value="quality">Qualidade dos dados</option><option value="ev" disabled={!availableEv}>EV validado {!availableEv ? '(indisponível)' : ''}</option></select></label><label className="check"><input type="checkbox" checked={filters.onlyQuoted} onChange={(event) => setFilters({ ...filters, onlyQuoted: event.target.checked })} /> Somente com odds</label><p className="filterhelp">A odd mínima começa em 1,50 e só filtra registros cotados. Análises sem odds continuam visíveis.</p></div>}
    {props.length ? <div className="proplist">{props.map((prop) => <Prop key={prop.id} prop={prop} />)}</div> : <Empty icon={<Info />} title={gameMode ? 'Sem props pré-jogo publicadas' : 'Nenhum cenário neste filtro'}>Sem dados suficientes, quote válida ou elegibilidade confirmada, o sistema preserva NO_BET.</Empty>}
  </section>;
}

function Prop({ prop }) {
  const [open, setOpen] = useState(false);
  const quoteOk = validQuote(prop.quote);
  const ev = approvedEv(prop);
  const history = prop.history || {};
  return <article className="card prop"><button className="prophead" onClick={() => setOpen(!open)} aria-expanded={open}><span className="position">{prop.position}</span><span className="propname"><b>{prop.player_name}</b><small>{prop.team} × {prop.opponent} · {MARKET_LABEL[prop.market] || prop.market}</small></span><span className="line"><b>{lineLabel(prop)}</b><small>{prop.line_kind === 'ANALYTICAL_THRESHOLD_NOT_BOOK_OFFER' ? 'Limiar analítico' : 'Pesquisa TD'}</small></span><span className={`price ${quoteOk ? '' : 'missing'}`}><b>{quoteOk ? number(prop.quote.decimal_odds, 2) : 'Sem odd'}</b><small>{quoteOk ? prop.quote.bookmaker : 'não cotado'}</small></span><ChevronRight className={open ? 'rotated' : ''} size={19} /></button>
    <div className="metrics summarymetrics"><Metric label="Temporada" value={hitLabel(history.season)} /><Metric label="Últimos 5" value={hitLabel(history.last5)} /><Metric label="Últimos 3" value={hitLabel(history.last3)} /><Metric label="Completude" value={`${number(prop.quality?.evidence_completeness_score, 0)}/100`} /><Metric label="EV" value={ev === null ? 'Não aprovado' : percent(ev)} /></div>
    {open && <div className="detail"><div className="distribution"><Distribution label="Temporada" data={history.season} /><Distribution label="Últimos 5" data={history.last5} /><Distribution label="Últimos 3" data={history.last3} /></div><div className="evidencegrid"><Evidence title="O que sustenta" items={prop.evidence?.favors} positive /><Evidence title="O que enfraquece" items={prop.evidence?.weakens} /></div><div className="volume"><h4>Volume e função</h4><div className="metrics"><Metric label="Targets/jogo" value={number(prop.volume?.targets_per_game)} /><Metric label="Recepções/jogo" value={number(prop.volume?.receptions_per_game)} /><Metric label="Carries/jogo" value={number(prop.volume?.carries_per_game)} /><Metric label="Snap share" value={percent(prop.volume?.offensive_snap_share_mean)} /><Metric label="Red zone" value={number(prop.volume?.red_zone_opportunities, 0)} /><Metric label="Goal line ≤5" value={number(prop.volume?.goal_line_opportunities, 0)} /></div></div><p className="micro"><b>{prop.decision}</b> · disponibilidade oficial {prop.eligibility?.status || 'UNVERIFIED'} · recorrência histórica não é probabilidade calibrada.</p></div>}</article>;
}

function hitLabel(data) { return data?.n ? `${data.hit_count}/${data.n} (${percent(data.historical_frequency, 0)})` : '—'; }
function Distribution({ label, data }) { return <div className="dist"><b>{label}</b><span>n={data?.n ?? 0}</span><Metric label="Média" value={number(data?.mean)} /><Metric label="Mediana" value={number(data?.median)} /><Metric label="Desvio" value={number(data?.stddev_sample)} /><Metric label="P25 / P75" value={data ? `${number(data.p25)} / ${number(data.p75)}` : '—'} /><Metric label="Mín. / Máx." value={data ? `${number(data.min)} / ${number(data.max)}` : '—'} /></div>; }
function Evidence({ title, items = [], positive }) { return <div className={positive ? 'evidence positive' : 'evidence'}><h4>{title}</h4><ul>{items.map((item, index) => <li key={index}>{item}</li>)}</ul></div>; }
function Metric({ label, value }) { return <span className="metric"><small>{label}</small><b>{value}</b></span>; }
function Empty({ icon, title, children }) { return <div className="empty">{icon}<b>{title}</b><p>{children}</p></div>; }

function Provenance({ data }) {
  return <section className="section" aria-labelledby="source-title"><div className="sectionhead"><h2 id="source-title"><Database size={20} /> Transparência dos dados</h2></div><div className="card provenance"><dl><div><dt>Snapshot</dt><dd>{data.source_snapshot_id || 'Não publicado'}</dd></div><div><dt>Banco SHA-256</dt><dd>{data.database_sha256 || '—'}</dd></div><div><dt>Cutoff</dt><dd>{datetime(data.cutoff_utc)}</dd></div><div><dt>Publicado</dt><dd>{datetime(data.generated_at_utc || data.published_at_utc)}</dd></div><div><dt>Estado</dt><dd>{data.status}</dd></div><div><dt>Identidades pendentes</dt><dd>{data.pending_identity_audit_rows ?? '—'}</dd></div></dl><p>Fonte estatística: NFLverse via catálogo canônico. Este é um snapshot congelado, não um placar ao vivo. Odds de outra casa nunca representam a Stake.</p></div></section>;
}

if ('serviceWorker' in navigator) addEventListener('load', () => navigator.serviceWorker.register(`${import.meta.env.BASE_URL || '/'}sw.js`).catch(() => {}));
createRoot(document.getElementById('root')).render(<App />);
