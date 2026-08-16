# Databricks Cross-Cloud Migration Runbook

**Live site: https://jthiruveedula.github.io/databricks-cross-cloud-migration/**

An enterprise runbook for migrating Databricks between Azure, AWS, and GCP. Cross-cloud migration is not a lift-and-shift — cloud accounts, identity, storage, and networking are different primitives on every cloud, so the platform has to be deliberately re-planned and rebuilt, not copied. This is that plan: a structured, practical runbook for platform teams, cloud architects, and security engineers doing the migration.

## What a Databricks cross-cloud migration actually involves

Moving Databricks off one cloud and onto another means rebuilding, one deliberate layer at a time:

- **Identity** — Entra ID, AWS IAM, and GCP IAM do not map 1:1. Every managed identity, service principal, and group has to be redesigned for the target cloud's model, not translated line-for-line. Workspace-local groups must be converted to account-level groups before Unity Catalog grants will behave correctly.
- **Storage** — ADLS Gen2, S3, and GCS have different path formats, access-delegation models, and encryption schemes. Every table, notebook, and job reference has to be rewritten, and legacy DBFS mounts should be retired in favor of Unity Catalog external locations and volumes.
- **Networking** — VNet/Private Link, VPC/PrivateLink, and VPC/Private Service Connect are rebuilt independently; a "no public IP" security posture has to be reproduced explicitly, not assumed.
- **Governance** — Unity Catalog metastores are regional and cannot move between clouds. A new metastore is created in the target, and catalogs, schemas, tables, and every grant are re-established — grants do not travel with data even when Delta Deep Clone copies the data itself.
- **Compute and pipelines** — cluster policies, init scripts, and Databricks Workflows/Lakeflow (DLT) pipelines are re-created against the new identity and storage foundation, sized to target-cloud instance types rather than assumed equivalent to source.

Before committing to a physical migration, it's also worth asking whether the actual driver can be satisfied by governing data remotely instead — Unity Catalog federation (foreign catalogs, Delta Sharing, Lakehouse Federation) can provide governed cross-cloud access without moving data at all, and is sometimes the permanent answer rather than a migration stopgap.

## Start here

