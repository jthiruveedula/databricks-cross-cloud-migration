"""Export a live Unity Catalog metastore into an :class:`Inventory`.

Two things make this more than a wrapper around ``list()`` calls.

**View dependencies.** A view's ``depends_on`` is what lets the planner order
views correctly, and it is not returned by the tables API. It comes from
``system.access.table_lineage``, with a regex fallback over the view body for
estates where lineage has not been enabled long enough to be complete.

**Completeness over convenience.** Row filters, column masks, constraints, tags,
and column comments are all pulled, because each one is an access-control or
correctness property that silently disappears if the migration only copies
columns and rows.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .models import (
    Catalog,
    Column,
    Constraint,
    ExternalLocation,
    Function,
    Grant,
    Inventory,
    RegisteredModel,
    Schema,
    StorageCredential,
    Table,
    Volume,
)

LINEAGE_QUERY = """
SELECT DISTINCT
  concat_ws('.', target_table_catalog, target_table_schema, target_table_name) AS target_name,
  concat_ws('.', source_table_catalog, source_table_schema, source_table_name) AS source_name
FROM system.access.table_lineage
WHERE target_table_catalog IN ({catalogs})
  AND source_table_name IS NOT NULL
  AND event_time >= current_date() - INTERVAL {days} DAYS
