// Consistency check across the three places a diagram has to agree:
//
//   diagrams/<name>.json        the spec (source of truth for type + name)
//   public/diagrams/<name>.html the rendered artifact (scripts/build-diagrams.mjs)
//   src/pages/**/*.mdx          the <ArchifyDiagram name="..."> embed that shows it
//
// Catches three regressions that are otherwise silent until a reader hits a
// broken iframe or a page ships a diagram no one can find:
//
//   1. A spec exists but isn't in scripts/build-diagrams.mjs's SPECS list
//      (or its render is stale/missing) -- ORPHAN SPEC
//   2. A page embeds a name with no rendered HTML on disk -- MISSING RENDER
//   3. A rendered HTML file has no page embedding it -- UNEMBEDDED RENDER
//      (dead weight shipped to production, or a page's embed was removed
//      without cleaning up the render)
//
//   node scripts/check-diagram-wiring.mjs

import { existsSync, readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SPEC_DIR = path.join(ROOT, 'diagrams');
const RENDER_DIR = path.join(ROOT, 'public', 'diagrams');
const PAGES_DIR = path.join(ROOT, 'src', 'pages');

function walk(dir, out = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (entry.name.endsWith('.mdx')) out.push(full);
  }
  return out;
}

const specNames = readdirSync(SPEC_DIR)
  .filter((f) => f.endsWith('.json'))
  .map((f) => f.replace(/\.json$/, ''));

const renderNames = readdirSync(RENDER_DIR)
  .filter((f) => f.endsWith('.html'))
  .map((f) => f.replace(/\.html$/, ''));

const embedNameRe = /<ArchifyDiagram\b[^>]*\bname=["']([^"']+)["']/g;
const embeddedNames = new Set();
for (const page of walk(PAGES_DIR)) {
  const text = readFileSync(page, 'utf8');
  for (const match of text.matchAll(embedNameRe)) embeddedNames.add(match[1]);
}

let failed = 0;

for (const name of specNames) {
  if (!renderNames.includes(name)) {
    console.error(`missing render: diagrams/${name}.json has no public/diagrams/${name}.html -- run npm run build:diagrams`);
    failed += 1;
  }
}

for (const name of embeddedNames) {
  if (!renderNames.includes(name)) {
    console.error(`broken embed: a page references name="${name}" but public/diagrams/${name}.html doesn't exist`);
    failed += 1;
  }
  if (!specNames.includes(name)) {
    console.error(`embed with no spec: a page references name="${name}" but diagrams/${name}.json doesn't exist`);
    failed += 1;
  }
}

for (const name of renderNames) {
  if (!embeddedNames.has(name)) {
    console.error(`unembedded render: public/diagrams/${name}.html exists but no page embeds it -- dead weight or a removed embed`);
    failed += 1;
  }
}

if (failed > 0) {
  console.error(`\n${failed} diagram-wiring issue(s) found`);
  process.exit(1);
}

console.log(`${specNames.length} specs, ${renderNames.length} renders, ${embeddedNames.size} embeds -- all wired consistently`);
