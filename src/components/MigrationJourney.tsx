import React, { useRef, useState } from 'react';
import { motion, useScroll, useTransform, useMotionValueEvent } from 'framer-motion';
import {
  Sparkles,
  Search,
  DraftingCompass,
  ArrowRightLeft,
  Flag,
  ArrowRight,
} from 'lucide-react';
import { withBase } from '../lib/paths';

interface Chapter {
  key: string;
  eyebrow: string;
  title: string;
  icon: React.ElementType;
  narrative: string;
  bullets: { label: string; href: string }[];
}

const CHAPTERS: Chapter[] = [
  {
    key: 'trigger',
    eyebrow: 'Chapter 01 — The Trigger',
    title: 'Why the cloud has to change',
    icon: Sparkles,
    narrative:
      'Every cross-cloud move starts with pressure: a merger, a data-residency mandate, a cloud credits cliff, or a mandate to consolidate on one provider. The runbook frames the trade-offs so you can defend the decision before a single byte moves.',
    bullets: [
      { label: 'Migration drivers & archetypes', href: '/overview/what-is-cross-cloud-migration' },
      { label: 'Decision framework', href: '/overview/decision-framework' },
    ],
  },
  {
    key: 'assess',
    eyebrow: 'Chapter 02 — The Assessment',
    title: 'Map the estate before you move it',
    icon: Search,
    narrative:
      'You cannot migrate what you cannot see. Inventory workspaces, catalogs, jobs, and notebooks; map the dependency graph; and score risk so the cutover sequence is driven by evidence, not gut feel.',
    bullets: [
      { label: 'Workspace & asset inventory', href: '/discovery/workspace-inventory' },
      { label: 'Dependency mapping', href: '/discovery/dependency-mapping' },
      { label: 'Risk assessment', href: '/discovery/risk-assessment' },
    ],
  },
  {
    key: 'blueprint',
    eyebrow: 'Chapter 03 — The Blueprint',
    title: 'Architect the target landing zone',
    icon: DraftingCompass,
    narrative:
      'Identity, networking, and governance are reset, not copied. Stand up the target cloud landing zone, federate identity, and lay Unity Catalog as the single governance plane before data ever lands.',
    bullets: [
      { label: 'Unity Catalog strategy', href: '/governance/unity-catalog-strategy' },
      { label: 'Identity federation', href: '/security/identity-federation' },
      { label: 'Network security', href: '/security/network-security' },
    ],
  },
  {
    key: 'move',
    eyebrow: 'Chapter 04 — The Move',
    title: 'Migrate data, compute & pipelines',
    icon: ArrowRightLeft,
    narrative:
      'With governance in place, move storage, metastores, clusters, and pipelines in waves. Reusable automation and CI/CD promotion keep every environment reproducible and rollback-ready.',
    bullets: [
      { label: 'Metastore migration', href: '/governance/metastore-migration' },
      { label: 'Cluster migration', href: '/compute/cluster-migration' },
      { label: 'Pipelines & DLT', href: '/pipelines/dlt-lakeflow' },
    ],
  },
  {
    key: 'cutover',
    eyebrow: 'Chapter 05 — The Cutover',
    title: 'Switch traffic, then prove it',
    icon: Flag,
    narrative:
      'Blue-green cutover, data reconciliation, and business UAT sign-off. Hypercare watches the new home until confidence is earned — and a verified rollback path stays one command away throughout.',
    bullets: [
      { label: 'Wave planning & cutover', href: '/execution/cutover' },
      { label: 'Rollback guardrails', href: '/execution/rollback' },
      { label: 'Hypercare', href: '/execution/hypercare' },
    ],
  },
];

