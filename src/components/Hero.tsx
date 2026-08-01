import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import BrandGlyph from './BrandGlyph';
import { BRAND_ICONS } from './logos/brandIcons';
import MigrationDiagram, { type ActiveCloud } from './MigrationDiagram';
import { withBase } from '../lib/paths';

const CLOUD_LOGOS = ['aws', 'azure', 'googlecloudsvg'] as const;

const ROTATING = ['across any cloud', 'to AWS', 'to Azure', 'to GCP'];

// Maps the rotating headline word to the diagram's active source cloud, so the migration
// visual isn't decorative -- the connector for whichever cloud the headline is currently
// naming lights up. 'across any cloud' has no single source, so all three light up evenly.
const ROTATING_CLOUD: ActiveCloud[] = [null, 'aws', 'azure', 'gcp'];

// Solid per-brand colors for the rotating headline word -- AWS orange, Azure blue, Google's
// four-color scheme split across the letters. 'across any cloud' stays solid ink (no single
// brand to anchor to, and a gradient fill here would read as decorative rather than factual).
const ROTATING_COLOR: Record<string, string | null> = {
  'across any cloud': null,
  'to AWS': '#FF9900',
  'to Azure': '#0078D4',
  'to GCP': null,
};

export default function Hero() {
  const [word, setWord] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setWord((w) => (w + 1) % ROTATING.length), 2600);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="hero-split grid items-center gap-10 py-12 md:py-16 lg:grid-cols-[7fr_5fr] lg:gap-16">
      <div>
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
          className="mb-6 flex items-center gap-5"
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
          <span className="inline-block min-w-[3ch]">
            <AnimatePresence mode="wait">
              <motion.span
                key={word}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }}
                transition={{ duration: 0.35, ease: 'easeOut' }}
                className="inline-block"
              >
                {ROTATING[word] === 'to GCP' ? (
                  <>
                    to{' '}
                    <span style={{ color: '#4285F4' }}>G</span>
                    <span style={{ color: '#EA4335' }}>C</span>
                    <span style={{ color: '#34A853' }}>P</span>
                  </>
                ) : ROTATING_COLOR[ROTATING[word]] ? (
                  <span style={{ color: ROTATING_COLOR[ROTATING[word]]! }}>{ROTATING[word]}</span>
                ) : (
                  <span className="text-[var(--ink)]">{ROTATING[word]}</span>
                )}
              </motion.span>
            </AnimatePresence>
          </span>
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2, ease: 'easeOut' }}
          className="mb-8 max-w-xl text-lg text-[var(--ink-muted)]"
        >
          A deeply detailed, practical runbook for platform teams, cloud architects, and security engineers moving Databricks between Azure, AWS, and GCP.
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3, ease: 'easeOut' }}
          className="flex flex-wrap items-center gap-4"
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

      <motion.div
        initial={{ opacity: 0, x: 16 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.6, delay: 0.25, ease: 'easeOut' }}
        className="flex justify-center rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] p-6 md:p-8 lg:justify-end"
      >
        <MigrationDiagram activeCloud={ROTATING_CLOUD[word]} />
      </motion.div>
    </div>
  );
}
