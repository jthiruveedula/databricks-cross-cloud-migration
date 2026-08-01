import React from 'react';
import { XCircle, CheckCircle2, Database, ShieldAlert, Link2, KeyRound, SkipForward, GitCompareArrows, ArrowRight } from 'lucide-react';
import { withBase } from '../lib/paths';

interface AntiPattern {
  icon: React.ElementType;
  title: string;
  mistake: string;
  instead: string;
  insteadHref?: string;
  insteadLinkLabel?: string;
}

// Same content as the prose version this replaces -- six stacked `##` sections read as a
// wall of text with no visual grouping, despite the site already having a red/green
// mistake-vs-fix visual language (ApplicabilityCompare) that fits this content directly.
const ANTI_PATTERNS: AntiPattern[] = [
  {
    icon: Database,
    title: 'Lifting legacy Hive metastore',
    mistake: 'Re-creating a legacy Hive metastore in the target wastes the migration opportunity. It perpetuates workspace-local governance, DBFS dependencies, and unsupported access modes.',
    instead: 'Adopt Unity Catalog as part of the migration.',
  },
  {
    icon: ShieldAlert,
    title: 'Copying data without validation',
    mistake: 'Moving petabytes without reconciliation is a gamble. Hidden schema drift, partition differences, or permission gaps only surface after cutover.',
    instead: 'Reconcile row counts, checksums, partitions, and permissions for every table.',
  },
  {
    icon: Link2,
    title: 'Hardcoding paths in notebooks',
    mistake: 'dbfs:/mnt/... or cloud-specific paths embedded in notebooks require manual fixes and are easy to miss.',
    instead: 'Use configuration tables, environment variables, or volume references.',
  },
  {
    icon: KeyRound,
    title: 'Migrating with personal access tokens',
    mistake: 'PATs tied to users do not survive identity changes and are difficult to rotate.',
    instead: 'Use OAuth service principals and managed identities for automation.',
    insteadHref: '/troubleshooting/known-limitations',
    insteadLinkLabel: 'PATs are unsupported for export/import',
  },
  {
    icon: SkipForward,
    title: 'Skipping the pilot',
    mistake: 'Jumping straight to production migration leaves tooling and process gaps undiscovered until it is too late.',
    instead: 'Run a pilot wave, validate the full runbook, and iterate.',
  },
  {
    icon: GitCompareArrows,
    title: 'Partial cutover without dual-run',
    mistake: 'Moving some users to target while others remain on source creates split-brain and reconciliation nightmares.',
    instead: 'Use a clear freeze window or blue-green cutover with a single system of record.',
  },
];

export default function AntiPatternGrid() {
  return (
    <div className="my-6 grid gap-4 sm:grid-cols-2">
      {ANTI_PATTERNS.map((p) => (
        <div key={p.title} className="rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] p-4">
          <div className="mb-3 flex items-center gap-2.5">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--danger)]/10 text-[var(--danger)]">
              <p.icon className="h-4 w-4" />
            </span>
            <h4 className="font-semibold text-[var(--ink)]">{p.title}</h4>
          </div>
          <p className="mb-3 flex gap-2 text-sm text-[var(--ink-muted)]">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--danger)]" />
            <span>{p.mistake}</span>
          </p>
          <p className="flex gap-2 text-sm text-[var(--ink-muted)]">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[var(--success)]" />
            <span>
              <strong className="text-[var(--ink)]">Instead:</strong> {p.instead}
              {p.insteadHref && (
                <>
                  {' '}
                  <a
                    href={withBase(p.insteadHref)}
                    className="inline-flex items-center gap-0.5 font-medium text-[var(--accent)] hover:underline"
                  >
                    {p.insteadLinkLabel}
                    <ArrowRight className="h-3 w-3" />
                  </a>
                </>
              )}
            </span>
          </p>
        </div>
      ))}
    </div>
  );
}
