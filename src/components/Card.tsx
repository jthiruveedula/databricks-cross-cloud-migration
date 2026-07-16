import React from 'react';
import { ArrowRight } from 'lucide-react';

interface Props {
  href?: string;
  title: string;
  description: string;
  icon?: React.ElementType;
  className?: string;
}

export default function Card({ href, title, description, icon, className = '' }: Props) {
  const Wrapper = href ? 'a' : 'div';
  return (
    <Wrapper
      href={href}
      className={`
        group relative overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] p-6
        shadow-card transition-all duration-300 hover:-translate-y-1 hover:shadow-card-hover hover:border-[var(--accent)]/30
        active:scale-[0.98] active:shadow-none
        ${href ? 'cursor-pointer' : ''} ${className}
      `}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-[var(--accent)]/5 via-transparent to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100" />
      <div className="relative">
        {icon && (
          <div className="mb-4 inline-flex rounded-lg bg-[var(--accent-soft)] p-3 text-[var(--accent)]">
            {React.isValidElement(icon) ? icon : React.createElement(icon as React.ElementType, { className: 'h-6 w-6' })}
          </div>
        )}
        <h3 className="mb-2 flex items-center gap-2 text-lg font-semibold text-[var(--ink)]">
          {title}
          {href && <ArrowRight className="h-4 w-4 opacity-0 transition-all group-hover:translate-x-1 group-hover:scale-110 group-hover:opacity-100" />}
        </h3>
        <p className="text-sm text-[var(--ink-muted)]">{description}</p>
      </div>
    </Wrapper>
  );
}
