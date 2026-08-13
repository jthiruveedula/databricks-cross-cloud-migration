import React from 'react';

/**
 * Swimlane: who does what on cutover night, and where the handoffs land.
 *
 * Static SVG, no client: directive, themed from CSS custom properties so it
 * follows the site's light/dark toggle.
 *
 * The table this sits beside lists the same eight steps correctly. What a
 * numbered list cannot show is that the work crosses five teams and changes
 * hands seven times -- and that one of those handoffs is the point after which
 * rollback stops being cheap.
 */

interface Step {
  n: number;
  lane: number;
  title: string;
  sub: string;
}

// Six owners in the prose collapse to five lanes: the source table already
// splits "Data team" and "QA / data team", which in practice is one group.
const LANES = ['Migration PMO', 'Platform', 'Data & QA', 'Network', 'Application'];

const STEPS: Step[] = [
  { n: 1, lane: 0, title: 'Announce', sub: 'maintenance window' },
  { n: 2, lane: 1, title: 'Pause source', sub: 'jobs and writes' },
  { n: 3, lane: 2, title: 'Final sync', sub: 'incremental' },
  { n: 4, lane: 2, title: 'Reconcile', sub: 'go / no-go' },
  { n: 5, lane: 3, title: 'Switch', sub: 'endpoints, DNS' },
  { n: 6, lane: 1, title: 'Enable jobs', sub: 'dependency order' },
  { n: 7, lane: 4, title: 'Verify runs', sub: 'first target runs' },
  { n: 8, lane: 0, title: 'Open channel', sub: 'hypercare support' },
];

// The handoff after which rollback stops being cheap: QA signs off, the
// network team commits the switch.
const FOCAL_HANDOFF = 4;

const LABEL_W = 112;
const X0 = 128;
const PITCH = 104;
const BOX_W = 80;
const BOX_H = 48;
const LANE_H = 72;
const TOP = 96;
const R = 8;

const boxX = (i: number) => X0 + i * PITCH;
const laneTop = (l: number) => TOP + l * LANE_H;
const boxY = (l: number) => laneTop(l) + 12;
const midY = (l: number) => laneTop(l) + 36;

/** Rounded right-angle elbow between two step boxes. */
function elbow(from: Step, to: Step): string {
  const x1 = boxX(STEPS.indexOf(from)) + BOX_W;
  const x2 = boxX(STEPS.indexOf(to));
  const y1 = midY(from.lane);
  const y2 = midY(to.lane);
  if (y1 === y2) return `M ${x1} ${y1} L ${x2} ${y2}`;
  const mx = (x1 + x2) / 2;
  const down = y2 > y1;
  const s = down ? 1 : -1;
  return [
    `M ${x1} ${y1}`,
    `L ${mx - R} ${y1}`,
    `Q ${mx} ${y1} ${mx} ${y1 + s * R}`,
    `L ${mx} ${y2 - s * R}`,
    `Q ${mx} ${y2} ${mx + R} ${y2}`,
    `L ${x2} ${y2}`,
  ].join(' ');
}

