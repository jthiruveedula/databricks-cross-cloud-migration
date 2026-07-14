import React, { useEffect, useState } from 'react';

interface Heading {
  id: string;
  text: string;
  level: number;
}

export default function TableOfContents() {
  const [headings, setHeadings] = useState<Heading[]>([]);
  const [active, setActive] = useState('');

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
        <ul className="space-y-1 border-l border-[var(--border)]">
          {headings.map((h) => (
            <li key={h.id}>
              <a
                href={`#${h.id}`}
                className={`
                  block border-l-2 py-1 pl-3 text-sm transition-colors
                  ${active === h.id ? 'border-[var(--accent)] text-[var(--accent)]' : 'border-transparent text-[var(--ink-muted)] hover:text-[var(--ink)]'}
                  ${h.level === 3 ? 'ml-3 text-xs' : ''}
                `}
              >
                {h.text}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}
