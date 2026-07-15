# Databricks Cross-Cloud Migration Runbook

**Live site: https://jthiruveedula.github.io/databricks-cross-cloud-migration/**

An enterprise runbook for migrating Databricks between Azure, AWS, and GCP. Cross-cloud migration is not a lift-and-shift — cloud accounts, identity, storage, and networking are different primitives on every cloud, so the platform has to be deliberately re-planned and rebuilt, not copied. This repo is that plan: a structured, practical runbook for platform teams, cloud architects, and security engineers doing the migration, plus an interactive planner that turns your source/target cloud pair into a concrete path through it.

## What a Databricks cross-cloud migration actually involves

Moving Databricks off one cloud and onto another means rebuilding, one deliberate layer at a time:

- **Identity** — Entra ID, AWS IAM, and GCP IAM do not map 1:1. Every managed identity, service principal, and group has to be redesigned for the target cloud's model, not translated line-for-line.
- **Storage** — ADLS Gen2, S3, and GCS have different path formats, access-delegation models, and encryption schemes. Every table, notebook, and job reference has to be rewritten.
- **Networking** — VNet/Private Link, VPC/PrivateLink, and VPC/Private Service Connect are rebuilt independently; a "no public IP" security posture has to be reproduced explicitly, not assumed.
- **Governance** — Unity Catalog metastores are regional and cannot move between clouds. A new metastore is created in the target, and catalogs, schemas, tables, and every grant are re-established — grants do not travel with data even when Delta Deep Clone copies the data itself.
- **Compute and pipelines** — cluster policies, init scripts, and Databricks Workflows/DLT pipelines are re-created against the new identity and storage foundation, sized to target-cloud instance types rather than assumed equivalent to source.

The runbook sequences this work end to end:

| Phase | Covers |
|---|---|
| **Overview** | What cross-cloud migration is, migration archetypes, and the decision framework for choosing one |
| **Discovery** | Workspace/asset inventory, dependency mapping, risk assessment |
| **Cloud mappings** | Construct-by-construct equivalency matrix plus all 6 directional deep-dives (Azure↔AWS, Azure↔GCP, AWS↔GCP) with concrete path-rewrite scripts |
| **Governance** | Unity Catalog strategy, metastore migration, grants and roles, legacy Hive transition, external locations and volumes |
| **Security** | IAM mapping, identity federation, secrets and KMS, network security, audit and compliance |
| **Compute** | Cluster migration, runtime upgrade, cluster policies, init scripts and libraries |
| **Pipelines** | Databricks Workflows/DLT, external orchestrators, CI/CD promotion |
| **Execution** | Wave planning → pilot → bulk migration → cutover → hypercare → rollback |
| **Validation** | Technical, data reconciliation, security, and business sign-off |
| **Templates** | Checklists, Terraform patterns, sample scripts, RACI, risk register |
| **Troubleshooting** | Common errors, anti-patterns, FAQ |

Pages still being written fall through to a placeholder route in the meantime — see [Contributing content](#contributing-content) if you want to help fill one in.

## Migration Planner

The homepage includes an interactive planner (`src/components/MigrationPlanner.tsx`): pick a source and target cloud and it returns whether you're looking at a same-cloud landing-zone move or a full cross-cloud platform reset, the specific identity/storage/network rework that pair requires, a recommended runbook reading path through the phases above, and the relevant toolset (Databricks CLI, UCX, Terraform provider, Delta Deep Clone, Delta Sharing, cloud CLIs).

## About this site

The runbook is published as a static docs site built with [Astro](https://astro.build), React, and Tailwind CSS, deployed to GitHub Pages automatically on every push to `main`. It's the delivery mechanism for the content above — search (⌘K), dark/light mode, table of contents, and the planner all exist to make the runbook usable, not as the point of the repo.

<details>
<summary>Tech stack, project structure, and local development</summary>

### Tech stack

- Astro 4.x, React 18, Tailwind CSS 3.4, TypeScript
- Framer Motion for the planner's interactions
- Lucide React icons + `simple-icons` for brand marks (Databricks, Terraform, GitHub, MLflow, Apache Spark, Kubernetes, Google Cloud render as real logos; AWS/Azure as brand-color wordmark badges since those marks aren't redistributable)

### Project structure

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

### Local development

```bash
npm install
npm run dev       # http://localhost:4321
npm run build     # static output to dist/
npm run preview   # serve the production build locally
```

</details>

## Contributing content

Most of the runbook's structure is already in `src/data/navigation.json`; many entries still need their page written.

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

Follow the existing pages' shape: intro, a comparison/decision table where relevant,
a concrete code sample (not pseudocode), then **Validation**, **Rollback**, and
**Automation opportunity** sections closing with a `<Checklist>`.
```

3. That's it — `[...slug].astro`'s `getStaticPaths` automatically excludes any nav slug that has a matching `.mdx` file, so your new page supersedes the placeholder with no routing changes needed.

## Deployment

Deploys to GitHub Pages automatically on push to `main` via `.github/workflows/deploy.yml` (build with `npm run build`, then `actions/deploy-pages`; Pages source is set to `workflow`, no `gh-pages` branch involved).

GitHub Pages serves a project repo under `/<repo-name>/`, not the domain root, so `astro.config.mjs` sets `site`/`base` accordingly and every internal link goes through `withBase()` in `src/lib/paths.ts` rather than a hardcoded root-relative path. Forking under a different repo name only requires updating `base` in `astro.config.mjs`.

## License

This is a reference implementation. Validate all commands and Terraform configurations against your environment and official Databricks documentation before production use.
