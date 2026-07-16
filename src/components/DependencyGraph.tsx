import React, { useState, useMemo, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  Layers,
  X,
  Network,
  Move,
} from 'lucide-react';
import sampleData from '../data/sampleDependencies.json';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GraphNode {
  id: string;
  type: string;
  label: string;
  group: string;
}

interface GraphEdge {
  source: string;
  target: string;
}

interface SampleDataShape {
  nodes: GraphNode[];
  edges: GraphEdge[];
  nodeTypes: string[];
  nodeColors: Record<string, string>;
}

const data = sampleData as unknown as SampleDataShape;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const NODE_R = 22;
const SVG_W = 800;
const SVG_H = 600;

const NODE_COLORS: Record<string, string> = data.nodeColors;

const NODE_TYPE_LABELS: Record<string, string> = {
  workspace: 'Workspace',
  datasource: 'Data Source',
  pipeline: 'Pipeline',
  notebook: 'Notebook',
  dashboard: 'Dashboard',
};

// ---------------------------------------------------------------------------
// Layout helper — distribute nodes in type-specific regions
// ---------------------------------------------------------------------------

function calcPositions(nodes: GraphNode[]): Record<string, { x: number; y: number }> {
  const cx = SVG_W / 2;
  const cy = SVG_H / 2;

  const regions: Record<
    string,
    { xr: [number, number]; yr: [number, number] }
  > = {
    workspace: { xr: [40, 200], yr: [cy - 110, cy + 110] },
    datasource: { xr: [240, 560], yr: [45, 180] },
    pipeline: { xr: [290, 510], yr: [cy - 90, cy + 90] },
    notebook: { xr: [600, 760], yr: [cy - 110, cy + 110] },
    dashboard: { xr: [300, 500], yr: [450, 570] },
  };

  const out: Record<string, { x: number; y: number }> = {};

  for (const [type, { xr, yr }] of Object.entries(regions)) {
    const typed = nodes.filter((n) => n.type === type);
    const n = typed.length;
    if (!n) continue;
    const cols = Math.max(Math.ceil(Math.sqrt(n)), 1);
    const rows = Math.max(Math.ceil(n / cols), 1);
    typed.forEach((node, i) => {
      const col = i % cols;
      const row = Math.floor(i / cols);
      out[node.id] = {
        x: xr[0] + (col + 0.5) * ((xr[1] - xr[0]) / cols),
        y: yr[0] + (row + 0.5) * ((yr[1] - yr[0]) / rows),
      };
    });
  }

  return out;
}

// ---------------------------------------------------------------------------
// Edge path — quadratic bezier with perpendicular offset
// ---------------------------------------------------------------------------

