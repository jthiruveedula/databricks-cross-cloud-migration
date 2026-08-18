"""Generate a Declarative Automation Bundle from a collected workspace inventory.

Recreating a few hundred jobs by hand in a target workspace is the least
interesting and most error-prone part of a migration. The inventory already
holds the definitions; this turns them into bundle YAML that can be reviewed as
a diff, committed, and deployed with ``databricks bundle deploy``.

Three rules shape the output, all of them consequences of the same idea — that
a generated artifact you cannot trust is worse than no artifact at all:

* **Server-owned fields are stripped.** ``job_id``, ``created_time``,
  ``creator_user_name`` and friends belong to the source workspace. Carrying
  them into a bundle produces resources that either fail to deploy or bind to
  the wrong thing.
* **Every ID that changes across workspaces becomes a variable.** Cluster
  policy IDs, SQL warehouse IDs, and instance pool IDs are workspace-scoped.
  They are emitted as bundle variables with **no default**, so
  ``databricks bundle deploy`` fails loudly until someone supplies the target
  value. A silent wrong ID is the failure this prevents.
* **Nothing is dropped quietly.** An asset the generator cannot faithfully
  reproduce is written to ``REVIEW.md`` with the reason, not omitted.

The bundle is a starting point for review, not a finished deliverable. Diff it
against the source definitions before deploying anything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .rewrite import Rewriter
from .streaming import StreamingReport
from .workspace import WorkspaceInventory

#: Fields the source workspace owns. Present in an API response, meaningless or
#: actively harmful in a bundle definition.
SERVER_OWNED_FIELDS = frozenset(
    {
        "job_id",
        "pipeline_id",
        "cluster_id",
        "created_time",
        "creator_user_name",
        "run_as_user_name",
        "created_by",
        "last_modified",
        "state",
        "latest_updates",
        "cluster_source",
        "start_time",
        "terminated_time",
        "last_state_loss_time",
        "default_tags",
        "effective_budget_policy_id",
        "url",
        "health",
    }
)

#: Fields whose value is workspace- or cloud-scoped and must be re-pointed.
#: Each becomes a bundle variable with no default, so the deploy fails until a
#: target value is supplied. ``node_type_id`` is here for a different reason
#: than the rest: it is not an id that changed, it is an instance type that does
#: not exist in the target cloud at all.
VARIABLE_FIELDS = {
    "policy_id": ("policy", "cluster policy"),
    "warehouse_id": ("warehouse", "SQL warehouse"),
    "instance_pool_id": ("pool", "instance pool"),
    "driver_instance_pool_id": ("pool", "instance pool"),
    "query_id": ("query", "saved query"),
    "node_type_id": ("node_type", "worker instance type (source-cloud specific)"),
    "driver_node_type_id": ("node_type", "driver instance type (source-cloud specific)"),
}

#: Fields holding a *bare* catalog name rather than a dotted reference. The
#: identifier rewriter only matches ``catalog.something``, so a pipeline's
#: ``catalog: prod`` would otherwise survive a catalog rename untouched and the
#: pipeline would write into the wrong catalog in the target.
CATALOG_NAME_FIELDS = frozenset({"catalog", "target_catalog", "source_catalog"})

#: URI scheme -> the key Databricks uses for an init-script location. Rewriting
#: a path from ADLS to GCS without changing this key produces a config that is
#: syntactically valid and points nowhere.
SCHEME_TO_INIT_KEY = {
    "abfss": "abfss",
    "abfs": "abfss",
    "wasbs": "abfss",
    "s3": "s3",
    "s3a": "s3",
    "gs": "gcs",
    "dbfs": "dbfs",
}


@dataclass
class BundleVariable:
    name: str
    description: str
    source_value: str

    def to_dict(self) -> Dict[str, Any]:
        # Deliberately no `default`: a bundle deploy must fail until the target
        # value is supplied, rather than silently reusing a source ID.
        return {"description": self.description}


@dataclass
class GeneratedBundle:
    files: Dict[str, str] = field(default_factory=dict)
    variables: Dict[str, BundleVariable] = field(default_factory=dict)
    review: List[Tuple[str, str]] = field(default_factory=list)
    resource_counts: Dict[str, int] = field(default_factory=dict)

    def needs_review(self) -> bool:
        return bool(self.review)


def variable_name(kind: str, source_value: str) -> str:
    """A stable, readable variable name derived from the source ID.

    Stable matters: regenerating the bundle after a re-collection must produce
    the same names, or every regeneration is an unreviewable diff.
    """
    slug = re.sub(r"[^A-Za-z0-9]+", "_", str(source_value)).strip("_").lower()
    return "{0}_{1}".format(kind, slug or "unnamed")


def _strip_and_rewrite(
    value: Any,
    rewriter: Optional[Rewriter],
    variables: Dict[str, BundleVariable],
) -> Any:
    """Recursively clean one API payload into bundle-shaped configuration."""
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, item in value.items():
            if key in SERVER_OWNED_FIELDS:
                continue
            if key in VARIABLE_FIELDS and isinstance(item, str) and item:
                prefix, label = VARIABLE_FIELDS[key]
                name = variable_name(prefix, item)
                variables[name] = BundleVariable(
                    name=name,
                    description="Target {0} replacing source value {1}".format(label, item),
                    source_value=item,
                )
                out[key] = "${var." + name + "}"
                continue
            if (
                key in CATALOG_NAME_FIELDS
                and isinstance(item, str)
                and rewriter is not None
                and item in rewriter.catalog_map
            ):
                out[key] = rewriter.catalog_map[item]
                continue
            if key == "init_scripts" and isinstance(item, list):
                out[key] = [
                    _rewrite_init_script(entry, rewriter, variables) for entry in item
                ]
                continue
            cleaned = _strip_and_rewrite(item, rewriter, variables)
            if cleaned is not None:
                out[key] = cleaned
        return out
    if isinstance(value, list):
        return [_strip_and_rewrite(v, rewriter, variables) for v in value]
    if isinstance(value, str) and rewriter is not None:
        return rewriter.rewrite_sql(value).value
    return value


def _rewrite_init_script(
    entry: Any,
    rewriter: Optional[Rewriter],
    variables: Dict[str, BundleVariable],
) -> Any:
    """Rewrite an init-script location, including its scheme key.

    ``{"abfss": {"destination": "abfss://..."}}`` rewritten to a GCS path must
    become ``{"gcs": {...}}``. Keeping the original key leaves a config that
    validates and resolves to nothing, which surfaces as a cluster that will not
    start long after the bundle was reviewed and approved.
    """
    if not isinstance(entry, dict) or len(entry) != 1:
        return _strip_and_rewrite(entry, rewriter, variables)
    (source_key, holder), = entry.items()
    if not isinstance(holder, dict) or "destination" not in holder:
        return _strip_and_rewrite(entry, rewriter, variables)
    destination = str(holder.get("destination") or "")
    rewritten = rewriter.rewrite_uri(destination).value if rewriter else destination
    scheme = rewritten.split("://", 1)[0].lower() if "://" in rewritten else ""
    if rewritten.startswith("/Volumes/"):
        target_key = "volumes"
    elif rewritten.startswith("/Workspace/"):
        target_key = "workspace"
    else:
        target_key = SCHEME_TO_INIT_KEY.get(scheme, source_key)
    return {target_key: {"destination": rewritten}}


def job_resource(
    row: Dict[str, Any],
    rewriter: Optional[Rewriter],
    variables: Dict[str, BundleVariable],
    pause_schedules: bool = True,
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """Return ``(resource_key, resource_body, review_reason)`` for one job.

    A job collected with ``--raw`` reproduces faithfully. Without it the
    inventory holds only the fields chosen for human review, which is not
    enough to recreate the job — so it is sent to review rather than guessed at.
    """
    name = str(row.get("name") or "").strip()
    key = _resource_key(name or str(row.get("job_id", "job")))
    raw = row.get("raw") or {}
    settings = raw.get("settings") if isinstance(raw, dict) else None
    if not settings:
        return (
            None,
            None,
            "job '{0}' was collected without --raw, so its tasks are not available; "
            "re-run `dbxmig workspace --raw` or port it by hand".format(name),
        )
    body = _strip_and_rewrite(settings, rewriter, variables)
    body.setdefault("name", name)
    if pause_schedules and isinstance(body.get("schedule"), dict):
        body["schedule"]["pause_status"] = "PAUSED"
    if pause_schedules and isinstance(body.get("trigger"), dict):
        body["trigger"]["pause_status"] = "PAUSED"
    return key, body, None


def pipeline_resource(
    row: Dict[str, Any],
    rewriter: Optional[Rewriter],
    variables: Dict[str, BundleVariable],
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    name = str(row.get("name") or "").strip()
    key = _resource_key(name or str(row.get("pipeline_id", "pipeline")))
    raw = row.get("raw") or {}
    spec = raw.get("spec") if isinstance(raw, dict) else None
    if not spec:
        return (
            None,
            None,
            "pipeline '{0}' was collected without --raw; its libraries and "
            "configuration are not available".format(name),
        )
    body = _strip_and_rewrite(spec, rewriter, variables)
    body.setdefault("name", name)
    # A pipeline's target catalog follows the catalog rename like any other
    # reference; the rewriter has already applied it to string fields.
    return key, body, None


def simple_resource(
    row: Dict[str, Any],
    fields: Sequence[str],
    rewriter: Optional[Rewriter],
    variables: Dict[str, BundleVariable],
    renames: Optional[Dict[str, str]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Build a bundle resource from selected flattened fields.

    Warehouses, cluster policies, and instance pools do not need the full raw
    payload: their bundle shape is small and the flattened inventory already
    holds every field that matters. Emitting them matters because they are the
    objects everything else depends on -- a job bundle that references
    ``${var.policy_x}`` is only deployable once the policy itself exists.
    """
    renames = renames or {}
    body: Dict[str, Any] = {}
    for source_field in fields:
        value = row.get(source_field)
        if value in (None, "", 0, [], {}):
            continue
        # Route through the dict form so the key-based rules apply: an
        # instance pool's node_type_id is as cloud-specific as a cluster's and
        # must not survive into the target as a literal.
        cleaned = _strip_and_rewrite({source_field: value}, rewriter, variables)
        if source_field not in cleaned:
            continue
        target_field = renames.get(source_field, source_field)
        body[target_field] = cleaned[source_field]
    if "channel" in body and isinstance(body["channel"], str):
        # A warehouse channel is a nested object in bundle configuration, not
        # the bare enum the API returns.
        body["channel"] = {"name": body["channel"]}
    return _resource_key(str(row.get("name") or "unnamed")), body