export default function CutoverSwimlane() {
  const bottom = TOP + LANES.length * LANE_H;
  const legendY = bottom + 56;

  return (
    <figure className="my-8 overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <svg
        viewBox="0 0 1000 560"
        role="img"
        aria-labelledby="cutover-lane-title cutover-lane-desc"
        className="min-w-[820px] w-full"
      >
        <title id="cutover-lane-title">Cutover night, by owner</title>
        <desc id="cutover-lane-desc">
          A swimlane of the eight cutover steps across five teams. The migration PMO announces the
          window and later opens the support channel; the platform team pauses the source and later
          enables target jobs; data and QA run the final sync and reconciliation; the network team
          switches endpoints; and application teams verify the first target runs. The handoff from
          reconciliation to the endpoint switch is marked as the point after which rollback stops
          being cheap.
        </desc>

        <defs>
          <marker id="cut-arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="var(--ink-subtle)" />
          </marker>
          <marker id="cut-arrow-accent" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="var(--accent)" />
          </marker>
        </defs>

        <text
          x="24"
          y="72"
          fill="var(--ink-muted)"
          fontSize="8"
          fontFamily="'Geist Mono', monospace"
          letterSpacing="0.14em"
        >
          CUTOVER NIGHT — 7 HANDOFFS ACROSS 5 TEAMS
        </text>

        {/* Lanes */}
        {LANES.map((lane, l) => (
          <g key={lane}>
            <line
              x1="24"
              y1={laneTop(l)}
              x2="976"
              y2={laneTop(l)}
              stroke="var(--border)"
              strokeWidth="0.8"
            />
            <text
              x="24"
              y={midY(l) + 4}
              fill="var(--ink-muted)"
              fontSize="9"
              fontFamily="'Geist Mono', monospace"
              letterSpacing="0.06em"
            >
              {lane}
            </text>
          </g>
        ))}
        <line x1="24" y1={bottom} x2="976" y2={bottom} stroke="var(--border)" strokeWidth="0.8" />
        <line
          x1={LABEL_W}
          y1={TOP}
          x2={LABEL_W}
          y2={bottom}
          stroke="var(--border)"
          strokeWidth="0.8"
        />

        {/* Connectors first, so boxes sit on top */}
        {STEPS.slice(0, -1).map((step, i) => {
          const next = STEPS[i + 1];
          const focal = step.n === FOCAL_HANDOFF;
          return (
            <path
              key={`edge-${step.n}`}
              d={elbow(step, next)}
              fill="none"
              stroke={focal ? 'var(--accent)' : 'var(--ink-subtle)'}
              strokeWidth={focal ? 1.5 : 1}
              markerEnd={focal ? 'url(#cut-arrow-accent)' : 'url(#cut-arrow)'}
            />
          );
        })}

        {/* Steps */}
        {STEPS.map((step, i) => {
          const x = boxX(i);
          const y = boxY(step.lane);
          return (
            <g key={step.n}>
              <rect x={x} y={y} width={BOX_W} height={BOX_H} rx="6" fill="var(--surface)" />
              <rect
                x={x}
                y={y}
                width={BOX_W}
                height={BOX_H}
                rx="6"
                fill="var(--surface-elevated)"
                stroke="var(--border)"
                strokeWidth="1"
              />
              <text
                x={x + 8}
                y={y + 14}
                fill="var(--ink-subtle)"
                fontSize="8"
                fontFamily="'Geist Mono', monospace"
              >
                {step.n}
              </text>
              <text
                x={x + BOX_W / 2}
                y={y + 28}
                fill="var(--ink)"
                fontSize="11"
                fontWeight="600"
                fontFamily="'Geist', system-ui, sans-serif"
                textAnchor="middle"
              >
                {step.title}
              </text>
              <text
                x={x + BOX_W / 2}
                y={y + 41}
                fill="var(--ink-muted)"
                fontSize="8"
                fontFamily="'Geist Mono', monospace"
                textAnchor="middle"
              >
                {step.sub}
              </text>
            </g>
          );
        })}

        {/* Focal handoff annotation, placed clear of the connector */}
        <text
          x={boxX(4) + BOX_W / 2}
          y={laneTop(3) + 68}
          fill="var(--accent)"
          fontSize="9"
          fontWeight="600"
          fontFamily="'Geist', system-ui, sans-serif"
          textAnchor="middle"
        >
          rollback stops being cheap here
        </text>

        {/* Legend strip */}
        <line x1="24" y1={legendY - 20} x2="976" y2={legendY - 20} stroke="var(--border)" strokeWidth="0.8" />
        <text
          x="24"
          y={legendY}
          fill="var(--ink-muted)"
          fontSize="8"
          fontFamily="'Geist Mono', monospace"
          letterSpacing="0.14em"
        >
          LEGEND
        </text>
        <line
          x1="128"
          y1={legendY - 4}
          x2="160"
          y2={legendY - 4}
          stroke="var(--accent)"
          strokeWidth="1.5"
          markerEnd="url(#cut-arrow-accent)"
        />
        <text x="172" y={legendY} fill="var(--ink-muted)" fontSize="9" fontFamily="'Geist Mono', monospace">
          the handoff that ends cheap rollback — everything after it is fix-forward
        </text>
      </svg>
    </figure>
  );
}
