import React, { forwardRef } from 'react';
import { ArrowRight } from 'lucide-react';

interface Props {
  href?: string;
  title: string;
  description: string;
  icon?: React.ElementType;
  className?: string;
}

// forwardRef so callers that need to animate this exact element (e.g. SectionGrid's
// `motion(Card)`) can attach directly to it -- animating a wrapper div around a plain
// Card left CSS Grid measuring the wrapper's auto-row height against the wrapper's own
// box, which disagreed with the Card's actual content height once the two diverged
// (grid stretch shrinks a box below its content's natural size unless something else
// constrains it -- the wrapper had nothing to constrain it to besides the row track).
const Card = forwardRef<HTMLAnchorElement | HTMLDivElement, Props>(function Card(
  { href, title, description, icon, className = '' },
  ref,
) {
  const Wrapper = href ? 'a' : 'div';
  return (
    <Wrapper
      ref={ref as never}
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
});

export default Card;
