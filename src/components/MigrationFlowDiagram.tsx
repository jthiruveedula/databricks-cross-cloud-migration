import React, { useState, useCallback, useEffect, useRef, useLayoutEffect } from 'react';
import { motion, useAnimationControls, AnimatePresence } from 'framer-motion';
import { Search, Compass, Database, Boxes, ShieldCheck, Flag, Activity, RotateCcw, ChevronLeft, ChevronRight } from 'lucide-react';

interface Phase {
  id: number;
  title: string;
  subtitle: string;
  desc: string;
  duration: string;
  color: string;
  icon: React.ElementType;
}

// Same seven phases, same hex values as TimelineEstimator's PHASE_META -- one color
// language for "migration phase" across the whole site, not just this component.
const PHASES: Phase[] = [
  { id: 1, title: 'Discovery', subtitle: 'Assess & inventory', color: '#8B5CF6', icon: Search,
    desc: 'Inventory workspaces, assets, dependencies & risks. Map network topology and assess migration readiness.', duration: 'Wk 1–4' },
  { id: 2, title: 'Foundation', subtitle: 'Landing zone & IAM', color: '#3B82F6', icon: Compass,
    desc: 'Set up target cloud landing zone, networking, identity, governance policies, and Unity Catalog metastore.', duration: 'Wk 3–8' },
  { id: 3, title: 'Data Migration', subtitle: 'Storage & catalog', color: '#10B981', icon: Database,
    desc: 'Migrate object storage, databases, external locations, and the Hive Metastore to Unity Catalog.', duration: 'Wk 5–16' },
  { id: 4, title: 'Compute & Pipelines', subtitle: 'Clusters & jobs', color: '#F59E0B', icon: Boxes,
    desc: 'Recreate clusters, policies, instance profiles, workflows, DLT pipelines, and CI/CD promotion chains.', duration: 'Wk 8–20' },
  { id: 5, title: 'Validation', subtitle: 'Test & benchmark', color: '#F97316', icon: ShieldCheck,
    desc: 'Technical validation, data reconciliation, performance benchmarking, security review, and business UAT sign-off.', duration: 'Wk 14–24' },
  { id: 6, title: 'Cutover', subtitle: 'Switch & rollback', color: '#EF4444', icon: Flag,
    desc: 'Blue-green cutover with traffic switch, DNS changes, monitoring hooks, and verified rollback procedure.', duration: 'Wk 20–26' },
  { id: 7, title: 'Hypercare', subtitle: 'Monitor & handover', color: '#EC4899', icon: Activity,
    desc: 'Active monitoring, performance tuning, cost optimization, incident response, documentation, and team handover.', duration: 'Wk 24–30' },
];

type AnimState = 'idle' | 'playing' | 'paused' | 'done';