#: Bundle resource shapes for the objects everything else depends on. The
#: field lists are deliberately short: anything the target should choose for
#: itself (ids, state, current size) is left out rather than carried over.
SIMPLE_RESOURCES = {
    "sql_warehouses": (
        "sql_warehouses",
        ("name", "cluster_size", "min_clusters", "max_clusters", "auto_stop_mins", "channel"),
        {"min_clusters": "min_num_clusters", "max_clusters": "max_num_clusters"},
    ),
    "cluster_policies": (
        "cluster_policies",
        ("name", "definition", "max_clusters_per_user"),
        {},
    ),
    "instance_pools": (
        "instance_pools",
        ("name", "node_type_id", "min_idle_instances", "max_capacity"),
        {"name": "instance_pool_name"},
    ),
}


def _resource_key(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
    return slug or "unnamed"


def _yaml(payload: Any) -> str:
    try:
        import yaml  # type: ignore import-not-found
    except ImportError:  # pragma: no cover - PyYAML is a declared dependency
        raise RuntimeError("PyYAML is required to emit bundle YAML") from None
    return yaml.safe_dump(payload, sort_keys=False, default_flow_style=False, width=100)


def generate_bundle(
    inventory: WorkspaceInventory,
    bundle_name: str = "migrated-estate",
    target_name: str = "target",
    target_host: str = "",
    rewriter: Optional[Rewriter] = None,
    include: Sequence[str] = (
        "jobs",
        "pipelines",
        "sql_warehouses",
        "cluster_policies",
        "instance_pools",
    ),
    pause_schedules: bool = True,
    streaming_report: Optional[StreamingReport] = None,
) -> GeneratedBundle:
    """Build the full set of bundle files from a workspace inventory."""
    result = GeneratedBundle()
    variables: Dict[str, BundleVariable] = {}

    if "jobs" in include:
        jobs: Dict[str, Any] = {}
        for row in inventory.rows("jobs"):
            key, body, reason = job_resource(row, rewriter, variables, pause_schedules)
            if reason:
                result.review.append(("job", reason))
                continue
            if key and body is not None:
                jobs[_unique(jobs, key)] = body
        if jobs:
            result.files["resources/jobs.yml"] = _yaml({"resources": {"jobs": jobs}})
        result.resource_counts["jobs"] = len(jobs)

    if "pipelines" in include:
        pipelines: Dict[str, Any] = {}
        for row in inventory.rows("pipelines"):
            key, body, reason = pipeline_resource(row, rewriter, variables)
            if reason:
                result.review.append(("pipeline", reason))
                continue
            if key and body is not None:
                pipelines[_unique(pipelines, key)] = body
        if pipelines:
            result.files["resources/pipelines.yml"] = _yaml(
                {"resources": {"pipelines": pipelines}}
            )
        result.resource_counts["pipelines"] = len(pipelines)

    for asset_class, (resource_type, fields, renames) in sorted(SIMPLE_RESOURCES.items()):
        if asset_class not in include:
            continue
        resources: Dict[str, Any] = {}
        for row in inventory.rows(asset_class):
            key, body = simple_resource(row, fields, rewriter, variables, renames)
            if body:
                resources[_unique(resources, key)] = body
        if resources:
            result.files["resources/{0}.yml".format(asset_class)] = _yaml(
                {"resources": {resource_type: resources}}
            )
        result.resource_counts[asset_class] = len(resources)

    result.variables = variables
    root: Dict[str, Any] = {
        "bundle": {"name": bundle_name},
        "include": sorted(result.files),
    }
    if variables:
        root["variables"] = {name: variables[name].to_dict() for name in sorted(variables)}
    workspace_block: Dict[str, Any] = {
        "root_path": "/Shared/.bundle/${bundle.name}/${bundle.target}"
    }
    if target_host:
        workspace_block["host"] = target_host
    root["targets"] = {target_name: {"mode": "production", "workspace": workspace_block}}
    result.files["databricks.yml"] = _yaml(root)

    result.files["REVIEW.md"] = _review_markdown(result, inventory, streaming_report)
    return result


def _unique(existing: Dict[str, Any], key: str) -> str:
    """Two jobs may legitimately share a name; bundle keys may not."""
    if key not in existing:
        return key
    index = 2
    while "{0}_{1}".format(key, index) in existing:
        index += 1
    return "{0}_{1}".format(key, index)


def _review_markdown(
    result: GeneratedBundle,
    inventory: WorkspaceInventory,
    streaming_report: Optional[StreamingReport] = None,
) -> str:
    lines = [
        "# Bundle review",
        "",
        "Generated by `dbxmig bundle`. **This is a starting point, not a deliverable.**",
        "Diff every resource against the source definition before deploying.",
        "",
        "## Generated",
        "",
    ]
    for kind, count in sorted(result.resource_counts.items()):
        total = len(inventory.rows(kind))
        lines.append("- {0}: {1} of {2} collected".format(kind, count, total))

    lines.extend(
        [
            "",
            "## Variables you must supply",
            "",
            "Each of these is a workspace-scoped id that differs in the target. They are",
            "declared with no default, so `databricks bundle deploy` fails until you set",
            "them — a deliberate choice, because a silently wrong id is worse than a",
            "failed deploy.",
            "",
        ]
    )
    if result.variables:
        lines.append("| Variable | Source id | What it is |")
        lines.append("|---|---|---|")
        for name in sorted(result.variables):
            variable = result.variables[name]
            lines.append(
                "| `{0}` | `{1}` | {2} |".format(name, variable.source_value, variable.description)
            )
        lines.extend(
            [
                "",
                "```bash",
                "databricks bundle deploy -t target \\",
            ]
        )
        for name in sorted(result.variables):
            lines.append("  --var=\"{0}=<target-value>\" \\".format(name))
        lines.append("```")
    else:
        lines.append("_none_")

    lines.extend(["", "## Not generated — port these by hand", ""])
    if result.review:
        lines.append("| Kind | Reason |")
        lines.append("|---|---|")
        for kind, reason in result.review:
            lines.append("| {0} | {1} |".format(kind, reason))
    else:
        lines.append("_none_")

    if streaming_report is not None and streaming_report.assets:
        lines.extend(["", "## Streaming and event-driven assets", ""])
        lines.append("| Kind | Name | Source | Migration strategy |")
        lines.append("|---|---|---|---|")
        for asset in streaming_report.assets:
            strategy = asset.migration_strategy or "**NEEDS DECISION**"
            lines.append(
                "| {0} | {1} | {2} | {3} |".format(
                    asset.kind, asset.name, asset.source_type or "-", strategy
                )
            )

    lines.extend(
        [
            "",
            "## Always check by hand",
            "",
            "The bundle carries configuration. It does not carry:",
            "",
            "- **Permissions.** Job, pipeline, warehouse, policy, and pool ACLs are a",
            "  separate system; replay them from the object-ACL inventory.",
            "- **Deploy order.** Policies, pools, and warehouses must exist before the jobs",
            "  that reference them, and their target ids are what the variables above",
            "  expect. Deploy the dependency resources first, read back their new ids,",
            "  then deploy the jobs with those values.",
            "- **Secrets.** Scopes and values must exist in the target before first run.",
            "- **Schedules.** Every generated job is emitted with `pause_status: PAUSED`,",
            "  because otherwise the whole estate starts firing the moment the bundle",
            "  deploys. Un-pause deliberately, per wave. (`--no-pause` disables this.)",
            "- **Run history.** Recreated jobs start empty; see *what does not migrate*.",
        ]
    )
    return "\n".join(lines) + "\n"
