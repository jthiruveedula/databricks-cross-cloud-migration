import React, { useState, useCallback, useEffect, useRef } from 'react';
import { motion, useAnimationControls, AnimatePresence } from 'framer-motion';

const PHASES = [
  {
    id: 1, title: 'Discovery', subtitle: 'Assess & inventory',
    desc: 'Inventory workspaces, assets, dependencies & risks. Map network topology and assess migration readiness.',
    duration: 'Wk 1–4',
  },
  {
    id: 2, title: 'Foundation', subtitle: 'Landing zone & IAM',
    desc: 'Set up target cloud landing zone, networking, identity, governance policies, and Unity Catalog metastore.',
    duration: 'Wk 3–8',
  },
  {
    id: 3, title: 'Data Migration', subtitle: 'Storage & catalog',
    desc: 'Migrate object storage, databases, external locations, and the Hive Metastore to Unity Catalog.',
    duration: 'Wk 5–16',
  },
  {
    id: 4, title: 'Compute & Pipelines', subtitle: 'Clusters & jobs',
    desc: 'Recreate clusters, policies, instance profiles, workflows, DLT pipelines, and CI/CD promotion chains.',
    duration: 'Wk 8–20',
  },
  {
    id: 5, title: 'Validation', subtitle: 'Test & benchmark',
    desc: 'Technical validation, data reconciliation, performance benchmarking, security review, and business UAT sign-off.',
    duration: 'Wk 14–24',
  },
  {
    id: 6, title: 'Cutover', subtitle: 'Switch & rollback',
    desc: 'Blue-green cutover with traffic switch, DNS changes, monitoring hooks, and verified rollback procedure.',
    duration: 'Wk 20–26',
  },
  {
    id: 7, title: 'Hypercare', subtitle: 'Monitor & handover',
    desc: 'Active monitoring, performance tuning, cost optimization, incident response, documentation, and team handover.',
    duration: 'Wk 24–30',
  },
];

const CARD_W = 180;
const CARD_H = 80;
const ROW1_Y = 24;
const ROW2_Y = 180;
const GAP = 24;
const TOTAL_W = CARD_W * 4 + GAP * 3;
const ROW1_X = (w: number) => (w - TOTAL_W) / 2;

function cardCenter(idx: number, containerW: number) {
  const r1x = ROW1_X(containerW);
  if (idx < 4) {
    return { cx: r1x + CARD_W / 2 + idx * (CARD_W + GAP), cy: ROW1_Y + CARD_H / 2 };
  }
  const row2Count = 3;
  const row2TotalW = CARD_W * row2Count + GAP * (row2Count - 1);
  const r2x = (containerW - row2TotalW) / 2;
  const i = idx - 4;
  return { cx: r2x + CARD_W / 2 + i * (CARD_W + GAP), cy: ROW2_Y + CARD_H / 2 };
}

type AnimState = 'idle' | 'playing' | 'paused' | 'done';