export default function MigrationJourney() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ['start start', 'end end'],
  });

  const progressHeight = useTransform(scrollYProgress, [0, 1], ['0%', '100%']);

  const [active, setActive] = useState(0);
  useMotionValueEvent(scrollYProgress, 'change', (v) => {
    setActive(Math.min(CHAPTERS.length - 1, Math.max(0, Math.floor(v * CHAPTERS.length))));
  });

  return (
    <section ref={sectionRef} className="relative my-16" style={{ height: `${CHAPTERS.length * 100}vh` }}>
      <div className="sticky top-0 flex h-screen items-center overflow-hidden">
        <div className="hero-glow" />
        <div className="relative z-10 mx-auto grid w-full max-w-6xl gap-10 px-6 lg:grid-cols-[280px_1fr] lg:px-10">
          {/* Progress rail */}
          <div className="hidden lg:block">
            <p className="mb-6 text-sm font-semibold uppercase tracking-widest text-[var(--ink-subtle)]">
              The Journey
            </p>
            <div className="relative pl-6">
              <div className="absolute left-[7px] top-1 h-[calc(100%-0.5rem)] w-0.5 rounded-full bg-[var(--border)]" />
              <motion.div
                className="absolute left-[7px] top-1 w-0.5 rounded-full bg-[var(--accent)]"
                style={{ height: progressHeight }}
              />
              {CHAPTERS.map((c, i) => (
                <motion.div
                  key={c.key}
                  className="relative mb-7 flex items-center gap-3"
                  initial={false}
                >
                  <span
                    className="absolute -left-6 flex h-3.5 w-3.5 items-center justify-center rounded-full border-2 transition-all duration-300"
                    style={{
                      borderColor:
                        'var(--border)',
                      backgroundColor:
                        i === active ? 'var(--accent)' : 'var(--surface)',
                    }}
                  />
                  <span
                    className="text-sm font-medium transition-colors duration-300"
                    style={{ color: i === active ? 'var(--ink)' : 'var(--ink-subtle)' }}
                  >
                    {c.title}
                  </span>
                </motion.div>
              ))}
            </div>
          </div>

          {/* Narrative stage */}
          <div className="relative min-h-[60vh]">
            {CHAPTERS.map((c, i) => (
              <motion.div
                key={c.key}
                className="absolute inset-0 flex items-center"
                style={{ pointerEvents: i === active ? 'auto' : 'none' }}
                initial={false}
                animate={{
                  opacity: i === active ? 1 : 0,
                  y: i === active ? 0 : 24,
                  scale: i === active ? 1 : 0.98,
                }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
              >
                <div className="w-full">
                  <div className="mb-5 inline-flex items-center gap-3 rounded-full border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-4 py-1.5 text-sm font-medium text-[var(--accent)]">
                    <c.icon className="h-4 w-4" />
                    {c.eyebrow}
                  </div>
                  <h3 className="mb-4 text-3xl font-bold tracking-tight text-[var(--ink)] md:text-4xl">
                    {c.title}
                  </h3>
                  <p className="mb-8 max-w-2xl text-lg leading-relaxed text-[var(--ink-muted)]">
                    {c.narrative}
                  </p>
                  <div className="flex flex-wrap gap-3">
                    {c.bullets.map((b) => (
                      <a
                        key={b.href}
                        href={withBase(b.href)}
                        className="group inline-flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] px-4 py-2.5 text-sm font-medium text-[var(--ink)] transition-colors hover:border-[var(--accent)]/40 hover:bg-[var(--surface-hover)]"
                      >
                        {b.label}
                        <ArrowRight className="h-3.5 w-3.5 text-[var(--ink-subtle)] transition-transform group-hover:translate-x-1 group-hover:text-[var(--accent)]" />
                      </a>
                    ))}
                  </div>
                </div>
              </motion.div>
            ))}

            {/* Scroll hint */}
            <div className="absolute -bottom-2 left-0 flex items-center gap-2 text-xs text-[var(--ink-subtle)]">
              <motion.span
                animate={{ y: [0, 6, 0] }}
                transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
              >
                ↓
              </motion.span>
              Scroll to advance the story
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
