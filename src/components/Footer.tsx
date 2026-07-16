import React from 'react';
import { motion } from 'framer-motion';
import { withBase } from '../lib/paths';

export default function Footer() {
  return (
    <motion.footer
      initial={{ opacity: 0 }}
      whileInView={{ opacity: 1 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ duration: 0.4 }}
      className="border-t border-[var(--border)] bg-[var(--surface-elevated)] px-6 py-10 text-sm text-[var(--ink-muted)]"
    >
      <div className="mx-auto flex max-w-6xl flex-col justify-between gap-6 md:flex-row">
        <div>
          <p className="font-semibold text-[var(--ink)]">Databricks Cross-Cloud Migration Runbook</p>
          <p className="mt-1">Enterprise-grade guidance for Azure, AWS, and GCP migrations.</p>
        </div>
        <div className="flex gap-6">
          {[
            { href: '/overview/what-is-cross-cloud-migration', label: 'Overview' },
            { href: '/tools', label: 'Tools' },
            { href: '/execution/wave-planning', label: 'Execution' },
            { href: '/troubleshooting/faq', label: 'FAQ' },
          ].map((link) => (
            <a
              key={link.href}
              href={withBase(link.href)}
              className="relative transition-colors hover:text-[var(--accent)] after:absolute after:bottom-0 after:left-0 after:h-px after:w-0 after:bg-[var(--accent)] after:transition-all hover:after:w-full"
            >
              {link.label}
            </a>
          ))}
        </div>
      </div>
      <div className="mx-auto mt-8 max-w-6xl text-xs text-[var(--ink-subtle)]">
        © {new Date().getFullYear()} Databricks Cross-Cloud Migration Runbook. This is a reference implementation; validate all commands against your environment and Databricks documentation before production use.
      </div>
    </motion.footer>
  );
}
