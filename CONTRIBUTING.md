# Contributing

Thanks for considering a contribution to the runbook. This is a content-first Astro/MDX
site — most contributions are new or corrected pages, not application code.

## Local setup

```bash
npm ci
npm run dev     # http://localhost:4321/databricks-cross-cloud-migration/
```

`predev`/`prebuild` regenerate `src/data/search-index.json` from every `.mdx` file automatically —
you never need to run that by hand, and you shouldn't hand-edit that file (it's gitignored).

Run the test suite and a full production build before opening a PR:

```bash
npm test
npm run build
```

## Adding or editing a runbook page

1. **Create the file** under `src/pages/<section>/<slug>.mdx`. Frontmatter shape:

   ```mdx
   ---
   title: 'Page title'
   layout: ../../layouts/Layout.astro
   description: 'One sentence for the nav/search/meta description.'
   ---

   import Callout from '../../components/Callout.tsx';
   import CodeBlock from '../../components/CodeBlock.tsx';
   import Checklist from '../../components/Checklist.tsx';

   # Page title
   ```

2. **Follow the page shape** every existing page uses — reviewers and readers expect it:
   executive framing → why it matters → applicability/inputs → recommended sequence →
   `## Validation` → `## Rollback` → `## Automation opportunity` → (optional) `## Evidence to
   capture` / cloud-specific caveats → (optional) `## Sources` for anything citing external docs.

3. **Register the page** in `src/data/navigation.json` under the right section, in reading order.
   The page won't appear in the sidebar or breadcrumbs without this.

4. **Use root-relative links** for anything internal — `[dependency mapping](/discovery/dependency-mapping)`,
   not a hardcoded `/databricks-cross-cloud-migration/...` prefix. The base path is added at build
   time by a remark plugin (`src/remark-base-path-links.mjs`, wired via `markdown.remarkPlugins` in
   `astro.config.mjs`). This only rewrites **markdown-syntax** links (`[text](/path)`) — a raw
   `<a href="/path">` inside JSX bypasses the plugin entirely and will 404 in production. Don't use
   raw anchor tags for internal links.

5. **Use the existing components**, don't invent new patterns for the same job:
   - `<Callout variant="warning|tip|prerequisite|decision">` for anything that needs visual weight.
   - `<CodeBlock language="..." filename="..." code={...} />` for any code sample.
   - `<Checklist title="..." items={[{ id, label }]} />` at the end of execution-shaped pages —
     it's an interactive, localStorage-persisted tracker, not decoration.
   - `<Tabs tabs={[{ label, content }]} />` for mutually-exclusive options (see `migration-archetypes.mdx`).

6. **Cite sources** for any claim about current Databricks/cloud-provider behavior, pricing, or
   API limits — link the official docs page, not just an assertion. Several pages got corrected
   after being checked against current (2025-2026) Databricks documentation; don't reintroduce
   stale claims (e.g. tool names, retention windows, GA dates) without a citation.

## Testing a UI/interactive change

If you touch a React component (a tool under `src/components/`, `Checklist`, `CodeBlock`, etc.),
run the dev server and check it in a real browser before opening the PR — a passing `npm run build`
only proves the page compiles, not that the interaction works. Check the browser console for
hydration errors, not just visible rendering.

## Pull request flow

- Branch off `main`: `git checkout -b content/<short-description>` or `ci/<short-description>`.
- CI runs automatically: unit tests, a full build (on PRs, via the `check` job), CodeQL, and
  Dependency Review. All four are **required status checks** on `main` — a PR can't merge until
  they pass.
- Keep PRs scoped to their stated intent — a content fix shouldn't also refactor an unrelated
  component. Note anything you noticed but didn't fix so it doesn't get lost.
- Direct pushes to `main` are reserved for trivial docs typos; everything else goes through a PR.

## Reporting a gap without writing the fix

Open an issue describing what's missing or wrong and, if you can, which page it belongs on or
near. Field experience on a specific cloud pairing, a tool that's changed behavior, or a step that
broke in practice are all useful even without a draft PR.
