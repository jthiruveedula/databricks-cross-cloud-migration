import React from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, Route } from 'lucide-react';
import { withBase } from '../lib/paths';

export default function Hero() {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] px-6 py-16 text-center md:py-24">
      <div className="hero-glow" />
      <div className="hero-orb hero-orb-1" />
      <div className="hero-orb hero-orb-2" />
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
        <motion.h1
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1, ease: 'easeOut' }}
          className="mb-6 text-4xl font-bold tracking-tight md:text-6xl"
        >
          Migrate Databricks <span className="gradient-text">across any cloud</span>
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