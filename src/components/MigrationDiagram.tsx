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
  y: number; // 0-1 vertical slot among the three source rows
}

const SOURCES: Source[] = [
  { key: 'aws', label: 'AWS', icon: 'aws', color: '#FF9900', y: 0 },
  { key: 'azure', label: 'Azure', icon: 'azure', color: '#0078D4', y: 1 },
  { key: 'gcp', label: 'Google Cloud', icon: 'googlecloudsvg', color: '#34A853', y: 2 },
];

// Panel geometry in a fixed viewBox so the connector paths are exact, hand-drawn
// orthogonal elbows -- the same visual language a real architecture diagram uses, not an
// abstract line. Reads as "here is the system," not "here is some ambient motion."
const VB_W = 360;
const VB_H = 220;
const SOURCE_X = 92;
const TARGET_X = 268;
const ROW_Y = [46, 110, 174];
const TARGET_Y = 110;
const ELBOW_X = 180;

function connectorPath(sourceY: number) {
  return `M ${SOURCE_X} ${sourceY} H ${ELBOW_X} V ${TARGET_Y} H ${TARGET_X}`;
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
        aria-label="Diagram: AWS, Azure, and Google Cloud each connect to Databricks"
      >
        {/* Connectors, drawn first so nodes sit on top of the line ends. */}
        {SOURCES.map((s) => {
          const active = activeCloud === null || activeCloud === s.key;
          return (
            <path
              key={s.key}
              d={connectorPath(ROW_Y[s.y])}
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
            const sourceY = ROW_Y[s.y];
            // Piecewise-linear position along the 3-segment elbow, parameterized 0-1.
            const legs = [
              { from: [SOURCE_X, sourceY], to: [ELBOW_X, sourceY] },
              { from: [ELBOW_X, sourceY], to: [ELBOW_X, TARGET_Y] },
              { from: [ELBOW_X, TARGET_Y], to: [TARGET_X, TARGET_Y] },
            ];
            const legLenX = Math.abs(legs[0].to[0] - legs[0].from[0]);
            const legLenY = Math.abs(legs[1].to[1] - legs[1].from[1]);
            const legLenX2 = Math.abs(legs[2].to[0] - legs[2].from[0]);
            const total = legLenX + legLenY + legLenX2;
            const dist = tick * total;
            let x: number, y: number;
            if (dist <= legLenX) {
              const t = legLenX === 0 ? 0 : dist / legLenX;
              x = legs[0].from[0] + (legs[0].to[0] - legs[0].from[0]) * t;
              y = sourceY;
            } else if (dist <= legLenX + legLenY) {
              const t = legLenY === 0 ? 0 : (dist - legLenX) / legLenY;
              x = ELBOW_X;
              y = legs[1].from[1] + (legs[1].to[1] - legs[1].from[1]) * t;
            } else {
              const t = legLenX2 === 0 ? 0 : (dist - legLenX - legLenY) / legLenX2;
              x = ELBOW_X + (legs[2].to[0] - legs[2].from[0]) * t;
              y = TARGET_Y;
            }
            return <circle key={s.key} cx={x} cy={y} r={3.5} fill={s.color} />;
          })}

        {/* Source nodes */}
        {SOURCES.map((s) => {
          const active = activeCloud === null || activeCloud === s.key;
          return (
            <g key={s.key} transform={`translate(${SOURCE_X}, ${ROW_Y[s.y]})`}>
              <rect
                x={-72}
                y={-16}
                width={144}
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
              <rect x={-65} y={-12} width={24} height={24} rx={5} fill="#ffffff" />
              <foreignObject x={-64} y={-11} width={22} height={22}>
                <BrandGlyph icon={BRAND_ICONS[s.icon]} className="h-[22px] w-[22px]" brandColor />
              </foreignObject>
              <text x={-32} y={5} fontSize="12" fontWeight={600} fill="var(--ink)" fontFamily="Inter, sans-serif">
                {s.label}
              </text>
            </g>
          );
        })}

        {/* Databricks target node -- always the brighter, receiving end. */}
        <g transform={`translate(${TARGET_X}, ${TARGET_Y})`}>
          <rect
            x={-56}
            y={-20}
            width={112}
            height={40}
            rx={10}
            fill="var(--accent-soft)"
            stroke="var(--accent)"
            strokeWidth={1.75}
          />
          <foreignObject x={-46} y={-13} width={26} height={26}>
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
        One target platform, wherever the workload runs today.
      </motion.p>
    </div>
  );
}
