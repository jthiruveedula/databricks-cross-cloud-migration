import React, { useEffect, useState } from 'react';
import { withBase } from '../lib/paths';

/**
 * Embeds one of the generated Archify diagrams from public/diagrams/.
 *
 * The diagrams are self-contained HTML documents with their own theme switch,
 * guided views, route tracing, and export menu -- they are not SVGs we can inline,
 * so they render in an iframe. That isolation is the point: the diagram's own
 * stylesheet and runtime cannot collide with the site's.
 *
 * The one thing isolation costs us is the theme. An iframed document does not
 * inherit the site's `.dark` class, so a reader in dark mode would otherwise get a
 * white rectangle in the middle of a dark page. Archify reads a `?theme=` query
 * param on load, so we pass the site's current theme and re-pass it whenever the
 * site toggle flips. Hydrate with `client:visible` for that sync to run; without a
 * client directive the frame still renders, it just keeps Archify's own default.
 *
 * Regenerate the embedded HTML with `npm run build:diagrams` after editing a spec
 * in diagrams/ -- never hand-edit the file under public/diagrams/.
 */

interface Props {
  /** File name under public/diagrams/, without the .html extension. */
  name: string;
  /** Shown above the frame; should say what the diagram answers, not just name it. */
  title: string;
  /** Archify diagram type, shown as a chip so readers know what kind of view this is. */
  type: 'architecture' | 'dataflow' | 'workflow' | 'sequence' | 'lifecycle';
  /** One sentence under the frame explaining what to look for. */
  caption?: string;
  /**
   * Frame height in px. Archify's viewer only auto-fits a diagram to its viewport
   * above 1024px wide; inside a prose column the frame is narrower than that, so the
   * document lays out at its natural height and the frame must be tall enough to hold
   * it or the reader gets a scrollbar inside a scrollbar. 1060px clears every diagram
   * in this repo at prose width (the tallest, the sequence, needs 1038px). A page that gives the frame >= 1024px (e.g. one with
   * `hideToc`) can pass something shorter and let the viewer do the fitting.
   */
  height?: number;
}

function currentTheme(): 'dark' | 'light' {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light';
}

export default function ArchifyDiagram({ name, title, type, caption, height = 1060 }: Props) {
  const base = withBase(`/diagrams/${name}.html`);
  // Undefined until hydration: server-rendered markup must not guess a theme, or the
  // first paint can disagree with the reader's stored preference.
  const [theme, setTheme] = useState<'dark' | 'light' | undefined>(undefined);

  useEffect(() => {
    setTheme(currentTheme());
    // ThemeToggle flips a class on <html> rather than firing an event, so watch the
    // attribute directly -- this also picks up a toggle from the keyboard shortcut.
    const observer = new MutationObserver(() => setTheme(currentTheme()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  const src = theme ? `${base}?theme=${theme}` : base;

  return (
    <figure className="my-8">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="rounded border border-[var(--border)] px-1.5 py-0.5 text-[0.65rem] font-medium uppercase tracking-wider text-[var(--ink-muted)]">
            {type}
          </span>
          <span className="text-sm font-medium text-[var(--ink)]">{title}</span>
        </div>
        <a
          href={src}
          target="_blank"
          rel="noopener"
          className="text-sm text-[var(--accent)] underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
        >
          Open full view ↗
        </a>
      </div>

      <iframe
        key={src}
        src={src}
        title={title}
        loading="lazy"
        className="w-full rounded-xl border border-[var(--border)] bg-[var(--surface)]"
        style={{ height: `${height}px` }}
      />

      {caption && (
        <figcaption className="mt-2 text-sm text-[var(--ink-muted)]">{caption}</figcaption>
      )}
    </figure>
  );
}