// One smooth spline through however many card centers exist, in DOM order --
// generalizes to any flex-wrap row split instead of a hardcoded two-row shape.
function splinePath(points: { x: number; y: number }[]): string {
  if (points.length < 2) return '';
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] || points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2] || p2;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${c1x} ${c1y}, ${c2x} ${c2y}, ${p2.x} ${p2.y}`;
  }
  return d;
}

export default function MigrationFlowDiagram() {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const cardRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const [points, setPoints] = useState<{ x: number; y: number }[]>([]);
  const [stageSize, setStageSize] = useState({ w: 0, h: 0 });
  // Single-row timeline that scrolls horizontally rather than wrapping -- seven cards at a
  // fixed width don't fit most containers on one line, and wrapping onto a second row forced
  // the connector spline to zigzag down and back up between rows. A scrollable rail (same
  // pattern as a CI pipeline or deploy-history view) keeps the flow reading as one continuous
  // line at any container width.
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateScrollState = useCallback(() => {
    const el = scrollAreaRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft < el.scrollWidth - el.clientWidth - 4);
  }, []);

  const scrollByCards = useCallback((dir: 1 | -1) => {
    scrollAreaRef.current?.scrollBy({ left: dir * 200, behavior: 'smooth' });
  }, []);

  const [animState, setAnimState] = useState<AnimState>('idle');
  const [currentPhase, setCurrentPhase] = useState(0);
  const [selectedPhase, setSelectedPhase] = useState<number | null>(null);
  const progressRef = useRef(0);
  const animRef = useRef<number | null>(null);
  const controls = useAnimationControls();

  const measure = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;
    const containerRect = container.getBoundingClientRect();
    const next = cardRefs.current.map((el) => {
      if (!el) return { x: 0, y: 0 };
      const r = el.getBoundingClientRect();
      return { x: r.left - containerRect.left + r.width / 2, y: r.top - containerRect.top + r.height / 2 };
    });
    setPoints(next);
    setStageSize({ w: containerRect.width, h: container.scrollHeight });
  }, []);

  useLayoutEffect(() => {
    measure();
    updateScrollState();
    const ro = new ResizeObserver(() => {
      measure();
      updateScrollState();
    });
    if (containerRef.current) ro.observe(containerRef.current);
    window.addEventListener('resize', measure);
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', measure);
    };
  }, [measure, updateScrollState]);

  // Keeps the card rail panned in sync with the playhead -- without this, autoplay reaches
  // phases 6-7 while the rail is still showing 1-3, so the "active" card the user is
  // supposed to be watching is scrolled off-screen.
  const scrollRailToProgress = useCallback((p: number) => {
    const el = scrollAreaRef.current;
    if (!el) return;
    const max = el.scrollWidth - el.clientWidth;
    if (max <= 0) return;
    el.scrollLeft = p * max;
    updateScrollState();
  }, [updateScrollState]);

  // Fixed autoplay pace -- no user-facing speed control, one consistent duration for the
  // whole flow to play out.
  const PLAY_DURATION_MS = 8000;

  const play = useCallback(() => {
    // Defensive: every current caller already cancels animRef.current before calling play(),
    // but a future caller that doesn't would spawn a second concurrent rAF loop racing the
    // first on progressRef/setCurrentPhase. Guard here too rather than relying on callers.
    if (animRef.current) cancelAnimationFrame(animRef.current);
    setAnimState('playing');
    const progress = progressRef.current;
    const duration = PLAY_DURATION_MS;

    controls.start({
      offsetDistance: ['0%', '100%'],
      transition: { duration: duration / 1000, ease: 'linear' },
    });

    const startT = performance.now() - progress * duration;
    animRef.current = requestAnimationFrame(function tick(now) {
      const elapsed = now - startT;
      const p = Math.min(elapsed / duration, 1);
      progressRef.current = p;
      setCurrentPhase(Math.min(Math.floor(p * PHASES.length), PHASES.length - 1));
      scrollRailToProgress(p);
      if (p >= 1) {
        setAnimState('done');
        controls.stop();
        animRef.current = null;
        return;
      }
      animRef.current = requestAnimationFrame(tick);
    });
  }, [controls, scrollRailToProgress]);

  const pause = useCallback(() => {
    setAnimState('paused');
    controls.stop();
    if (animRef.current) cancelAnimationFrame(animRef.current);
  }, [controls]);

  // Restart plays again from the top -- there's no separate play button, so this
  // is the only way back into autoplay once a card click or the end has stopped it.
  const reset = useCallback(() => {
    if (animRef.current) cancelAnimationFrame(animRef.current);
    controls.stop();
    controls.set({ offsetDistance: '0%' });
    progressRef.current = 0;
    setCurrentPhase(0);
    setSelectedPhase(null);
    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      play();
    } else {
      setAnimState('idle');
    }
  }, [controls, play]);

  // Autoplay on mount -- no play/resume button to press. Respect reduced-motion:
  // land on a static, explorable state instead of an unrequested moving animation.
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    play();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Click-to-seek: jump the play head to any phase directly, rather than only
  // being able to watch it advance -- the interactive win over a passive diagram.
  const seekTrackRef = useRef<HTMLDivElement>(null);
  const seekToFraction = useCallback((frac: number) => {
    if (animRef.current) cancelAnimationFrame(animRef.current);
    controls.stop();
    controls.set({ offsetDistance: `${frac * 100}%` });
    progressRef.current = frac;
    setAnimState('paused');
    const idx = Math.min(Math.floor(frac * PHASES.length), PHASES.length - 1);
    setCurrentPhase(idx);
    scrollRailToProgress(frac);
    return idx;
  }, [controls, scrollRailToProgress]);

  const seekTo = useCallback((clientX: number) => {
    const track = seekTrackRef.current;
    if (!track) return;
    const rect = track.getBoundingClientRect();
    seekToFraction(Math.min(1, Math.max(0, (clientX - rect.left) / rect.width)));
  }, [seekToFraction]);

  // Clicking any card stops autoplay and pins the play head + detail panel on it.
  const selectCard = useCallback((i: number) => {
    seekToFraction(i / (PHASES.length - 1));
    setSelectedPhase((prev) => (prev === i ? null : i));
    cardRefs.current[i]?.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
  }, [seekToFraction]);

  useEffect(() => () => { if (animRef.current) cancelAnimationFrame(animRef.current); }, []);

  const path = splinePath(points);
  const currentPhaseData = PHASES[currentPhase] ?? PHASES[0];
  const activeColor = currentPhaseData.color;
  const selected = selectedPhase !== null ? PHASES[selectedPhase] : null;

  return (
    <div className="migration-flow-diagram">
      {/* Toolbar */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-medium text-[var(--ink-muted)]">
          {animState === 'playing' && (
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-75" style={{ background: activeColor }} />
              <span className="relative inline-flex h-2 w-2 rounded-full" style={{ background: activeColor }} />
            </span>
          )}
          {animState === 'done'
            ? 'Migration flow complete'
            : animState === 'idle'
              ? 'Click any phase, or drag the rail below, to explore'
              : `Phase ${currentPhase + 1} of ${PHASES.length} — ${currentPhaseData.title}`}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={reset}
            aria-label="Restart from the beginning"
            title="Restart"
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1.5 text-sm text-[var(--ink-muted)] transition-colors hover:text-[var(--ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Seek rail */}
      <div
        ref={seekTrackRef}
        role="slider"
        aria-label="Seek migration phase"
        aria-valuemin={1}
        aria-valuemax={PHASES.length}
        aria-valuenow={currentPhase + 1}
        aria-valuetext={currentPhaseData.title}
        tabIndex={0}
        onClick={(e) => seekTo(e.clientX)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowRight') { e.preventDefault(); const i = Math.min(currentPhase + 1, PHASES.length - 1); setCurrentPhase(i); controls.set({ offsetDistance: `${(i / (PHASES.length - 1)) * 100}%` }); setAnimState('paused'); scrollRailToProgress(i / (PHASES.length - 1)); }
          if (e.key === 'ArrowLeft') { e.preventDefault(); const i = Math.max(currentPhase - 1, 0); setCurrentPhase(i); controls.set({ offsetDistance: `${(i / (PHASES.length - 1)) * 100}%` }); setAnimState('paused'); scrollRailToProgress(i / (PHASES.length - 1)); }
        }}
        className="group relative mb-6 h-2 cursor-pointer rounded-full bg-[var(--border)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
      >
        <div
          className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-150"
          style={{ width: `${((currentPhase + (animState === 'playing' ? 0.5 : 0)) / PHASES.length) * 100}%`, background: `linear-gradient(90deg, ${PHASES[0].color}, ${activeColor})` }}
        />
        <div className="pointer-events-none absolute inset-x-0 top-1/2 flex -translate-y-1/2 justify-between px-0.5">
          {PHASES.map((p, i) => (
            <span
              key={p.id}
              className="h-3 w-3 rounded-full ring-2 ring-[var(--surface)] transition-transform duration-200"
              style={{ background: i <= currentPhase ? p.color : 'var(--border)', transform: i === currentPhase ? 'scale(1.3)' : 'scale(1)' }}
            />
          ))}
        </div>
      </div>

      {/* Stage: a single-row, horizontally scrollable timeline -- keeps the connector a
          clean unbroken line at any container width instead of wrapping onto a second row. */}
      <div className="relative overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] p-6">
        <div className="relative">
          <div
            ref={scrollAreaRef}
            onScroll={updateScrollState}
            className="no-scrollbar overflow-x-auto pb-2"
            style={{
              maskImage: `linear-gradient(90deg, ${canScrollLeft ? 'transparent' : 'black'} 0, black 24px, black calc(100% - 24px), ${canScrollRight ? 'transparent' : 'black'} 100%)`,
              WebkitMaskImage: `linear-gradient(90deg, ${canScrollLeft ? 'transparent' : 'black'} 0, black 24px, black calc(100% - 24px), ${canScrollRight ? 'transparent' : 'black'} 100%)`,
            }}
          >
            <div ref={containerRef} className="relative w-max">
              {stageSize.w > 0 && (
                <svg
                  className="pointer-events-none absolute inset-0"
                  width={stageSize.w}
                  height={stageSize.h}
                  viewBox={`0 0 ${stageSize.w} ${stageSize.h}`}
                >
                  <defs>
                    <linearGradient id="flow-rail-gradient" x1="0" y1="0" x2={stageSize.w} y2="0" gradientUnits="userSpaceOnUse">
                      {PHASES.map((p, i) => (
                        <stop key={p.id} offset={`${(i / (PHASES.length - 1)) * 100}%`} stopColor={p.color} />
                      ))}
                    </linearGradient>
                  </defs>
                  <path d={path} fill="none" stroke="var(--border)" strokeWidth={2} strokeDasharray="1 8" strokeLinecap="round" />
                  <path d={path} fill="none" stroke="url(#flow-rail-gradient)" strokeWidth={2} strokeLinecap="round" opacity={0.55} />
                  {path && (
                    <motion.circle
                      r={7}
                      fill={activeColor}
                      style={{ offsetPath: `path('${path}')`, filter: `drop-shadow(0 0 6px ${activeColor})` }}
                      animate={controls}
                      initial={{ offsetDistance: '0%' }}
                    />
                  )}
                </svg>
              )}

              <div className="relative flex gap-4">
                {PHASES.map((p, i) => {
                  const active = i === currentPhase && animState !== 'idle';
                  const isSelected = i === selectedPhase;
                  const Icon = p.icon;
                  return (
                    <button
                      key={p.id}
                      ref={(el) => { cardRefs.current[i] = el; }}
                      onClick={() => selectCard(i)}
                      aria-label={`Phase ${p.id}: ${p.title}, ${p.subtitle}`}
                      aria-expanded={isSelected}
                      className="flow-phase-card w-[168px] shrink-0 rounded-xl border bg-[var(--surface)] p-3.5 text-left transition-all duration-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                      style={{
                        borderColor: active || isSelected ? p.color : 'var(--border)',
                        borderWidth: active || isSelected ? 2 : 1,
                        boxShadow: active ? `0 0 0 3px ${p.color}22, 0 8px 20px -8px ${p.color}55` : isSelected ? `0 0 0 3px ${p.color}22` : 'none',
                        transform: active ? 'translateY(-2px)' : 'none',
                        ['--flow-card-color' as any]: p.color,
                      }}
                    >
                      <div className="mb-2.5 flex items-center gap-2">
                        <span
                          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-white"
                          style={{ background: p.color }}
                        >
                          <Icon className="h-3.5 w-3.5" />
                        </span>
                        <span
                          className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold"
                          style={{ background: `${p.color}1f`, color: p.color }}
                        >
                          {p.id}
                        </span>
                      </div>
                      <div className="mb-0.5 text-sm font-semibold text-[var(--ink)]">{p.title}</div>
                      <div className="mb-2.5 text-xs text-[var(--ink-muted)]">{p.subtitle}</div>
                      <span
                        className="inline-block rounded-full px-2 py-0.5 text-[10px] font-medium"
                        style={{ background: `${p.color}1f`, color: p.color }}
                      >
                        {p.duration}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {canScrollLeft && (
            <button
              onClick={() => scrollByCards(-1)}
              aria-label="Scroll earlier phases into view"
              className="absolute left-1 top-1/2 z-10 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--surface)] text-[var(--ink-muted)] shadow-card transition-colors hover:text-[var(--ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          )}
          {canScrollRight && (
            <button
              onClick={() => scrollByCards(1)}
              aria-label="Scroll later phases into view"
              className="absolute right-1 top-1/2 z-10 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--surface)] text-[var(--ink-muted)] shadow-card transition-colors hover:text-[var(--ink)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Detail panel, color-matched to the selected phase */}
        <AnimatePresence>
          {selected && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
              className="relative mt-5 overflow-hidden"
            >
              <div
                className="rounded-xl border-l-4 bg-[var(--surface-elevated)] p-4"
                style={{ borderLeftColor: selected.color }}
              >
                <h4 className="mb-1 text-sm font-semibold" style={{ color: selected.color }}>
                  Phase {selected.id}: {selected.title}
                </h4>
                <p className="text-sm leading-relaxed text-[var(--ink-muted)]">{selected.desc}</p>
                <div className="mt-2 flex items-center gap-4 text-xs text-[var(--ink-muted)]">
                  <span>Duration: <strong className="text-[var(--ink)]">{selected.duration}</strong></span>
                  <span>Type: <strong className="text-[var(--ink)]">Migration phase</strong></span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
