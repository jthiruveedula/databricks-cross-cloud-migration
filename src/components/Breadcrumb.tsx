import React from 'react';
import { ChevronRight, Home } from 'lucide-react';
import nav from '../data/navigation.json';
import { withBase } from '../lib/paths';

interface Props {
  currentSlug: string;
}

export default function Breadcrumb({ currentSlug }: Props) {
  if (!currentSlug || currentSlug === 'index' || currentSlug === '') return null;

  const parts = currentSlug.split('/');
  const sectionSlug = parts[0];

  const section = nav.sections.find((s) => s.slug === sectionSlug);
  const item = section?.items.find((i) => i.slug === currentSlug);

  const crumbs: { label: string; href?: string }[] = [{ label: 'Home', href: withBase('/') }];

  if (section) {
    crumbs.push({ label: section.title, href: withBase(`/${section.items[0].slug}`) });
  }
  if (item) {
    crumbs.push({ label: item.title });
  }

  return (
    <nav aria-label="Breadcrumb" className="mb-4 flex items-center gap-1.5 text-sm text-[var(--ink-muted)]">
      {crumbs.map((c, i) => (
        <React.Fragment key={i}>
          {i > 0 && <ChevronRight className="h-3.5 w-3.5 text-[var(--ink-subtle)]" />}
          {c.href ? (
            <a
              href={c.href}
              className="flex items-center gap-1 rounded px-1.5 py-0.5 transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--accent)]"
            >
              {i === 0 && <Home className="h-3.5 w-3.5" />}
              {c.label}
            </a>
          ) : (
            <span className="rounded px-1.5 py-0.5 text-[var(--ink)]">{c.label}</span>
          )}
        </React.Fragment>
      ))}
    </nav>
  );
}
