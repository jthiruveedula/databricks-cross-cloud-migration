// Renders every Archify spec in diagrams/ into a self-contained HTML file under
// public/diagrams/, which the site serves as a static asset and embeds via
// src/components/ArchifyDiagram.tsx.
//
// The generated HTML is COMMITTED on purpose: Archify is an agent skill installed
// outside this repo, so CI and the Pages deploy must never depend on it being present.
// Run this locally after editing a spec, then commit both the spec and its HTML.
//
//   node scripts/build-diagrams.mjs            # render all specs
//   node scripts/build-diagrams.mjs --validate # check specs without writing HTML
//
// ARCHIFY_HOME overrides the skill location (default: ~/.claude/skills/archify).

import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { homedir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SPEC_DIR = path.join(ROOT, 'diagrams');
const OUT_DIR = path.join(ROOT, 'public', 'diagrams');

const ARCHIFY_HOME = process.env.ARCHIFY_HOME || path.join(homedir(), '.claude', 'skills', 'archify');
const ARCHIFY_BIN = path.join(ARCHIFY_HOME, 'bin', 'archify.mjs');

// Diagram type is not derivable from the file name alone -- keep the mapping explicit
// so a renamed spec fails loudly here instead of being rendered as the wrong type.
const SPECS = [
  { type: 'architecture', name: 'estate-migration.architecture' },
  { type: 'dataflow', name: 'table-migration.dataflow' },
  { type: 'workflow', name: 'cutover-runbook.workflow' },
  { type: 'sequence', name: 'event-bridge.sequence' },
  { type: 'lifecycle', name: 'table-state.lifecycle' },
];

const validateOnly = process.argv.includes('--validate');

if (!existsSync(ARCHIFY_BIN)) {
  console.error(`archify not found at ${ARCHIFY_BIN}`);
  console.error('install it with: npx skills add tt-a1i/archify -g');
  console.error('or point ARCHIFY_HOME at an existing checkout');
  process.exit(1);
}

let failed = 0;

for (const { type, name } of SPECS) {
  const spec = path.join(SPEC_DIR, `${name}.json`);
  const out = path.join(OUT_DIR, `${name}.html`);

  if (!existsSync(spec)) {
    console.error(`missing spec: ${path.relative(ROOT, spec)}`);
    failed += 1;
    continue;
  }

  const args = validateOnly
    ? ['validate', type, spec, '--quality', 'showcase']
    : ['deliver', type, spec, out, '--quality', 'showcase'];

  console.log(`${validateOnly ? 'validate' : 'deliver '} ${type.padEnd(12)} ${name}`);
  const result = spawnSync(process.execPath, [ARCHIFY_BIN, ...args], { stdio: 'inherit' });

  // A non-zero exit means the spec failed showcase validation or the render was rejected.
  // Never treat that as a success -- the committed HTML would silently go stale.
  if (result.status !== 0) failed += 1;
}

if (failed > 0) {
  console.error(`\n${failed} diagram(s) failed`);
  process.exit(1);
}

console.log(`\n${SPECS.length} diagram(s) ${validateOnly ? 'validated' : 'delivered'}`);