New to the runbook, or leading a migration? **[Start here — by role](https://jthiruveedula.github.io/databricks-cross-cloud-migration/overview/start-here-by-role)** gives the architect, the platform engineer, the project manager, and the domain owner each a first week, the decisions only they can make, and a reading path through the sections below that are actually theirs.

## Runbook structure

| Phase | Covers |
|---|---|
| **Overview** | What cross-cloud migration is, migration archetypes, the decision framework for choosing one, and when to govern remotely instead of migrating |
| **Discovery** | Workspace/asset inventory, dependency mapping, risk assessment |
| **Cloud mappings** | Construct-by-construct equivalency matrix plus all 6 directional deep-dives (Azure↔AWS, Azure↔GCP, AWS↔GCP) with concrete path-rewrite scripts |
| **Governance** | Unity Catalog strategy, metastore migration, grants and roles, legacy Hive transition, external locations and volumes, UCX-assisted migration, disaster recovery |
| **Security** | IAM mapping, identity federation, secrets and KMS, network security, audit and compliance |
| **Compute** | Cluster migration, runtime upgrade, cluster policies, init scripts and libraries |
| **Pipelines** | Databricks Workflows/Lakeflow (DLT), external orchestrators, CI/CD promotion |
| **Analytics** | SQL queries, dashboards, alerts, notebooks and repos, BI tool reconnection (Power BI/Tableau/Looker) |
| **ML** | MLflow, model registry, feature assets, serving and artifacts |
| **Execution** | Wave planning → pilot → large-scale data transfer → bulk migration → cutover → hypercare → rollback |
| **Validation** | Technical, data reconciliation, security, and business sign-off |
| **Templates** | Checklists, Terraform patterns, sample scripts, RACI, risk register |
| **Troubleshooting** | Common errors, anti-patterns, FAQ |
| **Accelerators** | AI-assisted migration, Databricks migration tooling (UCX, Lakebridge, Replicator) |
| **Collaboration** | Cross-cloud data collaboration — Delta Sharing, Lakehouse Federation, Clean Rooms, dual-run CDC |
| **Tools** | Browser-only, no-data-leaves-the-page calculators: cost calculator, instance type mapper, timeline estimator, RACI builder, dependency graph |

Every page follows the same shape: executive framing, why it matters, applicability, inputs required, recommended sequence, validation, rollback, automation opportunity, evidence to capture, and cloud-specific caveats, with code examples labeled illustrative where they aren't meant to be copy-pasted into production as-is.

## Migration Planner

The homepage includes an interactive planner: pick a source and target cloud and it returns whether you're looking at a same-cloud landing-zone move or a full cross-cloud platform reset, the specific identity/storage/network rework that pair requires, a recommended runbook reading path through the phases above, and the relevant toolset (Databricks CLI, UCX, Terraform provider, Delta Deep Clone, Delta Sharing, cloud CLIs).

## Tech stack and content tooling

- **[Astro 7](https://astro.build/)** with **[MDX](https://docs.astro.build/en/guides/integrations-guide/mdx/)** — every runbook page is a `.mdx` file: prose plus interactive React islands (`client:visible`), not a static-site-generator template.
- **React 19** components for anything interactive — `Callout`, `Checklist` (localStorage-persisted progress tracking), `CodeBlock` (copy/download, syntax highlighted via `prism-react-renderer`), `Tabs`, plus purpose-built tools (cost calculator, instance mapper, dependency graph, RACI builder, timeline estimator) — animated with **Framer Motion** and **GSAP**. Diagrams (the hero, per-chapter migration-journey visuals) are hand-built SVG/React components (`JourneyVisual`, `MigrationJourney`), not a diagramming library.
- **[Archify](https://github.com/tt-a1i/archify)** — ten generated interactive diagrams (six cloud-pair architectures, plus data flow, cutover workflow, event sequence, and per-table lifecycle), collected on [Visual atlas](https://jthiruveedula.github.io/databricks-cross-cloud-migration/overview/visual-atlas) and embedded inline on the page each one belongs to. Each is a typed JSON spec in `diagrams/` rendered to a self-contained HTML file in `public/diagrams/` (`npm run build:diagrams`), with its own theme, guided views, route tracing, and PNG/SVG/WebM export. The rendered files are committed so CI never depends on the generator.
- **A custom remark plugin** (`src/remark-base-path-links.mjs`) — rewrites root-relative markdown links (`[x](/path)`) to include the GitHub Pages base path (`/databricks-cross-cloud-migration/`) at build time, so page authors can write normal-looking links without knowing about the base path. Wired via `markdown.remarkPlugins` in `astro.config.mjs` (not `mdx({ remarkPlugins })` — that option is a no-op in this Astro version).
- **Shiki** (`github-dark` theme) for static syntax highlighting in fenced code blocks.
- **[MiniSearch](https://github.com/lucaong/minisearch)** — powers full-text search (⌘K) over an index generated from every page's headings and prose (`scripts/build-search-index.mjs`, regenerated on every `dev`/`build`).
- **[Tailwind CSS v4](https://tailwindcss.com/)** via the Vite plugin, with light/dark theme support (`next-themes`).
- **Vitest** for unit tests (`src/**/*.test.ts`) — path helpers, the search-index builder, and the interactive tool components' calculation logic.

## Contributing

Found a gap, an inaccuracy, or want to add a phase/page? Open an issue or a PR — anyone can propose changes, and review is evidence-based (a docs citation, a repro, a passing test), not opinion-based. Every PR references an issue (`Closes #N`); anything bigger than a single-page fix — a new phase, a major upgrade — gets a tracking issue broken into sub-issues first. See [CONTRIBUTING.md](./CONTRIBUTING.md) for the full page-authoring conventions (frontmatter, the Validation/Rollback/Automation-opportunity shape, navigation + search-index wiring) and the PR/CI workflow.

## License

[MIT](./LICENSE) — reuse the structure and code freely. This is still a reference implementation: validate all commands and Terraform configurations against your environment and official Databricks documentation before production use.
