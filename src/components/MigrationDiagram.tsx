import React, { useEffect, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import BrandGlyph from './BrandGlyph';
import { BRAND_ICONS } from './logos/brandIcons';

export type ActiveCloud = 'aws' | 'azure' | 'gcp' | null;

interface Source {
  key: 'aws' | 'azure' | 'gcp';
  label: string;
  icon: keyof typeof BRAND_ICONS;
  color: string;
  x: number;
}

// Panel geometry in a fixed viewBox so the connector paths are exact, hand-drawn
// orthogonal elbows -- the same visual language a real architecture diagram uses. Clouds
// sit UNDERNEATH, Databricks sits ON TOP, connectors rising into it -- Databricks is the
// platform layer; any of the three clouds is just the infra it runs on.
const VB_W = 360;
const VB_H = 220;
const TARGET_X = 180;
const TARGET_Y = 40;
const MID_Y = 118;
const SOURCE_Y = 182;

const SOURCES: Source[] = [
  { key: 'aws', label: 'AWS', icon: 'aws', color: '#FF9900', x: 62 },
  { key: 'azure', label: 'Azure', icon: 'azure', color: '#0078D4', x: 180 },
  { key: 'gcp', label: 'Google Cloud', icon: 'googlecloudsvg', color: '#34A853', x: 298 },
];

// A polyline as a flat list of waypoints; used both to draw the connector and to place a
// packet at an arbitrary distance `t` (0-1) along it, regardless of how many elbows it has.
function waypoints(sx: number): [number, number][] {
  return [
    [sx, SOURCE_Y - 16],
    [sx, MID_Y],
    [TARGET_X, MID_Y],
    [TARGET_X, TARGET_Y + 22],
  ];
}

function pathD(points: [number, number][]) {
  return points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ');
}

function pointAtT(points: [number, number][], t: number): [number, number] {
  const lens = points.slice(1).map((p, i) => Math.hypot(p[0] - points[i][0], p[1] - points[i][1]));
  const total = lens.reduce((a, b) => a + b, 0);
  let dist = t * total;
  for (let i = 0; i < lens.length; i++) {
    if (dist <= lens[i] || i === lens.length - 1) {
      const segT = lens[i] === 0 ? 0 : dist / lens[i];
      const [x1, y1] = points[i];
      const [x2, y2] = points[i + 1];
      return [x1 + (x2 - x1) * segT, y1 + (y2 - y1) * segT];
    }
    dist -= lens[i];
  }
  return points[0];
}

export default function MigrationDiagram({ activeCloud }: { activeCloud: ActiveCloud }) {
  const reducedMotion = useReducedMotion();
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (reducedMotion) return;
    let raf: number;
    const start = performance.now();
    const loop = (now: number) => {
      setTick(((now - start) / 1600) % 1);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [reducedMotion]);

  return (
    <div className="relative w-full max-w-md">
      <svg
        viewBox={`0 0 ${VB_W} ${VB_H}`}
        className="w-full"
        role="img"
        aria-label="Diagram: Databricks runs on top of AWS, Azure, or Google Cloud"
      >
        {/* Connectors, rising from each cloud into Databricks. */}
        {SOURCES.map((s) => {
          const active = activeCloud === null || activeCloud === s.key;
          return (
            <path
              key={s.key}
              d={pathD(waypoints(s.x))}
              fill="none"
              stroke={active ? s.color : 'var(--border)'}
              strokeWidth={active ? 2 : 1.5}
              opacity={active ? 0.9 : 0.4}
              className="transition-[stroke,opacity] duration-300"
            />
          );
        })}

        {/* Moving packet on each active connector -- the one meaningful motion in the
            diagram: it shows a migration literally in flight, only on the stream(s) the
            headline is currently naming. */}
        {!reducedMotion &&
          SOURCES.map((s) => {
            const active = activeCloud === null || activeCloud === s.key;
            if (!active) return null;
            const [x, y] = pointAtT(waypoints(s.x), tick);
            return <circle key={s.key} cx={x} cy={y} r={3.5} fill={s.color} />;
          })}

        {/* Source nodes -- the infra layer, underneath. */}
        {SOURCES.map((s) => {
          const active = activeCloud === null || activeCloud === s.key;
          return (
            <g key={s.key} transform={`translate(${s.x}, ${SOURCE_Y})`}>
              <rect
                x={-56}
                y={-16}
                width={112}
                height={32}
                rx={8}
                fill="var(--surface)"
                stroke={active ? s.color : 'var(--border)'}
                strokeWidth={active ? 1.5 : 1}
                opacity={active ? 1 : 0.6}
                className="transition-[stroke,opacity] duration-300"
              />
              {/* A small light chip behind every source logo -- several of these brand marks
                  (AWS's wordmark especially) are dark-on-transparent and wash out against a
                  dark surface otherwise. Guarantees contrast in both themes. */}
              <rect x={-48} y={-12} width={24} height={24} rx={5} fill="#ffffff" />
              <foreignObject x={-47} y={-11} width={22} height={22}>
                <BrandGlyph icon={BRAND_ICONS[s.icon]} className="h-[22px] w-[22px]" brandColor />
              </foreignObject>
              <text x={-16} y={5} fontSize="11.5" fontWeight={600} fill="var(--ink)" fontFamily="Inter, sans-serif">
                {s.label}
              </text>
            </g>
          );
        })}

        {/* Databricks -- the platform layer, on top. Always the brighter, receiving end,
            since it's the one constant regardless of which cloud is underneath it. */}
        <g transform={`translate(${TARGET_X}, ${TARGET_Y})`}>
          <rect x={-58} y={-20} width={116} height={40} rx={10} fill="var(--accent-soft)" stroke="var(--accent)" strokeWidth={1.75} />
          <foreignObject x={-48} y={-13} width={26} height={26}>
            <BrandGlyph icon={BRAND_ICONS.databricks} className="h-[26px] w-[26px]" brandColor />
          </foreignObject>
          <text x={-10} y={5} fontSize="13" fontWeight={700} fill="var(--accent)" fontFamily="Inter, sans-serif">
            Databricks
          </text>
        </g>
      </svg>
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4, duration: 0.5 }}
        className="mt-2 text-center text-xs text-[var(--ink-subtle)]"
      >
        One platform, installed on whichever cloud you run.
      </motion.p>
    </div>
  );
}
