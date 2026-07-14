# Databricks Cross-Cloud Migration Runbook

A production-grade, enterprise-focused documentation website and migration runbook for moving Databricks across Azure, AWS, and GCP.

## What is included

- **Static docs website** built with [Astro](https://astro.build), React, and Tailwind CSS.
- **Premium UX** with dark/light mode, search, progress indicator, animated cards, code copy buttons, and table of contents.
- **Full runbook content** covering discovery, cloud mappings, governance, security, compute, pipelines, execution, validation, templates, and troubleshooting.
- **Sample pages** (28+ pages) with decision tables, checklists, code snippets, Mermaid-ready diagrams, and callouts.
- **Reusable components**: cards, callouts, code blocks, checklists, tabs, accordions, theme toggle, search, sidebar, and TOC.

## Tech stack

- Astro 4.x
- React 18
- Tailwind CSS 3.4
- TypeScript
- Lucide React icons

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
│   ├── data/
│   │   └── navigation.json  # Sidebar and search index
│   ├── layouts/
│   │   └── Layout.astro     # Docs shell
│   ├── pages/
│   │   ├── index.astro      # Landing page
│   │   ├── [...slug].astro  # Placeholder for pages not yet written
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

1. Create a new `.mdx` file under `src/pages/<section>/<page>.mdx`.
2. Import the layout and components:

```mdx
---
title: 'Page title'
description: 'Page description'
---

import Layout from '../../layouts/Layout.astro';
import Callout from '../../components/Callout.tsx';

export default function ({ children }) {
  return <Layout title={frontmatter.title} description={frontmatter.description} currentSlug="section/page">{children}</Layout>;
}

# Page title
```

3. Add the page to `src/data/navigation.json`.
4. If you want the new page to render instead of the placeholder, remove or rename the `[...slug].astro` dynamic route or ensure your static file path matches the navigation slug.

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

## Optional enhancements

- **Local search**: Replace the simple navigation search with a full-text index built from page content (e.g., using `pagefind` or a custom Astro integration).
- **Versioning**: Add a version selector for runbook releases.
- **Print/export**: Add a print stylesheet and PDF export for the full runbook.
- **Diagram zoom**: Integrate Mermaid or SVG diagrams with pan/zoom controls.
- **Downloadable bundles**: Package Markdown content and templates as a downloadable zip.

## License

This is a reference implementation. Validate all commands and Terraform configurations against your environment and official Databricks documentation before production use.