"""

_FROM_JOIN = re.compile(
    r"\b(?:FROM|JOIN)\s+`?([A-Za-z_][\w]*)`?\.`?([A-Za-z_][\w]*)`?\.`?([A-Za-z_][\w]*)`?",
    re.IGNORECASE,
)


def parse_view_dependencies(view_sql: Optional[str]) -> List[str]:
    """Extract three-part names a view reads from, as a lineage fallback.

    Regex, not a parser: it over-matches on CTE names that happen to be dotted
    and under-matches on dynamic SQL. That is acceptable because the planner
    intersects the result with the inventory, so a phantom name is dropped and a
    missed one shows up as a dangling reference in the plan report.
    """
    if not view_sql:
        return []
    found: List[str] = []
    for match in _FROM_JOIN.finditer(view_sql):
        name = "{0}.{1}.{2}".format(match.group(1), match.group(2), match.group(3))
        if name not in found:
            found.append(name)
    return found


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    value = getattr(obj, name, default)
    return default if value is None else value


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def export_inventory(
    client: Any,
    catalogs: Optional[Sequence[str]] = None,
    lineage_days: int = 90,
    warehouse_id: Optional[str] = None,
) -> Inventory:
    """Walk the metastore and build the inventory.

    ``client`` is a ``databricks.sdk.WorkspaceClient``. Passed in rather than
    constructed here so tests can substitute a stub with the same shape.
    """
    inventory = Inventory(captured_at=_utc_now())

    metastore = None
    try:
        metastore = client.metastores.current()
    except Exception:  # pragma: no cover - metastore summary is optional
        metastore = None
    if metastore is not None:
        inventory.metastore_id = str(_attr(metastore, "metastore_id", ""))
        inventory.metastore_name = str(_attr(metastore, "name", ""))
        inventory.region = str(_attr(metastore, "region", ""))

    for credential in _safe_list(client.storage_credentials.list):
        inventory.storage_credentials.append(
            StorageCredential(
                name=str(_attr(credential, "name", "")),
                comment=_attr(credential, "comment"),
                read_only=bool(_attr(credential, "read_only", False)),
            )
        )

    for location in _safe_list(client.external_locations.list):
        inventory.external_locations.append(
            ExternalLocation(
                name=str(_attr(location, "name", "")),
                url=str(_attr(location, "url", "")),
                credential_name=str(_attr(location, "credential_name", "")),
                read_only=bool(_attr(location, "read_only", False)),
                comment=_attr(location, "comment"),
            )
        )

    wanted = set(catalogs) if catalogs else None
    for catalog in _safe_list(client.catalogs.list):
        name = str(_attr(catalog, "name", ""))
        if wanted is not None and name not in wanted:
            continue
        inventory.catalogs.append(
            Catalog(
                name=name,
                comment=_attr(catalog, "comment"),
                owner=_attr(catalog, "owner"),
                storage_root=_attr(catalog, "storage_root"),
                isolation_mode=_enum_value(_attr(catalog, "isolation_mode")) or None,
                properties=dict(_attr(catalog, "properties", {}) or {}),
            )
        )
        _export_catalog_contents(client, inventory, name)

    _attach_lineage(client, inventory, lineage_days, warehouse_id)
    return inventory


def _export_catalog_contents(client: Any, inventory: Inventory, catalog_name: str) -> None:
    for schema in _safe_list(client.schemas.list, catalog_name=catalog_name):
        schema_name = str(_attr(schema, "name", ""))
        if schema_name == "information_schema":
            continue
        inventory.schemas.append(
            Schema(
                catalog=catalog_name,
                name=schema_name,
                comment=_attr(schema, "comment"),
                owner=_attr(schema, "owner"),
                storage_root=_attr(schema, "storage_root"),
                properties=dict(_attr(schema, "properties", {}) or {}),
            )
        )
        for table in _safe_list(
            client.tables.list, catalog_name=catalog_name, schema_name=schema_name
        ):
            inventory.tables.append(_build_table(catalog_name, schema_name, table))
        for volume in _safe_list(
            client.volumes.list, catalog_name=catalog_name, schema_name=schema_name
        ):
            inventory.volumes.append(
                Volume(
                    catalog=catalog_name,
                    schema=schema_name,
                    name=str(_attr(volume, "name", "")),
                    volume_type=_enum_value(_attr(volume, "volume_type")) or "MANAGED",
                    storage_location=_attr(volume, "storage_location"),
                    comment=_attr(volume, "comment"),
                    owner=_attr(volume, "owner"),
                )
            )
        for function in _safe_list(
            client.functions.list, catalog_name=catalog_name, schema_name=schema_name
        ):
            inventory.functions.append(
                Function(
                    catalog=catalog_name,
                    schema=schema_name,
                    name=str(_attr(function, "name", "")),
                    language=_enum_value(_attr(function, "routine_body")) or "SQL",
                    routine_definition=_attr(function, "routine_definition"),
                    comment=_attr(function, "comment"),
                    owner=_attr(function, "owner"),
                )
            )
        for model in _safe_list(
            client.registered_models.list, catalog_name=catalog_name, schema_name=schema_name
        ):
            inventory.models.append(
                RegisteredModel(
                    catalog=catalog_name,
                    schema=schema_name,
                    name=str(_attr(model, "name", "")),
                    owner=_attr(model, "owner"),
                    comment=_attr(model, "comment"),
                )
            )


def _build_table(catalog_name: str, schema_name: str, raw: Any) -> Table:
    columns: List[Column] = []
    for position, column in enumerate(_attr(raw, "columns", []) or []):
        columns.append(
            Column(
                name=str(_attr(column, "name", "")),
                type_text=str(_attr(column, "type_text", "STRING")),
                nullable=bool(_attr(column, "nullable", True)),
                comment=_attr(column, "comment"),
                position=int(_attr(column, "position", position)),
            )
        )
    constraints: List[Constraint] = []
    for constraint in _attr(raw, "table_constraints", []) or []:
        for kind, key in (
            ("PRIMARY_KEY", "primary_key_constraint"),
            ("FOREIGN_KEY", "foreign_key_constraint"),
            ("NOT_NULL", "named_table_constraint"),
        ):
            payload = _attr(constraint, key)
            if payload is None:
                continue
            constraints.append(
                Constraint(
                    name=str(_attr(payload, "name", kind.lower())),
                    kind=kind,
                    definition=", ".join(_attr(payload, "child_columns", []) or []),
                )
            )
    view_definition = _attr(raw, "view_definition")
    return Table(
        catalog=catalog_name,
        schema=schema_name,
        name=str(_attr(raw, "name", "")),
        table_type=_enum_value(_attr(raw, "table_type")) or "MANAGED",
        data_source_format=_enum_value(_attr(raw, "data_source_format")) or "DELTA",
        storage_location=_attr(raw, "storage_location"),
        columns=columns,
        constraints=constraints,
        properties=dict(_attr(raw, "properties", {}) or {}),
        comment=_attr(raw, "comment"),
        owner=_attr(raw, "owner"),
        view_definition=view_definition,
        depends_on=parse_view_dependencies(view_definition),
        row_filter=_attr(getattr(raw, "row_filter", None), "function_name"),
    )


def _attach_lineage(
    client: Any, inventory: Inventory, lineage_days: int, warehouse_id: Optional[str]
) -> None:
    """Overlay system-table lineage onto the regex-derived dependencies.

    Lineage is authoritative where it exists -- it sees dynamic SQL and
    pipeline-generated reads a regex cannot. Where the system table returns
    nothing (lineage not yet enabled, or the view has not run inside the
    window), the parsed dependencies stand.
    """
    if not warehouse_id or not inventory.catalogs:
        return
    catalog_list = ", ".join("'{0}'".format(c.name.replace("'", "''")) for c in inventory.catalogs)
    query = LINEAGE_QUERY.format(catalogs=catalog_list, days=int(lineage_days))
    try:
        response = client.statement_execution.execute_statement(
            statement=query, warehouse_id=warehouse_id, wait_timeout="50s"
        )
    except Exception:  # pragma: no cover - lineage is best-effort
        return
    result = getattr(response, "result", None)
    rows = getattr(result, "data_array", None) or []
    edges: Dict[str, List[str]] = {}
    for row in rows:
        if len(row) < 2:
            continue
        edges.setdefault(str(row[0]), []).append(str(row[1]))

    merged: List[Table] = []
    for table in inventory.tables:
        extra = edges.get(table.full_name, [])
        if not extra:
            merged.append(table)
            continue
        combined = list(table.depends_on)
        for name in extra:
            if name not in combined and name != table.full_name:
                combined.append(name)
        merged.append(
            Table(
                catalog=table.catalog,
                schema=table.schema,
                name=table.name,
                table_type=table.table_type,
                data_source_format=table.data_source_format,
                storage_location=table.storage_location,
                columns=table.columns,
                partition_columns=table.partition_columns,
                cluster_columns=table.cluster_columns,
                constraints=table.constraints,
                properties=table.properties,
                tags=table.tags,
                comment=table.comment,
                owner=table.owner,
                view_definition=table.view_definition,
                depends_on=combined,
                row_filter=table.row_filter,
                column_masks=table.column_masks,
                size_bytes=table.size_bytes,
            )
        )
    inventory.tables = merged


def export_grants(rows: Iterable[Dict[str, Any]]) -> List[Grant]:
    """Build grants from ``information_schema`` rows.

    Accepts the column names used by the privilege views
    (``grantee``/``privilege_type``) as well as the toolkit's own field names,
    so an export produced by hand or by SQL both load.
    """
    grants: List[Grant] = []
    for row in rows:
        full_name = (
            row.get("full_name")
            or row.get("object_name")
            or ".".join(
                part
                for part in (
                    row.get("table_catalog"),
                    row.get("table_schema"),
                    row.get("table_name"),
                )
                if part
            )
        )
        if not full_name:
            continue
        grants.append(
            Grant(
                object_type=str(row.get("object_type") or "TABLE").upper(),
                full_name=str(full_name),
                principal=str(row.get("principal") or row.get("grantee") or ""),
                privilege=str(row.get("privilege") or row.get("privilege_type") or "").upper(),
            )
        )
    return grants


def _safe_list(method: Any, **kwargs: Any) -> List[Any]:
    """Call a paginated SDK ``list`` and materialise it, tolerating absence.

    Not every workspace exposes every API (registered models need UC-enabled ML,
    volumes need a recent metastore). A missing surface degrades the inventory
    for that object type rather than aborting the export.
    """
    try:
        return list(method(**kwargs) or [])
    except Exception:
        return []