export default function MigrationFlowDiagram() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerW, setContainerW] = useState(800);
  const [animState, setAnimState] = useState<AnimState>('idle');
  const [speed, setSpeed] = useState(1);
  const [currentPhase, setCurrentPhase] = useState(0);
  const [selectedPhase, setSelectedPhase] = useState<number | null>(null);
  const progressRef = useRef(0);
  const animRef = useRef<number | null>(null);
  const controls = useAnimationControls();

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerW(entry.contentRect.width);
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const phaseCenters = PHASES.map((_, i) => cardCenter(i, containerW));

  const buildPath = useCallback(() => {
    const pts = phaseCenters;
    const r1End = { cx: pts[3].cx + CARD_W / 2, cy: pts[3].cy };
    const r2Start = { cx: pts[4].cx, cy: pts[4].cy - CARD_H / 2 };
    const midY = (r1End.cy + r2Start.cy) / 2;
    let d = `M ${pts[0].cx} ${pts[0].cy}`;
    for (let i = 1; i < 4; i++) d += ` L ${pts[i].cx} ${pts[i].cy}`;
    d += ` L ${r1End.cx} ${r1End.cy}`;
    d += ` C ${r1End.cx} ${midY}, ${r2Start.cx} ${midY}, ${r2Start.cx} ${r2Start.cy}`;
    for (let i = 4; i < 7; i++) d += ` L ${pts[i].cx} ${pts[i].cy}`;
    return d;
  }, [phaseCenters]);

  const play = useCallback(() => {
    setAnimState('playing');
    const progress = progressRef.current;
    const duration = 8000 / speed;

    controls.start({
      offsetDistance: ['0%', '100%'],
      transition: { duration: duration / 1000, ease: 'linear' },
    });

    const startT = performance.now() - progress * duration;
    animRef.current = requestAnimationFrame(function tick(now) {
      const elapsed = now - startT;
      const p = Math.min(elapsed / duration, 1);
      progressRef.current = p;
      const phaseIdx = Math.min(Math.floor(p * 7), 6);
      setCurrentPhase(phaseIdx);
      if (p >= 1) {
        setAnimState('done');
        controls.stop();
        animRef.current = null;
        return;
      }
      animRef.current = requestAnimationFrame(tick);
    });
  }, [speed, controls]);

  const pause = useCallback(() => {
    setAnimState('paused');
    controls.stop();
    if (animRef.current) cancelAnimationFrame(animRef.current);
  }, [controls]);

  const reset = useCallback(() => {
    if (animRef.current) cancelAnimationFrame(animRef.current);
    controls.stop();
    progressRef.current = 0;
    setAnimState('idle');
    setCurrentPhase(0);
    setSelectedPhase(null);
  }, [controls]);

  const togglePlay = useCallback(() => {
    if (animState === 'playing') pause();
    else play();
  }, [animState, play, pause]);

  const handleCardClick = useCallback((idx: number) => {
    setSelectedPhase(idx === selectedPhase ? null : idx);
  }, [selectedPhase]);

  const svgH = ROW2_Y + CARD_H + 24;
  const scale = containerW > 0 ? Math.min(containerW / 800, 1) : 1;

  const svgW = Math.max(containerW, 320);

  return (
    <div className="migration-flow-diagram" ref={containerRef}>
      <style>{`
        .migration-flow-diagram {
          --flow-accent: var(--accent, #6366f1);
        }
        .flow-controls button {
          cursor: pointer;
        }
        .flow-phase-card {
          cursor: pointer;
          transition: all 0.3s ease;
        }
        .flow-phase-card:hover {
          filter: brightness(1.15);
        }
        .flow-phase-card.active {
          filter: brightness(1.25);
          stroke-width: 2.5;
        }
        .flow-phase-card.pulse-highlight {
          filter: brightness(1.35);
          stroke-width: 3;
        }
        .flow-arrowhead {
          fill: none;
          stroke: var(--border);
          stroke-width: 1.5;
        }
        .flow-arrowhead-marker {
          fill: var(--border);
        }
      `}</style>

      {/* Hover tooltips - adding title attributes for native tooltips */}
      {PHASES.map((p, i) => {
        const c = phaseCenters[i];
        if (!c) return null;
        return (
          <g key={`tooltip-${i}`} transform={`translate(${c.cx - CARD_W/2 + 10}, ${c.cy - CARD_H/2 - 8})`}></g>
        );
      })}

      {/* Top bar */}
      <div className="mb-4 flex items-center justify-between">
        <div className="text-sm font-medium text-[var(--ink-muted)]">
          {animState === 'done'
            ? 'Migration flow complete'
            : animState === 'idle'
              ? 'Click Play to start the migration flow'
              : `Phase ${currentPhase + 1} of 7 — ${PHASES[currentPhase].title}`}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-0.5">
            {[1, 2].map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                className={`rounded-md px-2 py-1 text-xs font-medium transition-colors ${
                  speed === s ? 'bg-[var(--accent)] text-white' : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                }`}
              >
                {s}×
              </button>
            ))}
          </div>
          <button
            onClick={togglePlay}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white shadow-glow transition-transform hover:scale-105 active:scale-95"
          >
            {animState === 'playing' ? (
              <>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><rect x="3" y="2" width="3" height="10" rx="1"/><rect x="8" y="2" width="3" height="10" rx="1"/></svg>
                Pause
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><polygon points="3,1 13,7 3,13"/></svg>
                {animState === 'done' ? 'Replay' : 'Play'}
              </>
            )}
          </button>
          <button
            onClick={reset}
            className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1.5 text-sm text-[var(--ink-muted)] transition-colors hover:text-[var(--ink)]"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 7a5 5 0 1 1 1.5 3.5"/><path d="M2 12V8.5H5.5"/></svg>
          </button>
        </div>
      </div>

      {/* SVG diagram */}
      <div className="relative overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)]">
        <svg
          viewBox={`0 0 ${svgW} ${svgH}`}
          className="w-full"
          style={{ height: svgH * scale }}
        >
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--border)" />
            </marker>
          </defs>

          {/* Static connecting paths */}
          {phaseCenters.length >= 7 && (() => {
            const pts = phaseCenters;
            const r1End = { cx: pts[3].cx + CARD_W / 2, cy: pts[3].cy };
            const r2Start = { cx: pts[4].cx, cy: pts[4].cy - CARD_H / 2 };
            const midY = (r1End.cy + r2Start.cy) / 2;

            // Row 1 arrows
            return (
              <>
                {[0, 1, 2].map((i) => (
                  <line
                    key={`r1-arrow-${i}`}
                    x1={pts[i].cx + CARD_W / 2}
                    y1={pts[i].cy}
                    x2={pts[i + 1].cx - CARD_W / 2}
                    y2={pts[i + 1].cy}
                    stroke="var(--border)"
                    strokeWidth="1.5"
                    strokeDasharray="4 3"
                    markerEnd="url(#arrow)"
                  />
                ))}
                {/* Row 2 arrows */}
                {[5, 6].map((i) => (
                  <line
                    key={`r2-arrow-${i}`}
                    x1={pts[i - 1].cx + CARD_W / 2}
                    y1={pts[i - 1].cy}
                    x2={pts[i].cx - CARD_W / 2}
                    y2={pts[i].cy}
                    stroke="var(--border)"
                    strokeWidth="1.5"
                    strokeDasharray="4 3"
                    markerEnd="url(#arrow)"
                  />
                ))}
                {/* Curve arrow 4→5 */}
                <path
                  d={`M ${r1End.cx} ${r1End.cy} C ${r1End.cx} ${midY}, ${r2Start.cx} ${midY}, ${r2Start.cx} ${r2Start.cy}`}
                  fill="none"
                  stroke="var(--border)"
                  strokeWidth="1.5"
                  strokeDasharray="4 3"
                  markerEnd="url(#arrow)"
                />
              </>
            );
          })()}

          {/* Animated progress pulse along the path */}
          <motion.circle
            r="8"
            fill="var(--accent)"
            style={{
              offsetPath: `path('${buildPath()}')`,
              filter: 'drop-shadow(0 0 8px var(--accent))',
            }}
            animate={controls}
            initial={{ offsetDistance: '0%' }}
          />
          <motion.circle
            r="6"
            fill="white"
            style={{
              offsetPath: `path('${buildPath()}')`,
            }}
            animate={controls}
            initial={{ offsetDistance: '0%' }}
          />

          {/* Phase cards */}
          {PHASES.map((p, i) => {
            const c = phaseCenters[i];
            if (!c) return null;
            const active = i === currentPhase && animState !== 'idle';
            const selected = i === selectedPhase;
            return (
              <g
                key={p.id}
                onClick={() => handleCardClick(i)}
                className="flow-phase-card"
              >
                <rect
                  x={c.cx - CARD_W / 2}
                  y={c.cy - CARD_H / 2}
                  width={CARD_W}
                  height={CARD_H}
                  rx="10"
                  fill={active ? 'var(--accent-soft)' : 'var(--surface)'}
                  stroke={active ? 'var(--accent)' : selected ? 'var(--accent)' : 'var(--border)'}
                  strokeWidth={active ? 2 : selected ? 2 : 1}
                />
                {/* Phase number badge */}
                <rect
                  x={c.cx - CARD_W / 2 + 8}
                  y={c.cy - CARD_H / 2 + 8}
                  width="20"
                  height="20"
                  rx="6"
                  fill={active ? 'var(--accent)' : 'var(--border)'}
                />
                <text
                  x={c.cx - CARD_W / 2 + 18}
                  y={c.cy - CARD_H / 2 + 22}
                  textAnchor="middle"
                  fill={active ? 'white' : 'var(--ink-muted)'}
                  fontSize="11"
                  fontWeight="600"
                >
                  {p.id}
                </text>

                {/* Title */}
                <text
                  x={c.cx + 6}
                  y={c.cy - 6}
                  textAnchor="middle"
                  fill="var(--ink)"
                  fontSize="13"
                  fontWeight="600"
                  className="select-none"
                >
                  {p.title}
                </text>
                {/* Subtitle */}
                <text
                  x={c.cx + 6}
                  y={c.cy + 12}
                  textAnchor="middle"
                  fill="var(--ink-muted)"
                  fontSize="10"
                  className="select-none"
                >
                  {p.subtitle}
                </text>
                {/* Duration badge */}
                <rect
                  x={c.cx - 22}
                  y={c.cy + CARD_H / 2 - 18}
                  width="44"
                  height="14"
                  rx="4"
                  fill={active ? 'var(--accent-soft)' : 'var(--surface)'}
                  stroke={active ? 'var(--accent)' : 'var(--border)'}
                  strokeWidth="0.5"
                />
                <text
                  x={c.cx}
                  y={c.cy + CARD_H / 2 - 8}
                  textAnchor="middle"
                  fill="var(--accent)"
                  fontSize="8"
                  fontWeight="500"
                >
                  {p.duration}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Phase detail panel */}
        <AnimatePresence>
          {selectedPhase !== null && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25, ease: 'easeInOut' }}
              className="overflow-hidden border-t border-[var(--border)]"
            >
              <div className="px-6 py-4">
                <h4 className="mb-1 text-sm font-semibold text-[var(--accent)]">
                  Phase {selectedPhase + 1}: {PHASES[selectedPhase].title}
                </h4>
                <p className="text-sm leading-relaxed text-[var(--ink-muted)]">
                  {PHASES[selectedPhase].desc}
                </p>
                <div className="mt-2 flex items-center gap-4 text-xs text-[var(--ink-muted)]">
                  <span>Duration: <strong className="text-[var(--ink)]">{PHASES[selectedPhase].duration}</strong></span>
                  <span>Type: <strong className="text-[var(--ink)]">Migration phase</strong></span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Phase progress dots */}
        <div className="flex items-center justify-center gap-1.5 border-t border-[var(--border)] px-4 py-2">
          {PHASES.map((p, i) => (
            <button
              key={p.id}
              onClick={() => { setSelectedPhase(i); setCurrentPhase(i); }}
              className={`h-2 rounded-full transition-all duration-300 ${
                i === currentPhase && animState !== 'idle'
                  ? 'w-6 bg-[var(--accent)]'
                  : i === currentPhase
                    ? 'w-3 bg-[var(--accent)]/50'
                    : 'w-2 bg-[var(--border)] hover:bg-[var(--accent)]/40'
              }`}
              title={p.title}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