function edgePath(
  x1: number, y1: number,
  x2: number, y2: number,
): string {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const dist = Math.sqrt(dx * dx + dy * dy) || 1;
  // Terminate at circle boundary
  const sx = x1 + (dx / dist) * NODE_R;
  const sy = y1 + (dy / dist) * NODE_R;
  const ex = x2 - (dx / dist) * NODE_R;
  const ey = y2 - (dy / dist) * NODE_R;

  const nx = -dy / dist;
  const ny = dx / dist;
  const off = Math.min(dist * 0.18, 45);

  const mx = (sx + ex) / 2 + nx * off;
  const my = (sy + ey) / 2 + ny * off;

  return `M ${sx} ${sy} Q ${mx} ${my} ${ex} ${ey}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DependencyGraph() {
  const [selected, setSelected] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all');
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const [nodePositions, setNodePositions] = useState<
    Record<string, { x: number; y: number }>
  >(() => calcPositions(data.nodes));

  // Drag / pan internal
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef({
    active: false as false | 'node' | 'pan',
    nodeId: '',
    startSvgX: 0,
    startSvgY: 0,
    nodeOrigX: 0,
    nodeOrigY: 0,
    panOrigX: 0,
    panOrigY: 0,
  });

  // -----------------------------------------------------------------------
  // Derived
  // -----------------------------------------------------------------------

  const filteredNodes = useMemo(
    () =>
      filter === 'all'
        ? data.nodes
        : data.nodes.filter((n) => n.type === filter),
    [filter],
  );

  const filteredIds = useMemo(
    () => new Set(filteredNodes.map((n) => n.id)),
    [filteredNodes],
  );

  const visibleEdges = useMemo(
    () =>
      data.edges.filter(
        (e) => filteredIds.has(e.source) && filteredIds.has(e.target),
      ),
    [filteredIds],
  );

  const neighborSet = useMemo(() => {
    if (!hovered) return new Set<string>();
    const s = new Set<string>([hovered]);
    for (const e of data.edges) {
      if (e.source === hovered) s.add(e.target);
      if (e.target === hovered) s.add(e.source);
    }
    return s;
  }, [hovered]);

  const selectedNode = useMemo(
    () => data.nodes.find((n) => n.id === selected) ?? null,
    [selected],
  );

  const selectedConnections = useMemo(() => {
    if (!selected) return [];
    return data.edges
      .filter((e) => e.source === selected || e.target === selected)
      .map((e) => {
        const otherId = e.source === selected ? e.target : e.source;
        const other = data.nodes.find((n) => n.id === otherId);
        return { edge: e, other: other! };
      })
      .filter((c) => c.other);
  }, [selected]);

  const isTransitioning = useRef(false);

  // -----------------------------------------------------------------------
  // Coordinate helpers
  // -----------------------------------------------------------------------

  const clientToSvg = useCallback(
    (clientX: number, clientY: number) => {
      const rect = svgRef.current?.getBoundingClientRect();
      if (!rect) return { x: 0, y: 0 };
      return {
        x: (clientX - rect.left - transform.x) / transform.scale,
        y: (clientY - rect.top - transform.y) / transform.scale,
      };
    },
    [transform],
  );

  // -----------------------------------------------------------------------
  // Handlers
  // -----------------------------------------------------------------------

  const zoomIn = useCallback(() => {
    setTransform((p) => ({ ...p, scale: Math.min(p.scale * 1.35, 5) }));
  }, []);

  const zoomOut = useCallback(() => {
    setTransform((p) => ({ ...p, scale: Math.max(p.scale / 1.35, 0.25) }));
  }, []);

  const resetView = useCallback(() => {
    setTransform({ x: 0, y: 0, scale: 1 });
    setNodePositions(calcPositions(data.nodes));
  }, []);

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (e.button !== 0) return;
      const el = e.target as Element;
      const nodeId = el.closest('[data-node-id]')?.getAttribute('data-node-id');

      const svgPt = clientToSvg(e.clientX, e.clientY);

      if (nodeId && nodePositions[nodeId]) {
        // --- node drag ---
        dragRef.current = {
          active: 'node',
          nodeId,
          startSvgX: svgPt.x,
          startSvgY: svgPt.y,
          nodeOrigX: nodePositions[nodeId].x,
          nodeOrigY: nodePositions[nodeId].y,
          panOrigX: 0,
          panOrigY: 0,
        };
        (e.target as Element).setPointerCapture?.(e.pointerId);
        setSelected(nodeId);
      } else {
        // --- background pan ---
        dragRef.current = {
          active: 'pan',
          nodeId: '',
          startSvgX: 0,
          startSvgY: 0,
          nodeOrigX: 0,
          nodeOrigY: 0,
          panOrigX: transform.x,
          panOrigY: transform.y,
        };
        // store client coords directly
        dragRef.current.startSvgX = e.clientX;
        dragRef.current.startSvgY = e.clientY;
        (e.target as Element).setPointerCapture?.(e.pointerId);
      }
    },
    [clientToSvg, nodePositions, transform.x, transform.y],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      const drag = dragRef.current;
      if (!drag.active) return;

      if (drag.active === 'node') {
        const svgPt = clientToSvg(e.clientX, e.clientY);
        const dx = svgPt.x - drag.startSvgX;
        const dy = svgPt.y - drag.startSvgY;
        setNodePositions((prev) => ({
          ...prev,
          [drag.nodeId]: {
            x: drag.nodeOrigX + dx,
            y: drag.nodeOrigY + dy,
          },
        }));
      } else {
        // pan
        const dx = e.clientX - drag.startSvgX;
        const dy = e.clientY - drag.startSvgY;
        setTransform((prev) => ({
          ...prev,
          x: drag.panOrigX + dx,
          y: drag.panOrigY + dy,
        }));
      }
    },
    [clientToSvg],
  );

  const handlePointerUp = useCallback(() => {
    dragRef.current.active = false;
  }, []);

  // -----------------------------------------------------------------------
  // Render helpers
  // -----------------------------------------------------------------------

  const nodeFill = useCallback(
    (id: string, type: string) => {
      if (!hovered) return NODE_COLORS[type] ?? '#888';
      return neighborSet.has(id) ? NODE_COLORS[type] ?? '#888' : `${NODE_COLORS[type]}44`;
    },
    [hovered, neighborSet],
  );

  const nodeStroke = useCallback(
    (id: string, type: string) => {
      const base = NODE_COLORS[type] ?? '#888';
      if (selected === id) return '#fff';
      if (hovered === id) return '#fff';
      if (!hovered || neighborSet.has(id)) return base;
      return `${base}44`;
    },
    [hovered, neighborSet, selected],
  );

  const edgeOpacity = useCallback(
    (edge: GraphEdge) => {
      if (!hovered) return 0.25;
      return neighborSet.has(edge.source) && neighborSet.has(edge.target) ? 0.45 : 0.04;
    },
    [hovered, neighborSet],
  );

  const labelOpacity = useCallback(
    (id: string) => {
      if (!hovered) return 1;
      return neighborSet.has(id) ? 1 : 0.2;
    },
    [hovered, neighborSet],
  );

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] p-6 md:p-8"
    >
      {/* ---- Header ---- */}
      <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-semibold text-[var(--ink)]">
            <Network className="h-6 w-6 text-[var(--accent)]" />
            Dependency Graph Viewer
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-[var(--ink-muted)]">
            Explore relationships between workspaces, data sources, pipelines,
            notebooks, and dashboards.
          </p>
        </div>
        <motion.button
          type="button"
          onClick={resetView}
          whileHover={{ scale: 1.04 }}
          whileTap={{ scale: 0.96 }}
          className="inline-flex items-center gap-1.5 self-start rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm font-medium text-[var(--ink-muted)] transition-colors hover:border-[var(--accent)]/40 hover:text-[var(--accent)]"
        >
          <Maximize2 className="h-4 w-4" />
          Reset
        </motion.button>
      </div>

      {/* ---- Filter bar + legend ---- */}
      <div className="mb-5 flex flex-wrap items-center gap-4">
        {/* Filter buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-1 flex items-center gap-1 text-xs font-medium uppercase tracking-wider text-[var(--ink-subtle)]">
            <Layers className="h-3.5 w-3.5" />
            Filter
          </span>
          <button
            type="button"
            onClick={() => setFilter('all')}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
              filter === 'all'
                ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]'
                : 'border-[var(--border)] text-[var(--ink-muted)] hover:border-[var(--ink-subtle)]'
            }`}
          >
            All
          </button>
          {data.nodeTypes.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setFilter(t)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                filter === t
                  ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]'
                  : 'border-[var(--border)] text-[var(--ink-muted)] hover:border-[var(--ink-subtle)]'
              }`}
            >
              {NODE_TYPE_LABELS[t] ?? t}
            </button>
          ))}
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-3 border-l border-[var(--border)] pl-4">
          {data.nodeTypes.map((t) => (
            <span key={t} className="flex items-center gap-1.5 text-xs text-[var(--ink-muted)]">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: NODE_COLORS[t] ?? '#888' }}
              />
              {NODE_TYPE_LABELS[t] ?? t}
            </span>
          ))}
        </div>
      </div>

      {/* ---- SVG Graph Area ---- */}
      <div className="relative min-h-[500px] overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)]">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${SVG_W} ${SVG_H}`}
          className="h-auto w-full"
          style={{ touchAction: 'none', cursor: dragRef.current.active === 'pan' ? 'grabbing' : 'grab' }}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
        >
          {/* Zoom/pan transform group */}
          <g
            transform={`translate(${transform.x}, ${transform.y}) scale(${transform.scale})`}
            style={{ transformOrigin: '0 0' }}
          >
            {/* ---- Edges ---- */}
            {visibleEdges.map((edge) => {
              const src = nodePositions[edge.source];
              const tgt = nodePositions[edge.target];
              if (!src || !tgt) return null;
              return (
                <path
                  key={`${edge.source}→${edge.target}`}
                  d={edgePath(src.x, src.y, tgt.x, tgt.y)}
                  fill="none"
                  stroke="var(--ink)"
                  strokeWidth={1.5}
                  opacity={edgeOpacity(edge)}
                  className="transition-opacity duration-200"
                />
              );
            })}

            {/* ---- Nodes ---- */}
            {filteredNodes.map((node) => {
              const pos = nodePositions[node.id];
              if (!pos) return null;
              const color = NODE_COLORS[node.type] ?? '#888';
              const isSelected = selected === node.id;
              const isHovered = hovered === node.id;

              return (
                <g
                  key={node.id}
                  data-node-id={node.id}
                  style={{ cursor: 'pointer' }}
                  onPointerEnter={() => setHovered(node.id)}
                  onPointerLeave={() => setHovered((h) => (h === node.id ? null : h))}
                >
                  {/* Hover ring */}
                  {(isHovered || isSelected) && (
                    <circle
                      cx={pos.x}
                      cy={pos.y}
                      r={NODE_R + 5}
                      fill="none"
                      stroke={color}
                      strokeWidth={2}
                      opacity={0.35}
                      className="pointer-events-none"
                    />
                  )}

                  {/* Circle */}
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={NODE_R}
                    fill={nodeFill(node.id, node.type)}
                    stroke={nodeStroke(node.id, node.type)}
                    strokeWidth={isSelected ? 2.5 : isHovered ? 2 : 1.5}
                    className="transition-[stroke,fill] duration-150"
                  />

                  {/* Type icon indicator — small dot or simple shape */}
                  <text
                    x={pos.x}
                    y={pos.y + 1}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fill="#fff"
                    fontSize={14}
                    fontWeight={600}
                    className="pointer-events-none select-none"
                    style={{ fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif' }}
                  >
                    {node.type === 'workspace'
                      ? 'W'
                      : node.type === 'datasource'
                        ? 'D'
                        : node.type === 'pipeline'
                          ? 'P'
                          : node.type === 'notebook'
                            ? 'N'
                            : 'V'}
                  </text>

                  {/* Label */}
                  <text
                    x={pos.x}
                    y={pos.y + NODE_R + 16}
                    textAnchor="middle"
                    fill="var(--ink)"
                    fontSize={11}
                    fontWeight={500}
                    opacity={labelOpacity(node.id)}
                    className="pointer-events-none select-none transition-opacity duration-200"
                    style={{ fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif' }}
                  >
                    {node.label}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>

        {/* ---- Zoom controls overlay ---- */}
        <div className="absolute right-3 top-3 flex flex-col gap-1.5">
          <button
            type="button"
            onClick={zoomIn}
            aria-label="Zoom in"
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] text-[var(--ink-muted)] shadow-sm transition-colors hover:text-[var(--accent)]"
          >
            <ZoomIn className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={zoomOut}
            aria-label="Zoom out"
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] text-[var(--ink-muted)] shadow-sm transition-colors hover:text-[var(--accent)]"
          >
            <ZoomOut className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={resetView}
            aria-label="Reset view"
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] text-[var(--ink-muted)] shadow-sm transition-colors hover:text-[var(--accent)]"
          >
            <Maximize2 className="h-4 w-4" />
          </button>
        </div>

        {/* Pan hint */}
        <div className="pointer-events-none absolute bottom-3 left-3 flex items-center gap-1.5 rounded-lg bg-[var(--surface-elevated)]/80 px-2.5 py-1 text-[10px] text-[var(--ink-subtle)] backdrop-blur-sm">
          <Move className="h-3 w-3" />
          Drag background to pan · Drag node to rearrange
        </div>
      </div>

      {/* ---- Info panel ---- */}
      <AnimatePresence>
        {selectedNode && (
          <motion.div
            key={selectedNode.id}
            initial={{ opacity: 0, y: 16, height: 0 }}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, y: 8, height: 0 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
            className="mt-4 overflow-hidden"
          >
            <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
              {/* Header row */}
              <div className="mb-4 flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    <span
                      className="inline-block h-3 w-3 rounded-full"
                      style={{
                        backgroundColor: NODE_COLORS[selectedNode.type] ?? '#888',
                      }}
                    />
                    <span
                      className="rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide"
                      style={{
                        backgroundColor: `${NODE_COLORS[selectedNode.type] ?? '#888'}1A`,
                        color: NODE_COLORS[selectedNode.type] ?? '#888',
                      }}
                    >
                      {NODE_TYPE_LABELS[selectedNode.type] ?? selectedNode.type}
                    </span>
                  </div>
                  <h3 className="text-lg font-semibold text-[var(--ink)]">
                    {selectedNode.label}
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setSelected(null)}
                  className="rounded-lg p-1 text-[var(--ink-subtle)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]"
                  aria-label="Close info panel"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Details */}
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="mb-1 text-xs font-medium uppercase tracking-wider text-[var(--ink-subtle)]">
                    ID
                  </p>
                  <p className="font-mono text-sm text-[var(--ink)]">
                    {selectedNode.id}
                  </p>
                </div>
                <div>
                  <p className="mb-1 text-xs font-medium uppercase tracking-wider text-[var(--ink-subtle)]">
                    Group
                  </p>
                  <p className="text-sm text-[var(--ink)]">{selectedNode.group}</p>
                </div>
              </div>

              {/* Connections */}
              {selectedConnections.length > 0 && (
                <div className="mt-4 border-t border-[var(--border)] pt-4">
                  <p className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--ink-subtle)]">
                    Connected to ({selectedConnections.length})
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {selectedConnections.map((c) => (
                      <button
                        key={c.other.id}
                        type="button"
                        onClick={() => setSelected(c.other.id)}
                        className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-1 text-xs font-medium text-[var(--ink)] transition-colors hover:border-[var(--accent)]/40 hover:text-[var(--accent)]"
                      >
                        <span
                          className="inline-block h-2 w-2 rounded-full"
                          style={{
                            backgroundColor:
                              NODE_COLORS[c.other.type] ?? '#888',
                          }}
                        />
                        {c.other.label}
                        <span className="text-[10px] text-[var(--ink-subtle)]">
                          ({c.other.type})
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
