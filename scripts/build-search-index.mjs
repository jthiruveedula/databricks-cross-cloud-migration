#!/usr/bin/env node
// Generates src/data/search-index.json from every src/pages/**/*.mdx file -- one entry per
// H1/H2/H3 section (title + heading + plain-text excerpt), not just the page title. The
// search box previously only matched page titles from navigation.json, so a real term that
// only appears in body text (e.g. "delta", "metastore", "PrivateLink") returned nothing even
// though dozens of pages mention it. Run via `npm run build` / `npm run dev` (wired as a
// pre-step) so the index never goes stale relative to the docs content.
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const PAGES_DIR = join(ROOT, 'src/pages');
const OUT_FILE = join(ROOT, 'src/data/search-index.json');
const NAV_FILE = join(ROOT, 'src/data/navigation.json');

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) out.push(...walk(full));
    else if (entry.endsWith('.mdx')) out.push(full);
  }
  return out;
}

// Same slug algorithm Astro's built-in markdown heading-id generator uses (lowercase,
// non-alphanumeric -> hyphen, collapse/trim hyphens) -- close enough to link search results
// directly to `#heading-id` on the target page.
function slugify(text) {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function stripMarkdown(text) {
  return text
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/<[^>]+>/g, ' ')
    .replace(/[|#>-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function extractFrontmatterTitle(raw) {
  const match = raw.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return null;
  const titleLine = match[1].split('\n').find((l) => l.trim().startsWith('title:'));
  if (!titleLine) return null;
  return titleLine.split(':').slice(1).join(':').trim().replace(/^['"]|['"]$/g, '');
}

function buildSectionMap(nav) {
  const map = new Map();
  for (const section of nav.sections) {
    for (const item of section.items) map.set(item.slug, section.title);
  }
  return map;
}

const nav = JSON.parse(readFileSync(NAV_FILE, 'utf8'));
const sectionBySlug = buildSectionMap(nav);

const files = walk(PAGES_DIR);
const entries = [];
let id = 0;

for (const file of files) {
  const raw = readFileSync(file, 'utf8');
  const slug = relative(PAGES_DIR, file).replace(/\.mdx$/, '');
  const pageTitle = extractFrontmatterTitle(raw) || slug;
  const section = sectionBySlug.get(slug) || '';

  // Drop frontmatter + import lines, then split on heading lines so each section becomes
  // its own indexed, individually-linkable entry.
  const body = raw.replace(/^---\n[\s\S]*?\n---/, '').replace(/^import .+$/gm, '');
  const lines = body.split('\n');

  let currentHeading = null;
  let currentSlug = null;
  let buffer = [];

  const flush = () => {
    const text = stripMarkdown(buffer.join(' ')).slice(0, 500);
    if (text.length > 20) {
      entries.push({
        id: id++,
        slug,
        pageTitle,
        section,
        heading: currentHeading,
        headingSlug: currentSlug,
        text,
      });
    }
    buffer = [];
  };

  for (const line of lines) {
    const headingMatch = line.match(/^(#{1,3})\s+(.+)$/);
    if (headingMatch) {
      flush();
      if (headingMatch[1] === '#') {
        // H1 restates the page title -- skip as its own heading, but keep indexing
        // the prose that follows it under the page's top-level entry (currentHeading null).
        currentHeading = null;
        currentSlug = null;
      } else {
        currentHeading = headingMatch[2].trim();
        currentSlug = slugify(currentHeading);
      }
      continue;
    }
    buffer.push(line);
  }
  flush();
}

writeFileSync(OUT_FILE, JSON.stringify(entries));
console.log(`search-index: ${entries.length} entries from ${files.length} pages -> ${relative(ROOT, OUT_FILE)}`);
