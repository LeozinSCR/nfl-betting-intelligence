import React from 'react';

export const WINDOWS = [
  ['season', 'Temporada'],
  ['last5', 'Últimos 5'],
  ['last3', 'Últimos 3']
];

export const isNumber = (value) => typeof value === 'number' && Number.isFinite(value);
export const number = (value, digits = 1) => isNumber(value)
  ? value.toLocaleString('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits }) : '—';
export const percent = (value, digits = 1) => isNumber(value)
  ? `${number(value * 100, digits)}%` : '—';

export function Metric({ label, value }) {
  return <span className="metric"><small>{label}</small><b>{value}</b></span>;
}

export function RateBar({ value }) {
  if (!isNumber(value) || value < 0 || value > 1) return null;
  return <span className="rate-track" aria-hidden="true"><span style={{ width: `${value * 100}%` }} /></span>;
}

export function ObservedFrequency({ history }) {
  return <div className="frequency">
    <h4>Frequência observada</h4>
    <div className="frequency-grid">{WINDOWS.map(([key, label]) => {
      const data = history[key];
      const available = data?.n > 0 && isNumber(data.hit_count) && isNumber(data.historical_frequency);
      return <div className="frequency-window" key={key}>
        <small>{label}</small>
        <b>{available ? percent(data.historical_frequency, 0) : '—'}</b>
        {available && <><RateBar value={data.historical_frequency} /><span>{data.hit_count} de {data.n} jogos</span></>}
      </div>;
    })}</div>
  </div>;
}

function QuantilePlot({ data, bounds }) {
  const quantiles = [data.min, data.p25, data.p50, data.p75, data.max];
  if (!bounds?.every(isNumber) || !quantiles.every(isNumber)
    || quantiles.some((value, index) => index > 0 && value < quantiles[index - 1])) return null;
  const [lower, upper] = bounds;
  if (upper < lower || data.min < lower || data.max > upper) return null;

  // Keep the common scale across windows and center constant samples.
  const at = (value) => upper === lower ? 50 : 3 + 94 * (value - lower) / (upper - lower);
  const [min, p25, p50, p75, max] = quantiles.map(at);
  return <div className="quantile-plot" aria-hidden="true">
    <span className="plot-range" style={{ left: `${min}%`, width: `${max - min}%` }} />
    <span className="plot-iqr" style={{ left: `${p25}%`, width: `${p75 - p25}%` }} />
    <span className="plot-median" style={{ left: `${p50}%` }} />
  </div>;
}

function Distribution({ label, data, bounds }) {
  const available = data?.n > 0;
  return <article className="dist">
    <header><h5>{label}</h5><span>{available ? `n = ${data.n}` : 'Sem amostra'}</span></header>
    {available && <>
      <QuantilePlot data={data} bounds={bounds} />
      <div className="dist-numbers">
        <Metric label="Média" value={number(data.mean)} />
        <Metric label="Desvio-padrão" value={number(data.stddev_sample)} />
        <Metric label="Mínimo" value={number(data.min)} />
        <Metric label="Máximo" value={number(data.max)} />
        <Metric label="P25" value={number(data.p25)} />
        <Metric label="Mediana (P50)" value={number(data.p50 ?? data.median)} />
        <Metric label="P75" value={number(data.p75)} />
        <Metric label="P90" value={number(data.p90)} />
      </div>
    </>}
  </article>;
}

export function HistoryDistribution({ history, unit }) {
  const bounds = [history.season?.min, history.season?.max];
  return <div className="history-distribution">
    <h4>Distribuição por janela <small>{unit}</small></h4>
    <p className="micro">Escala comum da temporada. Traço fino entre mínimo e máximo, faixa entre P25 e P75 e marca na mediana.</p>
    <div className="distribution">{WINDOWS.map(([key, label]) =>
      <Distribution key={key} label={label} data={history[key]} bounds={bounds} />
    )}</div>
  </div>;
}
