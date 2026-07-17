import React, { useRef, useState, useEffect } from 'react';
import { motion, AnimatePresence, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import BrandGlyph from './BrandGlyph';
import { BRAND_ICONS } from './logos/brandIcons';
import { withBase } from '../lib/paths';

const CLOUD_LOGOS = ['aws', 'azure', 'googlecloud'] as const;

const ROTATING = ['across any cloud', 'to AWS', 'to Azure', 'to GCP'];

export default function Hero() {
  const ref = useRef<HTMLDivElement>(null);
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const sx = useSpring(mouseX, { stiffness: 60, damping: 18 });
  const sy = useSpring(mouseY, { stiffness: 60, damping: 18 });

  const orb1X = useTransform(sx, [-0.5, 0.5], [18, -18]);
  const orb1Y = useTransform(sy, [-0.5, 0.5], [14, -14]);
  const orb2X = useTransform(sx, [-0.5, 0.5], [-22, 22]);
  const orb2Y = useTransform(sy, [-0.5, 0.5], [-16, 16]);
  const glowX = useTransform(sx, [-0.5, 0.5], [-12, 12]);
  const glowY = useTransform(sy, [-0.5, 0.5], [-10, 10]);

  const [word, setWord] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setWord((w) => (w + 1) % ROTATING.length), 2600);
    return () => clearInterval(id);
  }, []);

  function onMove(e: React.MouseEvent<HTMLDivElement>) {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    mouseX.set((e.clientX - rect.left) / rect.width - 0.5);
    mouseY.set((e.clientY - rect.top) / rect.height - 0.5);
  }

  return (
    <div
      ref={ref}
      onMouseMove={onMove}
      className="relative overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] px-6 py-16 text-center md:py-24"
    >
      <motion.div className="hero-glow" style={{ x: glowX, y: glowY }} />
      <motion.div className="hero-orb hero-orb-1" style={{ x: orb1X, y: orb1Y }} />
      <motion.div className="hero-orb hero-orb-2" style={{ x: orb2X, y: orb2Y }} />
      <div className="hero-orb hero-orb-3" />
      <div className="relative z-10 mx-auto max-w-3xl">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="mb-6 inline-flex items-center gap-2 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-4 py-1.5 text-sm font-medium text-[var(--accent)]"
        >
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--accent)] opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-[var(--accent)]" />
          </span>
          Enterprise runbook v1.0
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.05, ease: 'easeOut' }}
          className="mb-6 flex items-center justify-center gap-5"
        >
          {CLOUD_LOGOS.map((key, i) => (
            <React.Fragment key={key}>
              {i > 0 && <span className="text-[var(--ink-subtle)] text-lg">+</span>}
              <BrandGlyph icon={BRAND_ICONS[key]} className="h-8 w-8 opacity-70 grayscale hover:opacity-100 hover:grayscale-0 transition-all duration-300" />
            </React.Fragment>
          ))}
        </motion.div>
        <motion.h1
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1, ease: 'easeOut' }}
          className="mb-6 text-4xl font-bold tracking-tight md:text-6xl"
        >
          Migrate Databricks{' '}
          <span className="gradient-text inline-block min-w-[3ch]">
            <AnimatePresence mode="wait">
              <motion.span
                key={word}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }}
                transition={{ duration: 0.35, ease: 'easeOut' }}
                className="inline-block"
              >
                {ROTATING[word]}
              </motion.span>
            </AnimatePresence>
          </span>
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2, ease: 'easeOut' }}
          className="mx-auto mb-8 max-w-2xl text-lg text-[var(--ink-muted)]"
        >
          A deeply detailed, practical runbook for platform teams, cloud architects, and security engineers moving Databricks between Azure, AWS, and GCP.
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3, ease: 'easeOut' }}
          className="flex flex-wrap items-center justify-center gap-4"
        >
          <a
            href={withBase('/overview/what-is-cross-cloud-migration')}
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-6 py-3 font-medium text-white shadow-glow transition-transform hover:-translate-y-0.5 active:translate-y-0"
          >
            Start reading <ArrowRight className="h-4 w-4" />
          </a>
          <a
            href={withBase('/execution/wave-planning')}
            className="inline-flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-6 py-3 font-medium text-[var(--ink)] transition-colors hover:bg-[var(--surface-hover)] active:scale-[0.98]"
          >
            Jump to execution
          </a>
        </motion.div>
      </div>
    </div>
  );
}
