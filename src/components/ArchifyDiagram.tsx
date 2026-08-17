import React, { useEffect, useRef, useState } from 'react';
import { withBase } from '../lib/paths';

/**
 * Embeds one of the generated Archify diagrams from public/diagrams/.
 *
 * The diagrams are self-contained HTML documents with their own theme switch,
 * guided views, route tracing, and export menu -- they are not SVGs we can inline,
 * so they render in an iframe. That isolation is the point: the diagram's own
 * stylesheet and runtime cannot collide with the site's.
 *
 * Two things isolation costs, and this component pays both back:
 *
 * 1. Theme. An iframed document does not inherit the site's `.dark` class, so a
 *    reader in dark mode would otherwise get a bright rectangle mid-page. Archify
 *    reads a `?theme=` query param on load; this component passes the site's
 *    current theme and re-passes it whenever the site toggle flips.
 *
 * 2. Height. Archify's viewer only self-fits to its viewport above 1024px wide;
 *    inside a prose column the frame is narrower than that, so the document lays
 *    out at its own natural height. Rather than hand-tune a pixel guess per
 *    diagram (fragile -- it goes stale the moment the spec changes rows), this
 *    component measures the iframe's own contentDocument.scrollHeight once it has
 *    loaded and sizes the frame to fit exactly, with a small settle-retry for
 *    web-font reflow. Same-origin (both site and diagram are served from
 *    public/diagrams/ on this domain) so contentDocument access is unrestricted.
 *    The `height` prop becomes a display-while-measuring fallback only; pass it
 *    for a nicer first paint, but it is no longer required to be accurate.
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
   * Optional starting height in px, shown only until the real height is measured.
   * Omit it and the frame still ends up correctly sized -- this only avoids an
   * initial resize jump on first paint.
   */
  height?: number;
}

function currentTheme(): 'dark' | 'light' {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light';
}

const MIN_HEIGHT = 480;
// A few settle passes catch late web-font swaps and image decodes that change
// layout after the initial load event fires, without polling indefinitely.
const SETTLE_DELAYS_MS = [50, 250, 700, 1500];

export default function ArchifyDiagram({ name, title, type, caption, height }: Props) {
  const base = withBase(`/diagrams/${name}.html`);
  // Undefined until hydration: server-rendered markup must not guess a theme, or the
  // first paint can disagree with the reader's stored preference.
  const [theme, setTheme] = useState<'dark' | 'light' | undefined>(undefined);
  const [frameHeight, setFrameHeight] = useState<number | undefined>(height);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    setTheme(currentTheme());
    // ThemeToggle flips a class on <html> rather than firing an event, so watch the
    // attribute directly -- this also picks up a toggle from the keyboard shortcut.
    const observer = new MutationObserver(() => setTheme(currentTheme()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  const src = theme ? `${base}?theme=${theme}` : base;

  const measure = () => {
    const doc = iframeRef.current?.contentDocument;
    if (!doc?.documentElement) return;
    const measured = doc.documentElement.scrollHeight;
    if (measured > 0) setFrameHeight(Math.max(MIN_HEIGHT, measured));
  };

  useEffect(() => {
    const timers = SETTLE_DELAYS_MS.map((delay) => window.setTimeout(measure, delay));
    return () => timers.forEach((t) => window.clearTimeout(t));
    // Re-measure whenever the src changes (a theme swap remounts the iframe via `key`).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src]);

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
        ref={iframeRef}
        src={src}
        title={title}
        loading="lazy"
        onLoad={measure}
        className="w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] transition-[height] duration-200"
        style={{ height: `${frameHeight ?? MIN_HEIGHT}px` }}
      />

      {caption && (
        <figcaption className="mt-2 text-sm text-[var(--ink-muted)]">{caption}</figcaption>
      )}
    </figure>
  );
}
