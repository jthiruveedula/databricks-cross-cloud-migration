# Databricks Cross-Cloud Migration Runbook

**Live site: https://jthiruveedula.github.io/databricks-cross-cloud-migration/**

A production-grade, enterprise-focused documentation website and migration runbook for moving Databricks across Azure, AWS, and GCP — discovery, Unity Catalog and metastore strategy, IAM and network security, compute and pipeline migration, wave planning through cutover and hypercare, and validation, backed by an interactive Migration Planner that generates a tailored runbook path for any source/target cloud pair.

## What is included

- **Static docs website** built with [Astro](https://astro.build), React, and Tailwind CSS, deployed to GitHub Pages via GitHub Actions on every push to `main`.
- **Interactive Migration Planner** (`src/components/MigrationPlanner.tsx`) — pick a source/target cloud and get a tailored migration strategy, recommended runbook path, and toolset.
- **Premium UX** with dark/light mode, search (⌘K), scroll progress indicator, animated cards, code copy buttons, table of contents, and real brand logos (Databricks, Terraform, GitHub, MLflow, Apache Spark, Kubernetes, Google Cloud via `simple-icons`; AWS/Azure as brand-color wordmark badges since those marks aren't redistributable).
- **Full runbook content** (40+ pages and growing) covering discovery, all 6 directional cloud mappings, governance, security, compute, pipelines, execution (pilot → bulk migration → cutover → hypercare → rollback), validation, templates, and troubleshooting. Nav entries without a dedicated page yet fall through to a placeholder route — see [Writing new pages](#writing-new-pages).
- **Reusable components**: cards, callouts, code blocks, checklists, tabs, accordions, theme toggle, search, sidebar, and TOC.

## Tech stack

- Astro 4.x
- React 18
- Tailwind CSS 3.4
- TypeScript
- Framer Motion
- Lucide React icons + `simple-icons` for brand marks

## Project structure

```
├── astro.config.mjs
├── tailwind.config.mjs
├── tsconfig.json
├── package.json
├── public/
│   └── favicon.svg
├── src/
│   ├── components/          # React UI components
│   │   └── logos/           # Brand SVG glyphs (simple-icons data) + BrandGlyph renderer
│   ├── data/
│   │   └── navigation.json  # Sidebar and search index
│   ├── lib/
│   │   └── paths.ts         # withBase() helper for GitHub Pages base-path-aware links
│   ├── layouts/
│   │   └── Layout.astro     # Docs shell (AppShell header+sidebar, TOC, footer)
│   ├── pages/
│   │   ├── index.astro      # Landing page + Migration Planner
│   │   ├── [...slug].astro  # Placeholder for nav items without a dedicated page yet
│   │   ├── overview/
│   │   ├── discovery/
│   │   ├── cloud-mappings/
│   │   ├── governance/
│   │   ├── security/
│   │   ├── compute/
│   │   ├── pipelines/
│   │   ├── analytics/
│   │   ├── ml/
│   │   ├── execution/
│   │   ├── validation/
│   │   ├── templates/
│   │   └── troubleshooting/
│   └── styles/
│       └── global.css       # Design tokens and typography
```

## Getting started

### Prerequisites

- Node.js 18 or later
- npm, yarn, or pnpm

### Install dependencies

```bash
npm install
```

### Run the development server

```bash
npm run dev
```

Open http://localhost:4321 to view the site.

### Build for production

```bash
npm run build
```

Static output is written to `dist/`.

### Preview the production build

```bash
npm run preview
```

## Writing new pages

1. Create a new `.mdx` file under `src/pages/<section>/<page>.mdx`, matching a slug already listed in `src/data/navigation.json` (add it there first if it isn't).
2. Use the `layout` frontmatter field — Astro applies it automatically, no manual wrapper needed:

```mdx
---
title: 'Page title'
layout: ../../layouts/Layout.astro
description: 'Page description'
---

import Callout from '../../components/Callout.tsx';
import CodeBlock from '../../components/CodeBlock.tsx';
import Checklist from '../../components/Checklist.tsx';

# Page title

Body content, using Callout/CodeBlock/Checklist/Tabs/Accordion as needed. Follow the
existing pages' shape: intro, a comparison/decision table where relevant, a code
sample, then **Validation**, **Rollback**, and **Automation opportunity** sections
closing with a `<Checklist>`.
```

3. That's it — `[...slug].astro`'s `getStaticPaths` automatically excludes any nav slug that has a matching `.mdx` file (via `import.meta.glob`), so your new page supersedes the placeholder with no extra routing changes.

## Design system

Design tokens are CSS custom properties in `src/styles/global.css`. Key tokens include:

- `--surface`, `--surface-elevated`, `--surface-hover`
- `--ink`, `--ink-muted`, `--ink-subtle`
- `--border`, `--accent`, `--accent-soft`, `--glow-color`

Components use these tokens so the site supports both light and dark modes.

## SEO and meta

Suggested site title: **Databricks Cross-Cloud Migration Runbook**

Suggested meta description:

> Enterprise runbook for migrating Databricks across Azure, AWS, and GCP. Covers Unity Catalog, metastores, IAM, data movement, cutover, validation, and rollback.

Suggested keywords: `Databricks migration`, `cross-cloud migration`, `Unity Catalog`, `Azure Databricks`, `AWS Databricks`, `GCP Databricks`, `data migration`, `cloud migration runbook`.

## Deployment

The site deploys to **GitHub Pages** automatically on every push to `main` via `.github/workflows/deploy.yml` (build with `npm run build`, then `actions/deploy-pages`). Pages is configured with build source `workflow` — no manual `gh-pages` branch step required.

Because GitHub Pages serves a project repo under `/<repo-name>/` rather than the domain root, `astro.config.mjs` sets `site`/`base` accordingly, and every internal link goes through the `withBase()` helper in `src/lib/paths.ts` instead of a hardcoded root-relative path. If you fork this repo under a different name, update `base` in `astro.config.mjs` to match — the rest of the app picks it up automatically.

## Optional enhancements

- **Local search**: Replace the simple navigation search with a full-text index built from page content (e.g., using `pagefind` or a custom Astro integration).
- **Versioning**: Add a version selector for runbook releases.
- **Print/export**: Add a print stylesheet and PDF export for the full runbook.
- **Diagram zoom**: Integrate Mermaid or SVG diagrams with pan/zoom controls.
- **Downloadable bundles**: Package Markdown content and templates as a downloadable zip.

## License

This is a reference implementation. Validate all commands and Terraform configurations against your environment and official Databricks documentation before production use.
