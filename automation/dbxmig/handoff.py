"""Hand the mechanical execution to the ready-made migration accelerators.

This toolkit plans a cross-cloud move -- it inventories, orders, translates
grants, and says what will not migrate. It deliberately does not try to be the
thing that *moves* petabytes: Databricks already ships and field-maintains
accelerators that do exactly that, and re-implementing them here would be a
worse copy nobody supports.

What was still manual was the join between the two. The same facts -- which
catalogs are in scope, which storage prefix becomes which, which source
principal becomes which target principal -- had to be hand-transcribed into
each accelerator's own config file, where a typo is a silently mis-scoped
migration rather than an error.

This module emits those configs from the configuration and inventory the rest
of the toolkit already reads, and renders the routing table that says which
accelerator owns which object class -- including the classes where the honest
answer is "none of them, rebuild it at cutover".

Coverage claims below are each tool's own, from its README; where a tool's
stated scope does not include cross-cloud, that is said rather than assumed
away.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .config import ConfigError, MigrationConfig
from .grants import PrincipalMap
from .models import FOREIGN, MATERIALIZED_VIEW, STREAMING_TABLE, Inventory

WORKSPACE_MIGRATION = "https://github.com/databricks-solutions/workspace-migration"
REPLICATOR = "https://github.com/databricks-solutions/databricks-replicator"
FLOWX = "https://github.com/databricks-solutions/flowx"
PLATFORM_KIT = "https://github.com/databricks-solutions/ai-platform-kit"
POWERBI_ACCELERATOR = (
    "https://github.com/databricks-solutions/powerbi-on-databricks-migration-accelerator"
)
ALTERYX_CONVERTER = "https://github.com/databricks-solutions/alteryx-to-databricks-converter"
WAF = "https://github.com/databricks-solutions/databricks-waf"
UCX = "https://github.com/databrickslabs/ucx"
LAKEBRIDGE = "https://github.com/databrickslabs/lakebridge"
TERRAFORM_EXPORTER = "https://docs.databricks.com/aws/en/admin/account-settings-e2/terraform-exporter"

#: UC object types `databricks-replicator` lists as supported today. Functions
#: and models are "In Development" in its README, so they are routed to
#: workspace-migration instead of being requested from a tool that will skip
#: them.
REPLICATOR_UC_OBJECT_TYPES: Tuple[str, ...] = (
    "storage_credentials",
    "external_locations",
    "catalogs",
    "schemas",
    "volumes",
    "tables",
    "views",
    "tags",
    "grants",
)

#: `storage_credential_config.target_credential_type` values the replicator
#: accepts, per target cloud. Azure has two (access connector vs managed
#: identity); the emitted config picks one and the handoff note says so.
CREDENTIAL_TYPE: Dict[str, str] = {
    "aws": "aws",
    "azure": "azure_managed_identity",
    "gcp": "gcp_service_account",
}


@dataclass(frozen=True)
class Route:
    """One object class and the accelerator that owns moving it."""

    object_class: str
    tool: str
    url: str
    covers: str
    stops_at: str
    #: Key into ``object_counts`` so the rendered table carries how many of
    #: these the source actually has -- a route with a zero count is work
    #: nobody has to schedule.
    count_key: str = ""


ROUTES: Tuple[Route, ...] = (
    Route(
        "Catalogs, schemas, tables, views, volumes (data + metadata)",
        "databricks-replicator",
        REPLICATOR,
        "Cross-metastore, cross-cloud incremental replication over D2D Delta "
        "Sharing, Deep Clone, and Auto Loader; explicitly cloud-agnostic",
        "UC functions and registered models (both 'in development'); object "
        "ownership; row filters and column masks; Hive metastore",
        "tables",
    ),
    Route(
        "Grants, tags, comments",
        "databricks-replicator",
        REPLICATOR,
        "Per-securable, per-principal privilege sync; incremental tag replication",
        "Ownership (`ALTER ... OWNER TO`) and row/column filters are not replicated",
        "grants",
    ),
    Route(
        "Functions, registered models, monitors, row filters / column masks / ABAC",
        "workspace-migration",
        WORKSPACE_MIGRATION,
        "SQL and Python functions, models (metadata + version artifacts + "
        "aliases), tags, filters/masks/ABAC policies, connections, foreign "
        "catalogs, Delta Sharing objects",
        "Its stated scope is control-plane, account-consolidation and "
        "cross-region moves -- not cross-cloud. Validate the data path on a "
        "pilot catalog before relying on it across clouds; use the replicator "
        "for the cross-cloud table move either way",
        "functions_and_models",
    ),
    Route(
        "Legacy Hive metastore objects",
        "workspace-migration (`migrate_hive`) + UCX",
        WORKSPACE_MIGRATION,
        "Like-for-like databases, tables, views, functions and grants into the "
        "target's own `hive_metastore`",
        "It is a copy, not an upgrade into Unity Catalog -- UCX does the "
        "Hive-to-UC upgrade, on either side",
        "",
    ),
    Route(
        "Materialized views, streaming tables",
        "none",
        "",
        "Nothing migrates these: both accelerators hard-skip them",
        "Rebuild by refreshing the owning pipeline against the target at "
        "cutover; schema and grants migrate, the object does not",
        "pipeline_outputs",
    ),
    Route(
        "DLT / Lakeflow pipelines, model serving endpoints, Apps",
        "Terraform exporter",
        TERRAFORM_EXPORTER,
        "Exports the resources as Terraform for replay against the target",
        "Runtime differences across clouds -- compute and instance types still "
        "need a deliberate re-map",
        "",
    ),
    Route(
        "Jobs, clusters, policies, notebooks, dashboards",
        "dbxmig bundle",
        "",
        "`dbxmig bundle` turns the workspace inventory into Declarative "
        "Automation Bundle YAML with every schedule paused",
        "Cross-cloud node types and init scripts are flagged for review, not "
        "auto-translated",
        "",
    ),
    Route(
        "Azure Data Factory / Apache Airflow pipelines",
        "flowx",
        FLOWX,
        "Translates ADF and Airflow pipelines into Lakeflow Jobs packaged as "
        "DABs -- deterministic for known activity types, agentic for the rest",
        "Source-system connectivity and credentials are re-created by hand",
        "",
    ),
    Route(
        "Power BI semantic models",
        "powerbi-on-databricks-migration-accelerator",
        POWERBI_ACCELERATOR,
        "Bulk-repoints `.pbip` semantic models at Databricks SQL + Unity "
        "Catalog by rewriting Power Query M, with `-WhatIf` previews",
        "It repoints; it does not convert reports to Metric Views or AI/BI "
        "dashboards",
        "",
    ),
    Route(
        "Alteryx workflows",
        "alteryx-to-databricks-converter",
        ALTERYX_CONVERTER,
        "Converts `.yxmd` workflows to PySpark, DLT, Spark SQL and Lakeflow "
        "Designer output without an Alteryx licence",
        "Unsupported tools are reported, not silently dropped -- review before "
        "running",
        "",
    ),
    Route(
        "Target workspace, metastore, identity, networking",
        "ai-platform-kit",
        PLATFORM_KIT,
        "Agent-driven provisioning of workspaces, Unity Catalog, SCIM groups "
        "and private networking across Azure, AWS and GCP, plus a three-path "
        "deployment verification",
        "It writes Terraform and SDK calls against your requirements -- review "
        "them; it is not a certified landing zone",
        "",
    ),
    Route(
        "Source warehouse / ETL SQL conversion and reconciliation",
        "lakebridge",
        LAKEBRIDGE,
        "Analyzer, Converter and Validator for warehouse and ETL migration "
        "into Databricks SQL",
        "Orchestration mapping -- pair with flowx",
        "",
    ),
    Route(
        "Post-migration architecture review",
        "databricks-waf",
        WAF,
        "Assesses the target against the seven Well-Architected pillars and "
        "traces each gap to evidence and affected resources",
        "Alpha; it reviews the target, it does not migrate anything",
        "",
    ),
)


def object_counts(inventory: Inventory) -> Dict[str, int]:
    """Counts keyed to ``Route.count_key`` -- what each route actually owns here."""
    pipeline_outputs = sum(
        1 for t in inventory.tables if t.table_type in (MATERIALIZED_VIEW, STREAMING_TABLE)
    )
    return {
        "tables": sum(
            1
            for t in inventory.tables
            if t.table_type not in (MATERIALIZED_VIEW, STREAMING_TABLE, FOREIGN)
        ),
        "grants": len(inventory.grants),
        "functions_and_models": len(inventory.functions) + len(inventory.models),
        "pipeline_outputs": pipeline_outputs,
    }


def scoped_catalogs(config: MigrationConfig, inventory: Inventory) -> List[str]:
    """Catalogs in the inventory that the config puts in scope, in a stable order.

    An empty ``source.catalogs`` means "everything discovered" -- the same
    convention both accelerators use for an empty filter.
    """
    scope = set(config.source.catalogs)
    names = sorted({c.name for c in inventory.catalogs})
    return [name for name in names if not scope or name in scope]


def unmapped_locations(config: MigrationConfig, inventory: Inventory) -> List[Tuple[str, str]]:
    """External storage this migration has no path rule for.

    The replicator's ``cloud_url_mapping`` is exactly the toolkit's
    ``path_rules``, so anything the rewriter cannot map is a hole in the
    emitted config -- surfaced here instead of being written out incomplete.
    """
    rewriter = config.rewriter()
    holes: List[Tuple[str, str]] = []
    for location in inventory.external_locations:
        if location.url and not rewriter.rewrite_uri(location.url).mapped:
            holes.append((location.name, location.url))
    for table in inventory.tables:
        if not table.storage_location:
            continue
        if not rewriter.rewrite_uri(table.storage_location).mapped:
            holes.append((table.full_name, table.storage_location))
    for volume in inventory.volumes:
        if not volume.storage_location:
            continue
        if not rewriter.rewrite_uri(volume.storage_location).mapped:
            holes.append((volume.full_name, volume.storage_location))
    return sorted(holes)


def unrouted(inventory: Inventory) -> List[Tuple[str, str]]:
    """Objects no accelerator in ``ROUTES`` migrates, with why."""
    items: List[Tuple[str, str]] = []
    for table in inventory.tables:
        if table.table_type in (MATERIALIZED_VIEW, STREAMING_TABLE):
            items.append(
                (
                    table.full_name,
                    "{0} -- both accelerators skip it; refresh the owning pipeline "
                    "against the target at cutover".format(table.table_type.lower()),
                )
            )
    for function in inventory.functions:
        if function.language.upper() not in ("SQL", "PYTHON"):
            items.append(
                (
                    function.full_name,
                    "{0} function -- workspace-migration covers SQL and Python "
                    "only; rewrite it by hand".format(function.language),
                )
            )
    return sorted(items)


def workspace_migration_config(config: MigrationConfig, inventory: Inventory) -> Dict[str, Any]:
    """`config.yaml` for the workspace-migration DAB, scoped to this migration.

    Secrets are never written: the SPN client secret lives in the Databricks
    secret scope this file only names, matching the accelerator's own design.
    """
    # An empty filter means "everything" to both accelerators, so falling back
    # to the configured scope matters: an inventory that resolved to nothing
    # would otherwise widen a scoped migration to the whole metastore silently.
    catalogs = scoped_catalogs(config, inventory) or list(config.source.catalogs)
    return {
        "source_workspace_url": config.source.host,
        "target_workspace_url": config.target.host,
        "spn_client_id": "REPLACE_WITH_APPLICATION_ID",
        "spn_secret_scope": "migration",
        "spn_secret_key": "spn-secret",
        "catalog_filter": ",".join(catalogs),
        "schema_filter": "",
        "dry_run": True,
        "batch_size": 50,
        "tracking_catalog": "migration_tracking",
        "tracking_schema": "cp_migration",
        # A cross-cloud target is a fresh metastore, so a name already taken
        # there belongs to someone else. Fail rather than migrate into it --
        # the same call `dbxmig gaps --target-inventory` makes.
        "on_target_collision": "fail",
        "overwrite_existing": False,
        "transfer_ownership": True,
    }


def replicator_environment(config: MigrationConfig) -> Dict[str, Any]:
    """`environments.yaml` for databricks-replicator: the two workspaces."""
    source_cloud = config.source.cloud or "source"
    target_cloud = config.target.cloud or "target"
    name = "{0}_to_{1}".format(source_cloud, target_cloud)
    return {
        "version": "1.0",
        "environments": {
            name: {
                "description": "Emitted by dbxmig handoff from the migration config",
                "is_default": True,
                "source_databricks_connect_config": {
                    "name": source_cloud,
                    "host": config.source.host,
                    "auth_type": "oauth",
                },
                "target_databricks_connect_config": {
                    "name": target_cloud,
                    "host": config.target.host,
                    "auth_type": "oauth",
                },
            }
        },
    }


def replicator_group(
    config: MigrationConfig,
    catalog: str,
    principal_map: Optional[PrincipalMap] = None,
) -> Dict[str, Any]:
    """One replication-group config for one source catalog.

    ``cloud_url_mapping`` and ``principal_mapping`` are this toolkit's
    ``path_rules`` and principal map verbatim -- the transcription step this
    command exists to remove.
    """
    target_catalog = config.catalog_map.get(catalog, catalog)
    # Guessing here would hand the replicator a credential type for the wrong
    # cloud, which fails at storage-credential creation rather than at config
    # time. Refuse instead.
    if config.target.cloud not in CREDENTIAL_TYPE:
        raise ConfigError(
            "target.cloud is {0!r}; databricks-replicator needs one of {1} to pick "
            "storage_credential_config.target_credential_type".format(
                config.target.cloud or "unset", ", ".join(sorted(CREDENTIAL_TYPE))
            )
        )
    credential_type = CREDENTIAL_TYPE[config.target.cloud]
    group: Dict[str, Any] = {
        "version": "1.0",
        "replication_group": "{0}_to_{1}".format(catalog, target_catalog),
        "uc_object_types": list(REPLICATOR_UC_OBJECT_TYPES),
        "table_types": ["all"],
        "storage_credential_config": {"target_credential_type": credential_type},
        "cloud_url_mapping": {
            rule.source_prefix: rule.target_prefix for rule in config.path_rules
        },
        "backup_config": {"enabled": True, "source_catalog": catalog},
        "replication_config": {"enabled": True, "enforce_schema": True},
        "reconciliation_config": {"enabled": True, "missing_data_check": False},
        "concurrency": {"max_workers": 5, "timeout_seconds": 1800},
        "retry": {"max_attempts": 2, "retry_delay_seconds": 3},
    }
    if principal_map and principal_map.mapping:
        group["principal_mapping"] = dict(sorted(principal_map.mapping.items()))
    return group


@dataclass
class HandoffResult:
    files: Dict[str, str] = field(default_factory=dict)
    unrouted: List[Tuple[str, str]] = field(default_factory=list)
    unmapped: List[Tuple[str, str]] = field(default_factory=list)

    def needs_review(self) -> bool:
        return bool(self.unrouted or self.unmapped)


def _yaml(payload: Any, header: Sequence[str] = ()) -> str:
    from .bundle import _yaml as dump

    prefix = "".join(("# {0}\n".format(line) if line else "#\n") for line in header)
    return prefix + dump(payload)


def handoff_markdown(
    config: MigrationConfig,
    inventory: Inventory,
    result: HandoffResult,
    catalogs: Sequence[str],
) -> str:
    counts = object_counts(inventory)
    lines = [
        "# Accelerator handoff",
        "",
        "Generated by `dbxmig handoff`. This toolkit planned the move; the tools",
        "below execute it. Every config here was filled from the same migration",
        "config the rest of the toolkit reads, so the scope, the storage-prefix",
        "rewrites, and the principal map cannot drift between them.",
        "",
        "Source `{0}` ({1}) -> target `{2}` ({3}); {4} catalog(s) in scope: {5}.".format(
            config.source.host or "unset",
            config.source.cloud or "cloud unset",
            config.target.host or "unset",
            config.target.cloud or "cloud unset",
            len(catalogs),
            ", ".join("`{0}`".format(c) for c in catalogs) or "none",
        ),
        "",
        "## Who moves what",
        "",
        "| Object class | Count | Accelerator | Covers | Stops at |",
        "| --- | --- | --- | --- | --- |",
    ]
    for route in ROUTES:
        count = counts.get(route.count_key, "")
        tool = (
            "[{0}]({1})".format(route.tool, route.url) if route.url else "`{0}`".format(route.tool)
        )
        lines.append(
            "| {0} | {1} | {2} | {3} | {4} |".format(
                route.object_class,
                count if count != "" else "--",
                tool,
                route.covers,
                route.stops_at,
            )
        )
    lines += [
        "",
        "## Emitted files",
        "",
        "```bash",
        "# 1. Provision the target platform first -- nothing below has anywhere to land",
        "#    without it: https://github.com/databricks-solutions/ai-platform-kit",
        "",
        "# 2. UC data + metadata, cross-cloud (databricks-replicator)",
        "cp databricks-replicator/*.yaml <replicator-checkout>/configs/cross_metastore/",
        "data-replicator configs/cross_metastore/{0}.yaml \\".format(
            "{0}_to_{1}".format(
                catalogs[0] if catalogs else "catalog",
                config.catalog_map.get(catalogs[0], catalogs[0]) if catalogs else "catalog",
            )
        ),
        "  --target-catalogs {0}".format(
            config.catalog_map.get(catalogs[0], catalogs[0]) if catalogs else "<target-catalog>"
        ),
        "",
        "# 3. Functions, models, filters/masks, connections (workspace-migration)",
        "cp workspace-migration/config.yaml <workspace-migration-checkout>/config.yaml",
        "databricks bundle deploy --var migration_spn_id=<app-id>",
        "",
        "# 4. Jobs, pipelines, notebooks -- this toolkit, already paused on arrival",
        "dbxmig -c migration.yaml bundle -w workspace.json -o ./bundle",
        "```",
        "",
        "`dry_run` is `true` in the emitted workspace-migration config and the",
        "replicator groups reconcile after every run. Both are deliberate: the",
        "first real run of an accelerator against a target metastore should be a",
        "report, not a write.",
        "",
    ]
    lines += [
        "## Nothing routes these",
        "",
    ]
    if result.unrouted:
        lines.append("| Object | Why |")
        lines.append("| --- | --- |")
        lines += ["| `{0}` | {1} |".format(name, why) for name, why in result.unrouted]
    else:
        lines.append("Nothing in this inventory falls outside every accelerator's coverage.")
    lines += ["", "## Storage locations with no path rule", ""]
    if result.unmapped:
        lines.append(
            "These have no `path_rules` entry, so the replicator's "
            "`cloud_url_mapping` emitted above does not cover them. Add a rule "
            "and re-run, or the objects land pointing at source-cloud storage."
        )
        lines.append("")
        lines.append("| Object | Unmapped location |")
        lines.append("| --- | --- |")
        lines += ["| `{0}` | `{1}` |".format(name, uri) for name, uri in result.unmapped]
    else:
        lines.append("Every external location in the inventory maps through a `path_rules` entry.")
    lines.append("")
    return "\n".join(lines)


def generate_handoff(
    config: MigrationConfig,
    inventory: Inventory,
    principal_map: Optional[PrincipalMap] = None,
) -> HandoffResult:
    """Emit every accelerator config this migration needs, plus the routing note."""
    catalogs = scoped_catalogs(config, inventory)
    result = HandoffResult(
        unrouted=unrouted(inventory),
        unmapped=unmapped_locations(config, inventory),
    )
    result.files["workspace-migration/config.yaml"] = _yaml(
        workspace_migration_config(config, inventory),
        header=[
            "workspace-migration config, emitted by dbxmig handoff.",
            "Copy to the workspace-migration checkout as config.yaml (git-ignored there).",
            "The SPN secret itself stays in the named secret scope, never in this file.",
            "See " + WORKSPACE_MIGRATION,
        ],
    )
    result.files["databricks-replicator/environments.yaml"] = _yaml(
        replicator_environment(config),
        header=[
            "databricks-replicator environments, emitted by dbxmig handoff.",
            "Tokens/secret scopes are intentionally absent -- add them for the auth",
            "mode you run with, or run inside one of the two workspaces.",
            "See " + REPLICATOR,
        ],
    )
    for catalog in catalogs:
        target_catalog = config.catalog_map.get(catalog, catalog)
        name = "{0}_to_{1}".format(catalog, target_catalog)
        result.files["databricks-replicator/{0}.yaml".format(name)] = _yaml(
            replicator_group(config, catalog, principal_map),
            header=[
                "cli: data-replicator configs/cross_metastore/{0}.yaml "
                "--target-catalogs {1}".format(name, target_catalog),
                "cloud_url_mapping and principal_mapping come from this migration's",
                "path_rules and principal map -- edit them there, not here.",
                "",
                "Delta Sharing infrastructure is NOT auto-created: create_recipient,",
                "create_share, add_to_share, create_backup_catalog and",
                "create_shared_catalog all keep their upstream default of false, so",
                "running this writes nothing to the source metastore you did not ask",
                "for. Set them true to let the replicator build the share infra, or",
                "point it at infra you provision yourself (Terraform, or the",
                "external-locations-and-volumes runbook page).",
            ],
        )
    result.files["HANDOFF.md"] = handoff_markdown(config, inventory, result, catalogs)
    return result
