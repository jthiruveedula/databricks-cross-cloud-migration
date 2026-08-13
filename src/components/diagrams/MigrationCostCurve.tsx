import React from 'react';

/**
 * Line chart: cost multiple against elapsed weeks, across a full migration.
 *
 * Static SVG, no client: directive, themed from CSS custom properties.
 *
 * The chart exists to make one point a table cannot: the 2x peak is narrow and
 * the elevated tail is long. Reading the same numbers as rows, people budget
 * for the peak and are surprised by the tail.
 */

interface Point {
  week: number;
  multiple: number;
  label?: string;
}

const SERIES: Point[] = [
  { week: 0, multiple: 1.0 },
  { week: 6, multiple: 1.0, label: 'discovery' },
  { week: 7, multiple: 1.15 },
  { week: 10, multiple: 1.15, label: 'pilot' },
  { week: 11, multiple: 1.6 },
  { week: 16, multiple: 1.6, label: 'bulk' },
  { week: 17, multiple: 2.0 },
  { week: 19, multiple: 2.0, label: 'cutover' },
  { week: 20, multiple: 1.4 },
  { week: 22, multiple: 1.4, label: 'wind-down' },
  { week: 23, multiple: 1.05 },
  { week: 35, multiple: 1.05, label: 'retention' },
  { week: 36, multiple: 1.0 },
  { week: 40, multiple: 1.0 },
];

const X0 = 96;
const X1 = 896;
const Y0 = 96; // y for 2.0x
const Y1 = 400; // y for 1.0x
const WEEK_MAX = 40;

const sx = (w: number) => X0 + (w / WEEK_MAX) * (X1 - X0);
const sy = (m: number) => Y1 - ((m - 1.0) / 1.0) * (Y1 - Y0);

export default function MigrationCostCurve() {
  const line = SERIES.map((p, i) => `${i === 0 ? 'M' : 'L'} ${sx(p.week).toFixed(1)} ${sy(p.multiple).toFixed(1)}`).join(' ');
  const area = `${line} L ${sx(WEEK_MAX).toFixed(1)} ${Y1} L ${X0} ${Y1} Z`;
  const tailStart = sx(23);
  const tailEnd = sx(35);
  const peakStart = sx(17);
  const peakEnd = sx(19);

  return (
    <figure className="my-8 overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <svg
        viewBox="0 0 1000 520"
        role="img"
        aria-labelledby="cost-curve-title cost-curve-desc"
        className="min-w-[720px] w-full"
      >
        <title id="cost-curve-title">Migration cost multiple over time</title>
        <desc id="cost-curve-desc">
          A line chart of platform cost as a multiple of steady-state target cost across forty
          weeks. Cost rises through discovery and pilot, reaches roughly 1.6 times during bulk
          migration, peaks at 2 times for the three weeks of cutover and hypercare, then falls to a
          long shallow tail of about 1.05 times through the retention period before returning to 1
          times once the source is deleted. The peak is narrow; the elevated tail is roughly four
          times longer.
        </desc>

        {/* Horizontal gridlines at each 0.25x */}
        {[1.0, 1.25, 1.5, 1.75, 2.0].map((m) => (
          <g key={m}>
            <line x1={X0} y1={sy(m)} x2={X1} y2={sy(m)} stroke="var(--border)" strokeWidth="0.8" />
            <text
              x={X0 - 12}
              y={sy(m) + 4}
              fill="var(--ink-subtle)"
              fontSize="9"
              fontFamily="'Geist Mono', monospace"
              textAnchor="end"
            >
              {m.toFixed(2)}x
            </text>
          </g>
        ))}

        {/* Tail band -- the editorial point of the chart */}
        <rect x={tailStart} y={Y0} width={tailEnd - tailStart} height={Y1 - Y0} fill="var(--accent-soft)" opacity="0.55" />
        <text
          x={(tailStart + tailEnd) / 2}
          y={Y0 - 12}
          fill="var(--accent)"
          fontSize="9"
          fontWeight="600"
          fontFamily="'Geist', system-ui, sans-serif"
          textAnchor="middle"
        >
          the tail — 13 weeks
        </text>

        {/* Peak marker */}
        <text
          x={(peakStart + peakEnd) / 2}
          y={Y0 - 12}
          fill="var(--ink-muted)"
          fontSize="9"
          fontFamily="'Geist Mono', monospace"
          textAnchor="middle"
        >
          PEAK — 3 WKS
        </text>

        <path d={area} fill="var(--ink)" opacity="0.06" />
        <path d={line} fill="none" stroke="var(--ink)" strokeWidth="2" strokeLinejoin="round" />

        {/* Axes */}
        <line x1={X0} y1={Y1} x2={X1} y2={Y1} stroke="var(--ink-muted)" strokeWidth="1" />
        {[0, 8, 16, 24, 32, 40].map((w) => (
          <g key={w}>
            <line x1={sx(w)} y1={Y1} x2={sx(w)} y2={Y1 + 6} stroke="var(--ink-muted)" strokeWidth="1" />
            <text
              x={sx(w)}
              y={Y1 + 24}
              fill="var(--ink-subtle)"
              fontSize="9"
              fontFamily="'Geist Mono', monospace"
              textAnchor="middle"
            >
              wk {w}
            </text>
          </g>
        ))}
        <text
          x={X0}
          y="72"
          fill="var(--ink-muted)"
          fontSize="8"
          fontFamily="'Geist Mono', monospace"
          letterSpacing="0.14em"
        >
          COST MULTIPLE VS STEADY-STATE TARGET
        </text>

        {/* Phase labels below the axis */}
        {[
          { at: 3, text: 'discovery' },
          { at: 8.5, text: 'pilot' },
          { at: 13.5, text: 'bulk' },
          { at: 18, text: 'cutover' },
          { at: 21, text: 'wind-down' },
          { at: 29, text: 'retention' },
        ].map((p) => (
          <text
            key={p.text}
            x={sx(p.at)}
            y={Y1 + 44}
            fill="var(--ink-muted)"
            fontSize="9"
            fontFamily="'Geist', system-ui, sans-serif"
            textAnchor="middle"
          >
            {p.text}
          </text>
        ))}

        {/* Legend strip */}
        <line x1="40" y1="464" x2="960" y2="464" stroke="var(--border)" strokeWidth="0.8" />
        <text
          x="40"
          y="484"
          fill="var(--ink-muted)"
          fontSize="8"
          fontFamily="'Geist Mono', monospace"
          letterSpacing="0.14em"
        >
          LEGEND
        </text>
        <rect x="132" y="474" width="12" height="12" rx="2" fill="var(--accent-soft)" stroke="var(--accent)" />
        <text x="152" y="484" fill="var(--ink-muted)" fontSize="9" fontFamily="'Geist Mono', monospace">
          elevated tail — longer than the peak, and the part budgets miss
        </text>
      </svg>
    </figure>
  );
}
