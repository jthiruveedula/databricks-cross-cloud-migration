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

## Runbook structure

| Phase | Covers |
|---|---|
| **Overview** | What cross-cloud migration is, migration archetypes, the decision framework for choosing one, and when to govern remotely instead of migrating |
| **Discovery** | Workspace/asset inventory, dependency mapping, risk assessment |
| **Cloud mappings** | Construct-by-construct equivalency matrix plus all 6 directional deep-dives (Azure↔AWS, Azure↔GCP, AWS↔GCP) with concrete path-rewrite scripts |
| **Governance** | Unity Catalog strategy, metastore migration, grants and roles, legacy Hive transition, external locations and volumes, UCX-assisted migration |
| **Security** | IAM mapping, identity federation, secrets and KMS, network security, audit and compliance |
| **Compute** | Cluster migration, runtime upgrade, cluster policies, init scripts and libraries |
| **Pipelines** | Databricks Workflows/Lakeflow (DLT), external orchestrators, CI/CD promotion |
| **Analytics** | SQL queries, dashboards, alerts, notebooks and repos |
| **ML** | MLflow, model registry, feature assets, serving and artifacts |
| **Execution** | Wave planning → pilot → bulk migration → cutover → hypercare → rollback |
| **Validation** | Technical, data reconciliation, security, and business sign-off |
| **Templates** | Checklists, Terraform patterns, sample scripts, RACI, risk register |
| **Troubleshooting** | Common errors, anti-patterns, FAQ |

Every page follows the same shape: executive framing, why it matters, applicability, inputs required, recommended sequence, validation, rollback, automation opportunity, evidence to capture, and cloud-specific caveats, with code examples labeled illustrative where they aren't meant to be copy-pasted into production as-is.

## Migration Planner

The homepage includes an interactive planner: pick a source and target cloud and it returns whether you're looking at a same-cloud landing-zone move or a full cross-cloud platform reset, the specific identity/storage/network rework that pair requires, a recommended runbook reading path through the phases above, and the relevant toolset (Databricks CLI, UCX, Terraform provider, Delta Deep Clone, Delta Sharing, cloud CLIs).

## License

This is a reference implementation. Validate all commands and Terraform configurations against your environment and official Databricks documentation before production use.
