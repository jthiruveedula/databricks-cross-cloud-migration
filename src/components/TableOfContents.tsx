import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';

interface Heading {
  id: string;
  text: string;
  level: number;
}

export default function TableOfContents() {
  const [headings, setHeadings] = useState<Heading[]>([]);
  const [active, setActive] = useState('');
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    const main = document.querySelector('main');
    if (!main) return;
    const elements = Array.from(main.querySelectorAll('h2, h3'));
    setHeadings(
      elements.map((el) => ({
        id: el.id,
        text: el.textContent ?? '',
        level: parseInt(el.tagName[1]),
      }))
    );

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: '-80px 0px -60% 0px', threshold: 0 }
    );

    elements.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  if (headings.length === 0) return null;

  return (
    <nav className="hidden xl:block w-[var(--toc-width)] pl-8">
      <div className="fixed top-[calc(var(--header-height)+2rem)] w-[var(--toc-width)]">
        <h5 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--ink-subtle)]">On this page</h5>
        <ul ref={listRef} className="relative space-y-1">
          {headings.map((h) => (
            <li key={h.id}>
              <a
                href={`#${h.id}`}
                onClick={(e) => {
                  e.preventDefault();
                  document.getElementById(h.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }}
                className={`
                  relative block rounded-r-md py-1 pl-3 text-sm transition-colors duration-150
                  ${active === h.id ? 'text-[var(--accent)] font-medium' : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'}
                  ${h.level === 3 ? 'ml-3 text-xs' : ''}
                `}
              >
                {active === h.id && (
                  <motion.span
                    layoutId="toc-active-pill"
                    className="absolute inset-0 rounded-r-md border-l-2 border-[var(--accent)] bg-[var(--accent-soft)]"
                    transition={{ type: 'spring', stiffness: 350, damping: 30 }}
                  />
                )}
                <span className="relative z-10">{h.text}</span>
              </a>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}
