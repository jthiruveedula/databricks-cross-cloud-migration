import React from 'react';

/**
 * Layer stack: the order Unity Catalog objects must be created in.
 *
 * Rendered without a client: directive -- this is static SVG, so it ships as
 * server-rendered markup with no JavaScript and no hydration surface.
 *
 * Colours come from the site's CSS custom properties rather than baked hex, so
 * the diagram follows the light/dark theme toggle. A standalone diagram with
 * literal colours would be unreadable in one of the two themes.
 */

interface Layer {
  tag: string;
  name: string;
  sub: string;
  focal?: boolean;
}

// Bottom of the stack is built first. Twelve tiers in the prose collapse to six
// bands here: past six the stack stops reading as a hierarchy and starts
// reading as a list, which a table already does better.
const LAYERS: Layer[] = [
  { tag: 'L6', name: 'Access control', sub: 'row filters, column masks, then grants', focal: true },
  { tag: 'L5', name: 'Derived objects', sub: 'views, functions, models' },
  { tag: 'L4', name: 'Table metadata', sub: 'constraints, tags, comments, properties' },
  { tag: 'L3', name: 'Data', sub: 'volumes, tables — DEEP CLONE or CTAS' },
  { tag: 'L2', name: 'Containers', sub: 'catalogs, schemas — MANAGED LOCATION' },
  { tag: 'L1', name: 'Storage foundation', sub: 'credential, external location' },
];

const BAND_X = 132;
const BAND_W = 632;
const BAND_H = 64;
const PITCH = 68;
const TOP = 96;

export default function MetastoreDependencyStack() {
  const bottom = TOP + (LAYERS.length - 1) * PITCH + BAND_H;
  // The window runs from the moment table data exists (top of L3) to the moment
  // access control lands (bottom of L6).
  const l3Top = TOP + 3 * PITCH;
  const l6Bottom = TOP + BAND_H;
  const legendY = bottom + 56;

  return (
    <figure className="my-8 overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <svg
        viewBox="0 0 1000 620"
        role="img"
        aria-labelledby="uc-dep-title uc-dep-desc"
        className="min-w-[720px] w-full"
      >
        <title id="uc-dep-title">Unity Catalog object dependency order</title>
        <desc id="uc-dep-desc">
          A six-layer stack showing the order metastore objects must be created in, built from the
          bottom up: storage foundation, containers, data, table metadata, derived objects, and
          finally access control. A marked window spans from the point table data exists to the
          point row filters and column masks are bound, during which a migrated table is readable
          but unfiltered.
        </desc>

        {/* Direction indicator, outside the stack */}
        <text
          x="40"
          y={TOP + 14}
          fill="var(--ink-subtle)"
          fontSize="8"
          fontFamily="'Geist Mono', monospace"
          letterSpacing="0.14em"
        >
          BUILD ORDER
        </text>
        <path
          d={`M 52 ${bottom - 8} L 52 ${TOP + 28}`}
          stroke="var(--ink-subtle)"
          strokeWidth="1"
          markerEnd="url(#uc-dep-arrow-up)"
          fill="none"
        />
        <text
          x="40"
          y={bottom + 4}
          fill="var(--ink-subtle)"
          fontSize="8"
          fontFamily="'Geist Mono', monospace"
          letterSpacing="0.14em"
        >
          FIRST
        </text>

        <defs>
          <marker id="uc-dep-arrow-up" markerWidth="8" markerHeight="6" refX="3" refY="5" orient="auto">
            <polygon points="0 6, 4 0, 8 6" fill="var(--ink-subtle)" />
          </marker>
        </defs>

        {LAYERS.map((layer, i) => {
          const y = TOP + i * PITCH;
          const stroke = layer.focal ? 'var(--accent)' : 'var(--border)';
          const fill = layer.focal ? 'var(--accent-soft)' : 'var(--surface-elevated)';
          return (
            <g key={layer.tag}>
              <rect x={BAND_X} y={y} width={BAND_W} height={BAND_H} rx="6" fill={fill} stroke={stroke} strokeWidth="1" />
              <rect
                x={BAND_X + 16}
                y={y + 24}
                width="28"
                height="16"
                rx="2"
                fill="transparent"
                stroke={layer.focal ? 'var(--accent)' : 'var(--ink-subtle)'}
                strokeWidth="0.8"
              />
              <text
                x={BAND_X + 30}
                y={y + 36}
                fill={layer.focal ? 'var(--accent)' : 'var(--ink-muted)'}
                fontSize="8"
                fontFamily="'Geist Mono', monospace"
                textAnchor="middle"
                letterSpacing="0.08em"
              >
                {layer.tag}
              </text>
              <text
                x={BAND_X + 64}
                y={y + 30}
                fill="var(--ink)"
                fontSize="14"
                fontWeight="600"
                fontFamily="'Geist', system-ui, sans-serif"
              >
                {layer.name}
              </text>
              <text
                x={BAND_X + 64}
                y={y + 48}
                fill="var(--ink-muted)"
                fontSize="9"
                fontFamily="'Geist Mono', monospace"
              >
                {layer.sub}
              </text>
            </g>
          );
        })}

        {/* Exposure window bracket, in the right margin */}
        <path
          d={`M 800 ${l6Bottom} L 812 ${l6Bottom} L 812 ${l3Top} L 800 ${l3Top}`}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="1"
          strokeDasharray="4,3"
        />
        <text
          x="824"
          y={(l6Bottom + l3Top) / 2 - 8}
          fill="var(--accent)"
          fontSize="9"
          fontWeight="600"
          fontFamily="'Geist', system-ui, sans-serif"
        >
          Exposure window
        </text>
        <text
          x="824"
          y={(l6Bottom + l3Top) / 2 + 8}
          fill="var(--ink-muted)"
          fontSize="9"
          fontFamily="'Geist Mono', monospace"
        >
          rows readable,
        </text>
        <text
          x="824"
          y={(l6Bottom + l3Top) / 2 + 24}
          fill="var(--ink-muted)"
          fontSize="9"
          fontFamily="'Geist Mono', monospace"
        >
          filters not yet bound
        </text>

        {/* Legend strip */}
        <line
          x1="40"
          y1={legendY - 20}
          x2="960"
          y2={legendY - 20}
          stroke="var(--border)"
          strokeWidth="0.8"
        />
        <text
          x="40"
          y={legendY}
          fill="var(--ink-muted)"
          fontSize="8"
          fontFamily="'Geist Mono', monospace"
          letterSpacing="0.14em"
        >
          LEGEND
        </text>
        <rect x="132" y={legendY - 10} width="12" height="12" rx="2" fill="var(--accent-soft)" stroke="var(--accent)" />
        <text x="152" y={legendY} fill="var(--ink-muted)" fontSize="9" fontFamily="'Geist Mono', monospace">
          access control — the layer that must land before anyone can read
        </text>
      </svg>
    </figure>
  );
}
