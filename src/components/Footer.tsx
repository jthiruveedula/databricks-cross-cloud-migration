import React from 'react';
import { withBase } from '../lib/paths';

export default function Footer() {
  return (
    <footer className="border-t border-[var(--border)] bg-[var(--surface-elevated)] px-6 py-10 text-sm text-[var(--ink-muted)]">
      <div className="mx-auto flex max-w-6xl flex-col justify-between gap-6 md:flex-row">
        <div>
          <p className="font-semibold text-[var(--ink)]">Databricks Cross-Cloud Migration Runbook</p>
          <p className="mt-1">Enterprise-grade guidance for Azure, AWS, and GCP migrations.</p>
        </div>
        <div className="flex gap-6">
          <a href={withBase('/overview/what-is-cross-cloud-migration')} className="hover:text-[var(--accent)]">Overview</a>
          <a href={withBase('/execution/wave-planning')} className="hover:text-[var(--accent)]">Execution</a>
          <a href={withBase('/templates/checklists')} className="hover:text-[var(--accent)]">Templates</a>
          <a href={withBase('/troubleshooting/faq')} className="hover:text-[var(--accent)]">FAQ</a>
        </div>
      </div>
      <div className="mx-auto mt-8 max-w-6xl text-xs text-[var(--ink-subtle)]">
        © {new Date().getFullYear()} Databricks Cross-Cloud Migration Runbook. This is a reference implementation; validate all commands against your environment and Databricks documentation before production use.
      </div>
    </footer>
  );
}
