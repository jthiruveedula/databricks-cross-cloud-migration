"""Workspace-plane inventory: everything that is not in the metastore.

``models.py``/``inventory.py`` cover Unity Catalog. This module covers the other
half of a Databricks estate -- jobs, pipelines, clusters, policies, pools,
warehouses, dashboards, queries, alerts, secret scopes, repos, principals, and
the workspace object ACLs that are a separate permission system from UC grants.

Three design choices make this useful to a person rather than just complete:

* **Flat rows.** Every asset class flattens to a list of dicts with stable keys,
  so the same collector feeds a JSON manifest, a spreadsheet a project manager
  can filter, and the cross-reference scan below.
* **Zero is reported.** An asset class that returns nothing is recorded as
  ``collected: 0`` with the reason, because "we have no cluster policies" and
  "the token could not read cluster policies" look identical in a JSON file and
  mean very different things three weeks later.
* **Secret values are never read.** Scope and key *names* are inventoried, and
  nothing here calls the get-secret API. Note that this is a deliberate choice
  rather than a limitation: for a Databricks-backed scope a caller with READ
  *can* retrieve values. A collector that hoovers up every production
  credential is not something to point at an estate, so it does not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

#: Asset classes collected, in the order a discovery phase usually needs them.
#: The order matters for the printed summary, not for correctness.
ASSET_CLASSES = (
    "jobs",
    "pipelines",
    "clusters",
    "cluster_policies",
    "instance_pools",
    "sql_warehouses",
    "dashboards",
    "queries",
    "alerts",
    "secret_scopes",
    "repos",
    "groups",
    "service_principals",
    "object_acls",
    # Surfaces that postdate a table-and-job-shaped estate. Collected last
    # because they are the ones most often absent -- and an absence has to be
    # distinguishable from "we never looked".
    "apps",
    "genie_spaces",
    "vector_search_endpoints",
    "vector_search_indexes",
    "usage_policies",
    "database_instances",
    "shares",
    "recipients",
    "providers",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    value = getattr(obj, name, default)
    return default if value is None else value


def _enum(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


class _ApiUnavailable(RuntimeError):
    """The SDK or workspace does not expose this API at all."""


def _api(client: Any, path: str) -> Any:
    """Resolve ``client.a.b``, or raise :class:`_ApiUnavailable`.

    Newer surfaces move and get renamed. An older SDK, or a workspace without
    the feature enabled, should degrade to "not checked" rather than to a
    failure that looks like a permissions problem.
    """
    node = client
    for part in path.split("."):
        node = getattr(node, part, None)
        if node is None:
            raise _ApiUnavailable("client.{0} is not present".format(path))
    return node


@dataclass
class CollectionResult:
    """What one asset class collection actually did.

    ``ok=False`` with a reason is the difference between an empty estate and a
    permission problem -- the distinction that decides whether discovery is
    finished.
    """

    asset_class: str
    collected: int = 0
    ok: bool = True
    reason: str = ""
    #: True when the API is not present in this SDK version or not enabled on
    #: this workspace. Distinct from both "empty" and "failed": there is
    #: nothing wrong, but the class has NOT been checked and must be verified
    #: by hand before discovery is signed off.
    unavailable: bool = False


@dataclass
class WorkspaceInventory:
    workspace_id: str = ""
    workspace_host: str = ""
    captured_at: str = ""
    assets: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    results: List[CollectionResult] = field(default_factory=list)

    def rows(self, asset_class: str) -> List[Dict[str, Any]]:
        return self.assets.get(asset_class, [])

    def counts(self) -> Dict[str, int]:
        return {name: len(self.assets.get(name, [])) for name in ASSET_CLASSES}

    def empty_classes(self) -> List[str]:
        """Asset classes with nothing in them -- each needs an explicit 'yes, really'."""
        return [name for name in ASSET_CLASSES if not self.assets.get(name)]

    def failed_classes(self) -> List[CollectionResult]:
        return [r for r in self.results if not r.ok]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "workspace_host": self.workspace_host,
            "captured_at": self.captured_at,
            "assets": {name: self.assets.get(name, []) for name in ASSET_CLASSES},
            "results": [
                {
                    "asset_class": r.asset_class,
                    "collected": r.collected,
                    "ok": r.ok,
                    "reason": r.reason,
                    "unavailable": r.unavailable,
                }
                for r in self.results
            ],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "WorkspaceInventory":
        inventory = cls(
            workspace_id=str(raw.get("workspace_id", "")),
            workspace_host=str(raw.get("workspace_host", "")),
            captured_at=str(raw.get("captured_at", "")),
            assets={k: list(v or []) for k, v in (raw.get("assets") or {}).items()},
        )
        for item in raw.get("results") or []:
            inventory.results.append(
                CollectionResult(
                    asset_class=str(item.get("asset_class", "")),
                    collected=int(item.get("collected", 0)),
                    ok=bool(item.get("ok", True)),
                    reason=str(item.get("reason", "")),
                    unavailable=bool(item.get("unavailable", False)),
                )
            )
        return inventory


def _collect(
    inventory: WorkspaceInventory,
    asset_class: str,
    fetch: Callable[[], List[Dict[str, Any]]],
) -> None:
    """Run one collector, recording success, emptiness, or failure explicitly."""
    try:
        rows = fetch()
    except _ApiUnavailable as exc:
        inventory.assets[asset_class] = []
        inventory.results.append(
            CollectionResult(
                asset_class,
                0,
                ok=True,
                reason="API not available here ({0}) -- check this class by hand".format(exc),
                unavailable=True,
            )
        )
        return
    except Exception as exc:  # noqa: BLE001 - the reason must reach the report
        inventory.assets[asset_class] = []
        inventory.results.append(
            CollectionResult(asset_class, 0, ok=False, reason=type(exc).__name__ + ": " + str(exc))
        )
        return
    inventory.assets[asset_class] = rows
    reason = "" if rows else "API returned no rows -- confirm this is a genuinely empty class"
    inventory.results.append(CollectionResult(asset_class, len(rows), ok=True, reason=reason))


# ---- per-asset-class flatteners -----------------------------------------
#
# Each returns the fields worth keeping for a migration, not the whole API
# response. The selection is deliberate: every field below is either an
# identifier you need to re-create the object, or a dependency that decides
# which wave it belongs to.


def _as_payload(raw: Any) -> Dict[str, Any]:
    """The object's own dict form, when the SDK offers one.

    Kept alongside the flattened row so bundle generation can be faithful.
    The flattened fields are for humans and spreadsheets; this is for machines
    that have to recreate the object exactly.
    """
    for method in ("as_dict", "as_shallow_dict"):
        fn = getattr(raw, method, None)
        if callable(fn):
            try:
                value = fn()
            except Exception:
                continue
            if isinstance(value, dict):
                return value
    return {}


def flatten_job(raw: Any, include_raw: bool = False) -> Dict[str, Any]:
    settings = _attr(raw, "settings")
    tasks = _attr(settings, "tasks", []) or []
    schedule = _attr(settings, "schedule")
    job_clusters = _attr(settings, "job_clusters", []) or []
    policy_ids = sorted(
        {
            str(_attr(_attr(jc, "new_cluster"), "policy_id", ""))
            for jc in job_clusters
            if _attr(_attr(jc, "new_cluster"), "policy_id", "")
        }
    )
    warehouse_ids = sorted(
        {
            str(_attr(_attr(t, "sql_task"), "warehouse_id", ""))
            for t in tasks
            if _attr(_attr(t, "sql_task"), "warehouse_id", "")
        }
    )
    notebook_paths = sorted(
        {
            str(_attr(_attr(t, "notebook_task"), "notebook_path", ""))
            for t in tasks
            if _attr(_attr(t, "notebook_task"), "notebook_path", "")
        }
    )
    return {
        "job_id": str(_attr(raw, "job_id", "")),
        "name": str(_attr(settings, "name", "")),
        "creator": str(_attr(raw, "creator_user_name", "")),
        "run_as": str(_attr(settings, "run_as_user_name", "")),
        "task_count": len(tasks),
        "schedule": str(_attr(schedule, "quartz_cron_expression", "")),
        "paused": _enum(_attr(schedule, "pause_status")) == "PAUSED",
        "cluster_policy_ids": policy_ids,
        "warehouse_ids": warehouse_ids,
        "notebook_paths": notebook_paths,
        "tags": dict(_attr(settings, "tags", {}) or {}),
        "raw": _as_payload(raw) if include_raw else {},
    }


def flatten_pipeline(raw: Any, include_raw: bool = False) -> Dict[str, Any]:
    spec = _attr(raw, "spec")
    return {
        "pipeline_id": str(_attr(raw, "pipeline_id", "")),
        "name": str(_attr(raw, "name", "")),
        "state": _enum(_attr(raw, "state")),
        "catalog": str(_attr(spec, "catalog", "")),
        "target": str(_attr(spec, "target", "")),
        "storage": str(_attr(spec, "storage", "")),
        "serverless": bool(_attr(spec, "serverless", False)),
        "continuous": bool(_attr(spec, "continuous", False)),
        "raw": _as_payload(raw) if include_raw else {},
    }


def flatten_cluster(raw: Any) -> Dict[str, Any]:
    init_scripts = []
    for script in _attr(raw, "init_scripts", []) or []:
        for kind in ("workspace", "volumes", "s3", "abfss", "gcs", "dbfs"):
            holder = _attr(script, kind)
            if holder is not None:
                init_scripts.append(str(_attr(holder, "destination", "")))
    aws = _attr(raw, "aws_attributes")
    return {
        "cluster_id": str(_attr(raw, "cluster_id", "")),
        "name": str(_attr(raw, "cluster_name", "")),
        "creator": str(_attr(raw, "creator_user_name", "")),
        "spark_version": str(_attr(raw, "spark_version", "")),
        "node_type_id": str(_attr(raw, "node_type_id", "")),
        "driver_node_type_id": str(_attr(raw, "driver_node_type_id", "")),
        "num_workers": int(_attr(raw, "num_workers", 0) or 0),
        "autoscale_max": int(_attr(_attr(raw, "autoscale"), "max_workers", 0) or 0),
        "data_security_mode": _enum(_attr(raw, "data_security_mode")),
        "policy_id": str(_attr(raw, "policy_id", "")),
        "instance_pool_id": str(_attr(raw, "instance_pool_id", "")),
        "instance_profile_arn": str(_attr(aws, "instance_profile_arn", "")),
        "init_scripts": [s for s in init_scripts if s],
        "spark_conf": dict(_attr(raw, "spark_conf", {}) or {}),
        "custom_tags": dict(_attr(raw, "custom_tags", {}) or {}),
    }


def flatten_policy(raw: Any) -> Dict[str, Any]:
    return {
        "policy_id": str(_attr(raw, "policy_id", "")),
        "name": str(_attr(raw, "name", "")),
        "definition": str(_attr(raw, "definition", "")),
        "max_clusters_per_user": int(_attr(raw, "max_clusters_per_user", 0) or 0),
    }


def flatten_pool(raw: Any) -> Dict[str, Any]:
    return {
        "instance_pool_id": str(_attr(raw, "instance_pool_id", "")),
        "name": str(_attr(raw, "instance_pool_name", "")),
        "node_type_id": str(_attr(raw, "node_type_id", "")),
        "min_idle_instances": int(_attr(raw, "min_idle_instances", 0) or 0),
        "max_capacity": int(_attr(raw, "max_capacity", 0) or 0),
    }


def flatten_warehouse(raw: Any) -> Dict[str, Any]:
    return {
        "warehouse_id": str(_attr(raw, "id", "")),
        "name": str(_attr(raw, "name", "")),
        "cluster_size": str(_attr(raw, "cluster_size", "")),
        "warehouse_type": _enum(_attr(raw, "warehouse_type")),
        "enable_serverless": bool(_attr(raw, "enable_serverless_compute", False)),
        "min_clusters": int(_attr(raw, "min_num_clusters", 0) or 0),
        "max_clusters": int(_attr(raw, "max_num_clusters", 0) or 0),
        "auto_stop_mins": int(_attr(raw, "auto_stop_mins", 0) or 0),
        "channel": _enum(_attr(_attr(raw, "channel"), "name")),
    }


def flatten_dashboard(raw: Any) -> Dict[str, Any]:
    return {
        "dashboard_id": str(_attr(raw, "dashboard_id", "") or _attr(raw, "id", "")),
        "name": str(_attr(raw, "display_name", "") or _attr(raw, "name", "")),
        "warehouse_id": str(_attr(raw, "warehouse_id", "")),
        "path": str(_attr(raw, "path", "")),
        "lifecycle_state": _enum(_attr(raw, "lifecycle_state")),
    }


def flatten_query(raw: Any) -> Dict[str, Any]:
    return {
        "query_id": str(_attr(raw, "id", "")),
        "name": str(_attr(raw, "display_name", "") or _attr(raw, "name", "")),
        "warehouse_id": str(_attr(raw, "warehouse_id", "")),
        "owner": str(_attr(raw, "owner_user_name", "")),
        "query_text": str(_attr(raw, "query_text", "")),
    }


def flatten_alert(raw: Any) -> Dict[str, Any]:
    return {
        "alert_id": str(_attr(raw, "id", "")),
        "name": str(_attr(raw, "display_name", "") or _attr(raw, "name", "")),
        "query_id": str(_attr(raw, "query_id", "")),
        "owner": str(_attr(raw, "owner_user_name", "")),
    }


def flatten_repo(raw: Any) -> Dict[str, Any]:
    return {
        "repo_id": str(_attr(raw, "id", "")),
        "path": str(_attr(raw, "path", "")),
        "url": str(_attr(raw, "url", "")),
        "provider": str(_attr(raw, "provider", "")),
        "branch": str(_attr(raw, "branch", "")),
    }


def flatten_group(raw: Any) -> Dict[str, Any]:
    members = _attr(raw, "members", []) or []
    return {
        "group_id": str(_attr(raw, "id", "")),
        "display_name": str(_attr(raw, "display_name", "")),
        "member_count": len(members),
        # Workspace-local groups must become account-level groups before Unity
        # Catalog grants behave correctly, so the distinction is inventoried.
        "meta_resource_type": str(_attr(_attr(raw, "meta"), "resource_type", "")),
    }


def flatten_service_principal(raw: Any) -> Dict[str, Any]:
    return {
        "application_id": str(_attr(raw, "application_id", "")),
        "display_name": str(_attr(raw, "display_name", "")),
        "active": bool(_attr(raw, "active", True)),
    }


# ---- collection ----------------------------------------------------------


def collect_workspace_inventory(
    client: Any,
    include_acls: bool = True,
    include_query_text: bool = True,
    include_raw: bool = False,
) -> WorkspaceInventory:
    """Walk the workspace APIs and build the inventory.

    ``client`` is a ``databricks.sdk.WorkspaceClient``. Passed in rather than
    constructed here so tests can substitute a stub of the same shape.
    """
    inventory = WorkspaceInventory(captured_at=_utc_now())
    inventory.workspace_host = str(getattr(getattr(client, "config", None), "host", "") or "")

    _collect(
        inventory,
        "jobs",
        lambda: [flatten_job(j, include_raw) for j in client.jobs.list(expand_tasks=True)],
    )
    _collect(
        inventory,
        "pipelines",
        lambda: [flatten_pipeline(p, include_raw) for p in client.pipelines.list_pipelines()],
    )
    _collect(inventory, "clusters", lambda: [flatten_cluster(c) for c in client.clusters.list()])
    _collect(
        inventory,
        "cluster_policies",
        lambda: [flatten_policy(p) for p in client.cluster_policies.list()],
    )
    _collect(
        inventory,
        "instance_pools",
        lambda: [flatten_pool(p) for p in client.instance_pools.list()],
    )
    _collect(
        inventory,
        "sql_warehouses",
        lambda: [flatten_warehouse(w) for w in client.warehouses.list()],
    )
    _collect(
        inventory, "dashboards", lambda: [flatten_dashboard(d) for d in client.lakeview.list()]
    )

    def _queries() -> List[Dict[str, Any]]:
        rows = [flatten_query(q) for q in client.queries.list()]
        if not include_query_text:
            for row in rows:
                row["query_text"] = ""
        return rows

    _collect(inventory, "queries", _queries)
    _collect(inventory, "alerts", lambda: [flatten_alert(a) for a in client.alerts.list()])
    _collect(inventory, "secret_scopes", lambda: _collect_secret_scopes(client))
    _collect(inventory, "repos", lambda: [flatten_repo(r) for r in client.repos.list()])
    _collect(inventory, "groups", lambda: [flatten_group(g) for g in client.groups.list()])
    _collect(
        inventory,
        "service_principals",
        lambda: [flatten_service_principal(s) for s in client.service_principals.list()],
    )

    _collect_newer_surfaces(client, inventory)

    if include_acls:
        _collect(inventory, "object_acls", lambda: _collect_object_acls(client, inventory))
    else:
        inventory.assets["object_acls"] = []
        inventory.results.append(
            CollectionResult("object_acls", 0, ok=True, reason="skipped: --no-acls")
        )
    return inventory


def _collect_newer_surfaces(client: Any, inventory: WorkspaceInventory) -> None:
    """Apps, Genie, AI Search, Lakebase, and Delta Sharing objects.

    Every one of these is invisible to an inventory shaped like a 2022 estate,
    and each degrades to "not checked" rather than to a failure when the API is
    absent -- so the report can say which of the three states applies.
    """
    _collect(
        inventory,
        "apps",
        lambda: [
            {
                "name": str(_attr(a, "name", "")),
                "description": str(_attr(a, "description", "")),
                "url": str(_attr(a, "url", "")),
                "service_principal_name": str(_attr(a, "service_principal_name", "")),
                "service_principal_id": str(_attr(a, "service_principal_id", "")),
                "state": _enum(_attr(_attr(a, "app_status"), "state")),
            }
            for a in _api(client, "apps").list()
        ],
    )

    _collect(
        inventory,
        "genie_spaces",
        lambda: [
            {
                "space_id": str(_attr(s, "space_id", "") or _attr(s, "id", "")),
                "title": str(_attr(s, "title", "") or _attr(s, "name", "")),
                "description": str(_attr(s, "description", "")),
                "warehouse_id": str(_attr(s, "warehouse_id", "")),
            }
            for s in _api(client, "genie").list_spaces()
        ],
    )

    _collect(
        inventory,
        "vector_search_endpoints",
        lambda: [
            {
                "name": str(_attr(e, "name", "")),
                "endpoint_type": _enum(_attr(e, "endpoint_type")),
                "endpoint_status": _enum(_attr(_attr(e, "endpoint_status"), "state")),
            }
            for e in _api(client, "vector_search_endpoints").list_endpoints()
        ],
    )

    def _indexes() -> List[Dict[str, Any]]:
        api = _api(client, "vector_search_indexes")
        rows: List[Dict[str, Any]] = []
        for endpoint in inventory.rows("vector_search_endpoints"):
            name = str(endpoint.get("name", ""))
            if not name:
                continue
            for index in api.list_indexes(endpoint_name=name) or []:
                index_type = _enum(_attr(index, "index_type"))
                rows.append(
                    {
                        "name": str(_attr(index, "name", "")),
                        "endpoint_name": name,
                        "index_type": index_type,
                        "primary_key": str(_attr(index, "primary_key", "")),
                        "source_table": str(
                            _attr(
                                _attr(index, "delta_sync_index_spec"),
                                "source_table",
                                "",
                            )
                        ),
                        # The distinction that decides whether losing this index
                        # is an inconvenience or data loss.
                        "rebuildable_from_source": index_type == "DELTA_SYNC",
                    }
                )
        return rows

    _collect(inventory, "vector_search_indexes", _indexes)

    _collect(
        inventory,
        "usage_policies",
        lambda: [
            {
                "policy_id": str(_attr(p, "policy_id", "")),
                "name": str(_attr(p, "policy_name", "") or _attr(p, "name", "")),
                # These tags are what lands in system.billing.usage.custom_tags,
                # so they are the cost-attribution contract, not decoration.
                "custom_tags": {
                    str(_attr(tag, "key", "")): str(_attr(tag, "value", ""))
                    for tag in (_attr(p, "custom_tags", []) or [])
                },
            }
            for p in _api(client, "budget_policy").list()
        ],
    )

    _collect(
        inventory,
        "database_instances",
        lambda: [
            {
                "name": str(_attr(d, "name", "")),
                "state": _enum(_attr(d, "state")),
                "capacity": str(_attr(d, "capacity", "")),
            }
            for d in _api(client, "database").list_database_instances()
        ],
    )

    _collect(
        inventory,
        "shares",
        lambda: [
            {
                "name": str(_attr(s, "name", "")),
                "owner": str(_attr(s, "owner", "")),
                "comment": str(_attr(s, "comment", "")),
            }
            for s in _api(client, "shares").list()
        ],
    )

    _collect(
        inventory,
        "recipients",
        lambda: [
            {
                "name": str(_attr(r, "name", "")),
                "authentication_type": _enum(_attr(r, "authentication_type")),
                "owner": str(_attr(r, "owner", "")),
                # Tokens are bound to the source metastore: every recipient
                # needs a new activation link, which is a conversation with an
                # organisation you do not control.
                "needs_reactivation": True,
            }
            for r in _api(client, "recipients").list()
        ],
    )

    _collect(
        inventory,
        "providers",
        lambda: [
            {
                "name": str(_attr(p, "name", "")),
                "authentication_type": _enum(_attr(p, "authentication_type")),
            }
            for p in _api(client, "providers").list()
        ],
    )


def _collect_secret_scopes(client: Any) -> List[Dict[str, Any]]:
    """Scope and key names only. Secret values are never read.

    ``get-secret`` is deliberately not called. For a Databricks-backed scope a
    caller with READ can retrieve values, so this restraint is a choice: the
    useful artifact is the dependency map -- which scope, which key, used by
    what -- so the target can be populated from whatever system of record
    issued the secret, rather than from a credential dump this tool created.
    """
    rows: List[Dict[str, Any]] = []
    for scope in client.secrets.list_scopes() or []:
        name = str(_attr(scope, "name", ""))
        try:
            keys = [str(_attr(k, "key", "")) for k in client.secrets.list_secrets(scope=name) or []]
        except Exception:
            keys = []
        rows.append(
            {
                "scope": name,
                "backend_type": _enum(_attr(scope, "backend_type")),
                "key_names": sorted(k for k in keys if k),
                "key_count": len(keys),
            }
        )
    return rows


#: Workspace object types whose ACLs are collected, mapped to the id field on
#: the already-flattened rows for that asset class.
ACL_TARGETS = (
    ("jobs", "jobs", "job_id"),
    ("clusters", "clusters", "cluster_id"),
    ("instance-pools", "instance_pools", "instance_pool_id"),
    ("sql/warehouses", "sql_warehouses", "warehouse_id"),
    ("pipelines", "pipelines", "pipeline_id"),
    ("cluster-policies", "cluster_policies", "policy_id"),
)


def _collect_object_acls(client: Any, inventory: WorkspaceInventory) -> List[Dict[str, Any]]:
    """Per-object permissions -- a separate system from Unity Catalog grants.

    Nothing in ``information_schema`` knows who may restart a cluster or edit a
    job. That lives here, it is not included in a workspace export, and its
    absence in the target surfaces weeks after cutover when a team discovers it
    cannot operate its own workloads.
    """
    rows: List[Dict[str, Any]] = []
    for api_type, asset_class, id_field in ACL_TARGETS:
        for asset in inventory.rows(asset_class):
            object_id = str(asset.get(id_field, ""))
            if not object_id:
                continue
            try:
                permissions = client.permissions.get(api_type, object_id)
            except Exception:
                continue
            for entry in _attr(permissions, "access_control_list", []) or []:
                principal = (
                    str(_attr(entry, "group_name", ""))
                    or str(_attr(entry, "user_name", ""))
                    or str(_attr(entry, "service_principal_name", ""))
                )
                for permission in _attr(entry, "all_permissions", []) or []:
                    if _attr(permission, "inherited", False):
                        continue
                    rows.append(
                        {
                            "object_type": api_type,
                            "object_id": object_id,
                            "object_name": str(asset.get("name", "")),
                            "principal": principal,
                            "permission_level": _enum(_attr(permission, "permission_level")),
                        }
                    )
    return rows


# ---- spreadsheet export --------------------------------------------------


def csv_rows(inventory: WorkspaceInventory, asset_class: str) -> List[List[str]]:
    """Header row plus data rows, list values joined so a cell stays a cell."""
    rows = inventory.rows(asset_class)
    if not rows:
        return []
    headers: List[str] = []
    for row in rows:
        for key in row:
            if key not in headers:
                headers.append(key)
    out = [headers]
    for row in rows:
        out.append([_cell(row.get(header)) for header in headers])
    return out


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return "; ".join(str(v) for v in value)
    if isinstance(value, dict):
        return "; ".join("{0}={1}".format(k, v) for k, v in sorted(value.items()))
    return str(value)


def owner_hint(asset_class: str) -> str:
    """Which role usually owns collecting and signing off this asset class.

    Included in the summary because "who is chasing this" is the question that
    actually stalls a discovery phase, not "what is the API".
    """
    return {
        "jobs": "Platform engineer + owning data team",
        "pipelines": "Data engineering",
        "clusters": "Platform engineer",
        "cluster_policies": "Platform engineer + FinOps",
        "instance_pools": "Platform engineer",
        "sql_warehouses": "Analytics engineering",
        "dashboards": "BI / analytics owner",
        "queries": "BI / analytics owner",
        "alerts": "BI / analytics owner",
        "secret_scopes": "Security engineer",
        "repos": "Developer / release engineer",
        "groups": "Identity / IAM owner",
        "service_principals": "Identity / IAM owner",
        "object_acls": "Platform engineer + security",
        "apps": "App owner + platform engineer",
        "genie_spaces": "Business/domain owner",
        "vector_search_endpoints": "ML engineering",
        "vector_search_indexes": "ML engineering",
        "usage_policies": "FinOps + platform engineer",
        "database_instances": "Application team",
        "shares": "Data product owner",
        "recipients": "Data product owner + partner manager",
        "providers": "Data product owner",
    }.get(asset_class, "Migration lead")
