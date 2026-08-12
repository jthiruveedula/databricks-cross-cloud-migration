# dbxmig — Unity Catalog metastore migration toolkit

Companion code for the [Databricks cross-cloud migration runbook](https://jthiruveedula.github.io/databricks-cross-cloud-migration/).
The runbook explains what to do and why. This does the mechanical parts of it
repeatably, and — more importantly — tells you what it **cannot** do, so the
objects that need a human are a list rather than a surprise.

A Unity Catalog metastore is regional and account-bound: cross-cloud migration
always means building a new metastore and replaying content into it. Grants do
not travel with data, principals are account-scoped, `CLONE` never copies
history or permissions, and materialized views and streaming tables cannot be
cloned at all. Those constraints are what this toolkit encodes.

## Install

```bash
cd automation
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'          # offline: planning, DDL, grants, reconciliation
pip install -e '.[databricks]'   # add live workspace access
```

The Databricks SDK is an **optional** extra on purpose. Everything except
`inventory` against a live workspace and `apply --execute` runs offline against
a JSON inventory, so the entire migration can be generated and reviewed before
anyone holds credentials for the target account.

## Try it with no cloud account

The repository ships a fixture metastore that deliberately contains the awkward
cases — an external table with no mapped path, a view on a view, a view reading
out of scope, a materialized view, a streaming table, a Scala function, a
registered model, a retired principal, a masked column:

```bash
# The metastore half
dbxmig -c examples/migration.fixture.yaml gaps -i tests/fixtures/source_metastore.json
dbxmig -c examples/migration.fixture.yaml ddl  -i tests/fixtures/source_metastore.json

# The workspace half
dbxmig -c examples/migration.fixture.yaml workspace  --fixture tests/fixtures/workspace.json -o ws.json
dbxmig -c examples/migration.fixture.yaml crossrefs  -w tests/fixtures/workspace.json

# ...and the code, with line numbers
dbxmig -c examples/migration.fixture.yaml crossrefs  -w tests/fixtures/workspace.json -s ../src
```

`gaps` exits non-zero when anything needs a decision. That makes it usable as a
CI gate on the migration itself, not just a report you read once.

## The sequence

| Command | What it does | Needs a workspace |
|---|---|---|
| `validate` | Check the config before anything else runs | no |
| `inventory` | Export the source **metastore** to JSON | yes (source) |
| `workspace` | Collect the **workspace plane** — jobs, clusters, policies, pools, warehouses, dashboards, queries, alerts, secret scopes, repos, principals, object ACLs — as JSON plus one CSV per asset class | yes (source) |
| `crossrefs` | What each workspace asset depends on and what breaks: storage paths, secrets, policies, warehouses, IAM identities, plus which assets must move in the same wave. `--source DIR` also scans exported notebooks and repo code, reporting a file and line number | no |
| `plan` | Order every object by dependency into executable steps | no |
| `gaps` | **Read this one.** Everything that will not migrate on its own | no |
| `ddl` | Emit target SQL, idempotent, in dependency order | no |
| `grants` | Emit translated `GRANT` and `SET OWNER` statements | no |
| `apply` | Execute the plan, resumably (dry-run unless `--execute`) | yes (target) |
| `reconcile` | Prove the target matches the source | no |
| `report` | One markdown file covering all of the above | no |

```bash
export DBX_SOURCE_TOKEN=...   # never in the config file
dbxmig -c migration.yaml validate
dbxmig -c migration.yaml inventory -o inventory.json
dbxmig -c migration.yaml gaps      -i inventory.json -o gaps.md      # fix these first
dbxmig -c migration.yaml ddl       -i inventory.json -o target.sql   # review this diff
dbxmig -c migration.yaml grants    -i inventory.json -o grants.sql
dbxmig -c migration.yaml apply     -i inventory.json                 # dry run
dbxmig -c migration.yaml apply     -i inventory.json --execute
dbxmig -c migration.yaml inventory -o target-inventory.json          # against the target
dbxmig -c migration.yaml reconcile -i inventory.json -t target-inventory.json
```

## Design decisions worth knowing

**Order is enforced, not assumed.** Storage credential → external location →
catalog → schema → volume → table → constraint → view → function → model →
row/column policy → grant, with views topologically sorted among themselves so a
view built on another view comes second. Getting this wrong produces a
permission error several steps later, which is the worst kind of failure to
debug at 2am.

**Nothing is skipped silently.** An object the toolkit cannot migrate becomes a
*blocked step* that appears in the plan, in the gap report, in the generated SQL
as a `-- BLOCKED` comment, and in the exit code. There is no path where an
object quietly disappears between source and target.

**Generated SQL is a reviewable artifact.** `ddl` and `grants` write files, they
do not execute. A migration you can read as a diff before anyone runs it is a
migration a security reviewer can sign off. Every statement is idempotent
(`IF NOT EXISTS` / `OR REPLACE`) so a re-run is safe.

**Runs are resumable.** `apply` journals every statement outcome to JSONL.
Re-running after an interruption skips what already succeeded — recovery is the
same command, not a different one. The journal is also the audit record.

**Unmapped principals are fatal, not skipped.** A grant whose grantee has no
target mapping aborts translation in strict mode. Skipping it would produce a
target that looks migrated and quietly denies access to whoever held it. A
principal that is genuinely not migrating goes in the `retired` list, which
makes it a recorded decision.

**Ownership is replayed separately from grants.** An object's owner is not
reproduced by any `GRANT` statement. Without the `SET OWNER` pass, whoever ran
the migration owns everything, silently concentrating `MANAGE` on one account.

**The LLM is on a short leash.** The deterministic rewriter runs first and
handles nearly everything. A model is consulted only for objects it could not
finish, only when explicitly enabled with an endpoint, and only after string
literals are redacted. Every output then passes a mechanical gate — single
statement, right object, no residual source URIs, no references outside an
allow-list — and output that fails is discarded rather than repaired. Model id
and prompt version are recorded with each result. The default backend translates
nothing and escalates to a human.

## What it does not do

Deliberately out of scope, and reported as manual work rather than pretended:

- **Storage credentials.** Cloud identity cannot be copied across clouds; the
  target IAM role, managed identity, or service account is built first.
- **Registered model versions.** Model artifacts move with the MLflow client, not
  with DDL.
- **Materialized views and streaming tables.** Recreate the Lakeflow/DLT pipeline
  and let it refresh; `CLONE` rejects them as source or target.
- **Row filters and column masks.** Not copied by `CLONE`; re-bound after the
  masking functions exist in the target.
- **Connections, shares, and recipients.** Recorded in the inventory and listed
  in the gap report; recreated by hand, and recipients need new activation.
- **Anything outside the metastore** — jobs, clusters, dashboards, secrets,
  audit history. See the runbook's *what does not migrate* page.

## Tests

```bash
pytest          # 166 tests, no credentials, no network
ruff check .
```

## Status

Reference implementation, not a Databricks product. Validate every generated
statement against your own environment and the current Databricks documentation
before running it in production.

MIT licensed, same as the rest of the repository.
