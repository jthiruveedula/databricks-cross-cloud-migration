import nav from '../data/navigation.json';
import { withBase } from '../lib/paths';

interface NavItem {
  title: string;
  slug: string;
}

const flat: NavItem[] = (nav as { sections: { items: NavItem[] }[] }).sections.flatMap(
  (section) => section.items
);

export interface PrevNextProps {
  currentSlug: string;
}

export default function PrevNext({ currentSlug }: PrevNextProps) {
  const index = flat.findIndex((item) => item.slug === currentSlug);
  if (index === -1) return null;

  const prev = index > 0 ? flat[index - 1] : null;
  const next = index < flat.length - 1 ? flat[index + 1] : null;
  if (!prev && !next) return null;

  return (
    <nav class="prev-next" aria-label="Pagination">
      {prev ? (
        <a class="prev-next__link prev-next__link--prev" href={withBase(`/${prev.slug}/`)}>
          <span class="prev-next__label">Previous</span>
          <span class="prev-next__title">{prev.title}</span>
        </a>
      ) : (
        <span class="prev-next__link prev-next__link--empty" aria-hidden="true" />
      )}
      {next ? (
        <a class="prev-next__link prev-next__link--next" href={withBase(`/${next.slug}/`)}>
          <span class="prev-next__label">Next</span>
          <span class="prev-next__title">{next.title}</span>
        </a>
      ) : (
        <span class="prev-next__link prev-next__link--empty" aria-hidden="true" />
      )}
    </nav>
  );
}
