import React from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, Compass } from 'lucide-react';
import { withBase } from '../lib/paths';

export default function CtaBand() {
  return (
    <motion.section
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-80px' }}
      transition={{ duration: 0.6, ease: 'easeOut' }}
      className="cta-band relative my-16 overflow-hidden rounded-2xl border border-[var(--accent)]/30 p-10 text-center md:p-16"
    >
      <div className="cta-glow" />
      <div className="relative z-10 mx-auto max-w-2xl">
        <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-4 py-1.5 text-sm font-medium text-[var(--accent)]">
          <Compass className="h-4 w-4" />
          Your migration, sequenced
        </div>
        <h2 className="mb-4 text-3xl font-bold tracking-tight text-[var(--ink)] md:text-4xl">
          Ready to move Databricks across clouds?
        </h2>
        <p className="mb-8 text-lg text-[var(--ink-muted)]">
          Start with the decision framework, or jump straight to execution and plan your first wave. Every section links to the next, so the runbook reads like a path, not a pile of docs.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-4">
          <a
            href={withBase('/overview/decision-framework')}
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-6 py-3 font-medium text-white shadow-glow transition-transform hover:-translate-y-0.5 active:translate-y-0"
          >
            Plan your migration <ArrowRight className="h-4 w-4" />
          </a>
          <a
            href={withBase('/tools')}
            className="inline-flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-6 py-3 font-medium text-[var(--ink)] transition-colors hover:bg-[var(--surface-hover)] active:scale-[0.98]"
          >
            Open the toolset
          </a>
        </div>
      </div>
    </motion.section>
  );
}
