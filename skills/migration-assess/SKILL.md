---
name: migration-assess
description: >
  Scan a codebase for Databricks cross-cloud migration blockers -- hardcoded
  DBFS paths, legacy hive_metastore references, cloud-specific identity
  (AWS instance profiles, Azure managed identities, GCP service accounts),
  stage-based MLflow model URIs, manual per-job CLI loops, hardcoded node
  types -- and report which ready-made accelerator fixes each one. Use when
  asked to assess a codebase for migration readiness, find what needs to
  change for a lift-and-shift, or identify migration blockers.
triggers:
  - "assess this codebase for migration"
  - "what needs to change for lift and shift"
  - "find migration blockers"
  - "check for hardcoded catalog paths"
  - "is this repo ready to migrate"
---

# Migration assessment

Deterministic scan first, agent reads the report second -- never read the whole codebase file by
file to look for these patterns. The script (`scripts/assess.py`, stdlib only, no install needed)
already did that; running it costs one command and a few hundred tokens of output, not a
file-by-file crawl.

## Step 1 — run the scanner

```bash
python3 scripts/assess.py <path-to-codebase> --format markdown -o assessment.md
```

Exit code is `1` when it found something (an intentional CI gate, matching the companion runbook's
own `dbxmig gaps`/`crossrefs` convention), `0` when clean. Read `assessment.md` — do not re-scan
the codebase yourself once this has run.

## Step 2 — read the report, not the code

The report groups findings by **what kind of migration work the codebase is doing**, not just by
file:

| Migration kind | What triggered it | Accelerator to point at |
|---|---|---|
| Metadata/table migration | DBFS paths, `hive_metastore.` refs, cloud-identity strings | [`dbxmig`](https://github.com/jthiruveedula/databricks-cross-cloud-migration) `gaps`/`crossrefs`, `databricks-replicator`, `workspace-migration` |
| Job/workflow migration | A per-job CLI export/import loop, a hardcoded instance type | Terraform Exporter, `databricks bundle init`/`generate job` |
| Data validation | A hand-rolled row-count assertion | `databrickslabs/lakebridge` Reconcile |
| MLflow/model registry | A stage-based `models:/name/Production` URI, `run.data.metrics` without `get_metric_history`, unpaged `search_runs` | `mlflow/mlflow-export-import` |

Each finding names the file, line, and why it blocks a migration — for the exact commands and
caveats behind each recommended tool, see the [Databricks cross-cloud migration
runbook](https://jthiruveedula.github.io/databricks-cross-cloud-migration/accelerators/databricks-tooling)
this skill's checks are drawn from.

## Step 3 — for the fix itself, reach for a Databricks-native coding agent skill

`databricks aitools install` puts Databricks-specific skills into Claude Code, Cursor, Codex CLI,
GitHub Copilot, or Gemini CLI — use it to draft the actual rewrites (cross-cloud node types,
catalog names, stage→alias URI rewrites) once this skill has told you where they're needed. This
skill finds and classifies; `aitools`-installed skills are the ones that know Databricks' own
rewrite conventions.

## Adding a new check

Every check in `scripts/assess.py`'s `CHECKS` tuple is `(regex, category, migration_kind, tool,
why)`. Add a new one there — the report renderer groups and formats automatically, nothing else
needs to change. Run `scripts/test_assess.py` after adding one; it asserts every check fires on a
small fixture repo before you trust it against something real.

## What this does not do

This is a static regex scan, not an execution trace or an LLM-graded review — it catches literal
patterns, not "this notebook will break for a subtler reason." Treat a clean report as "no known
pattern matched," not "definitely migration-ready." It does not modify anything; it only reports.
