// Verifies every root-relative markdown link (`[text](/some/page)`) in
// src/pages/**/*.mdx actually points at a page that exists.
//
// This runbook is ~90 pages deep in cross-links ("see rollback", "see what
// does not migrate") -- a renamed or deleted page silently breaks every link
// that pointed at it, and nothing catches that until a reader clicks a 404.
// The base-path remark plugin (src/remark-base-path-links.mjs) rewrites these
// at build time but never validates the target exists.
//
//   node scripts/check-internal-links.mjs
//
// Skips: external links (http/https/mailto), anchor-only links (#section on
// the same page), and asset links (anything not ending in a plausible page
// path). Does not validate that a #fragment resolves to a real heading --
// only that the page itself exists.

import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PAGES_DIR = path.join(ROOT, 'src', 'pages');

function walk(dir, out = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (entry.name.endsWith('.mdx') || entry.name.endsWith('.astro')) out.push(full);
  }
  return out;
}

// Pages come from both .mdx (the runbook content) and .astro (the interactive
// tools under /tools/) -- a link target is valid if either extension exists.
const PAGE_EXTENSIONS = ['.mdx', '.astro'];

function pageExists(routePath) {
  // routePath is like "/execution/rollback" -- map to src/pages/execution/rollback.{mdx,astro}
  const rel = routePath.replace(/^\//, '');
  for (const ext of PAGE_EXTENSIONS) {
    if (rel === '') {
      if (statSync(path.join(PAGES_DIR, `index${ext}`), { throwIfNoEntry: false }) != null) return true;
      continue;
    }
    const asFile = path.join(PAGES_DIR, `${rel}${ext}`);
    const asIndex = path.join(PAGES_DIR, rel, `index${ext}`);
    if (
      statSync(asFile, { throwIfNoEntry: false }) != null ||
      statSync(asIndex, { throwIfNoEntry: false }) != null
    ) {
      return true;
    }
  }
  return false;
}

// Matches [text](/path) and [text](/path#anchor); ignores http(s)/mailto and bare "#anchor" links.
const linkRe = /\[[^\]]*\]\((\/[a-zA-Z0-9\-_/]*)(#[^)]*)?\)/g;

let broken = 0;
let checked = 0;

for (const file of walk(PAGES_DIR)) {
  const text = readFileSync(file, 'utf8');
  for (const match of text.matchAll(linkRe)) {
    const routePath = match[1];
    checked += 1;
    if (!pageExists(routePath)) {
      const rel = path.relative(ROOT, file);
      console.error(`broken link in ${rel}: ${match[0]} -- no page at ${routePath}`);
      broken += 1;
    }
  }
}

if (broken > 0) {
  console.error(`\n${broken} broken internal link(s) of ${checked} checked`);
  process.exit(1);
}

console.log(`${checked} internal links checked -- all resolve to an existing page`);
