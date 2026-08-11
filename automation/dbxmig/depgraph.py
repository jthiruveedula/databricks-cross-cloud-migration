"""Turn an inventory into a dependency-ordered, resumable migration plan.

Object order is not a style preference in Unity Catalog -- it is a hard
constraint. An external location cannot exist before its storage credential, a
table cannot exist before its schema, a view cannot compile before the tables it
reads, and a view built on another view needs that view first. Get the order
wrong and the failure surfaces as a permission error or a "table not found"
several steps later, which is why this module does the ordering once, up front,
instead of leaving it to whoever is running the migration at 2am.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set

from .models import (
    EXTERNAL,
    MANAGED,
    MATERIALIZED_VIEW,
    STREAMING_TABLE,
    VIEW,
    Inventory,
    Table,
)

# Execution tiers. Every object in tier N may depend only on tiers <= N.
TIER_STORAGE_CREDENTIAL = 10
TIER_EXTERNAL_LOCATION = 20
TIER_CATALOG = 30
TIER_SCHEMA = 40
TIER_VOLUME = 50
TIER_TABLE = 60
TIER_CONSTRAINT = 65
TIER_VIEW = 70
TIER_FUNCTION = 80
TIER_MODEL = 85
TIER_POLICY = 90  # row filters and column masks: after the objects they guard
TIER_GRANT = 95

# Strategies the planner assigns to a data-bearing object.
DEEP_CLONE = "DEEP_CLONE"
CTAS = "CTAS"
CREATE_VIEW = "CREATE_VIEW"
RECREATE_PIPELINE = "RECREATE_PIPELINE"
CREATE_OBJECT = "CREATE_OBJECT"
MANUAL = "MANUAL"


@dataclass(frozen=True)
class Step:
    """One unit of work, addressable by ``id`` so a run can resume mid-plan."""

    id: str
    tier: int
    action: str
    object_type: str
    source_name: str
    target_name: str
    strategy: str = CREATE_OBJECT
    depends_on: List[str] = field(default_factory=list)
    #: Set when the step cannot be executed automatically. A blocked step never
    #: silently disappears -- it lands in the plan, in the report, and in the
    #: exit code.
    blocked_reason: Optional[str] = None
    detail: Dict[str, str] = field(default_factory=dict)

    @property
    def blocked(self) -> bool:
        return self.blocked_reason is not None


@dataclass
class Plan:
    steps: List[Step] = field(default_factory=list)
    #: Objects referenced by something in the plan but absent from the
    #: inventory -- a view reading a table nobody exported, most often because
    #: the table lives in a catalog outside the migration scope.
    dangling_references: Dict[str, List[str]] = field(default_factory=dict)
    cycles: List[List[str]] = field(default_factory=list)

    @property
    def blocked_steps(self) -> List[Step]:
        return [s for s in self.steps if s.blocked]

    @property
    def executable_steps(self) -> List[Step]:
        return [s for s in self.steps if not s.blocked]

    def by_id(self) -> Dict[str, Step]:
        return {s.id: s for s in self.steps}

    def counts_by_strategy(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for step in self.steps:
            out[step.strategy] = out.get(step.strategy, 0) + 1
        return out


def _step_id(object_type: str, name: str) -> str:
    return "{0}:{1}".format(object_type.lower(), name)


def _view_dependencies(table: Table, known: Set[str]) -> List[str]:
    """Dependencies a view/MV/streaming table declares, limited to in-scope objects."""
    return [dep for dep in table.depends_on if dep in known]


def build_plan(
    inventory: Inventory,
    catalog_map: Optional[Dict[str, str]] = None,
    target_location_for: Optional[Dict[str, str]] = None,
) -> Plan:
    """Produce the ordered plan for one metastore inventory.

    ``catalog_map`` renames catalogs on the way across (``prod`` -> ``prod_gcp``).
    ``target_location_for`` maps a table's full name to the target storage URI
    for its data, for tables that need an explicit ``LOCATION``.
    """
    catalog_map = catalog_map or {}
    target_location_for = target_location_for or {}
    steps: List[Step] = []
    dangling: Dict[str, List[str]] = {}

    def target(name: str) -> str:
        parts = name.split(".")
        parts[0] = catalog_map.get(parts[0], parts[0])
        return ".".join(parts)

    # Tier 10-20: the storage foundation.
    credential_step: Dict[str, str] = {}
    for credential in sorted(inventory.storage_credentials, key=lambda c: c.name):
        step_id = _step_id("storage_credential", credential.name)
        credential_step[credential.name] = step_id
        steps.append(
            Step(
                id=step_id,
                tier=TIER_STORAGE_CREDENTIAL,
                action="create",
                object_type="STORAGE_CREDENTIAL",
                source_name=credential.name,
                target_name=credential.name,
                strategy=MANUAL,
                blocked_reason=(
                    "Cloud identity cannot be copied across clouds -- create the target "
                    "IAM role / managed identity / service account first, then the credential"
                ),
            )
        )

    location_step: Dict[str, str] = {}
    for location in sorted(inventory.external_locations, key=lambda loc: loc.name):
        step_id = _step_id("external_location", location.name)
        location_step[location.name] = step_id
        deps = []
        if location.credential_name in credential_step:
            deps.append(credential_step[location.credential_name])
        steps.append(
            Step(
                id=step_id,
                tier=TIER_EXTERNAL_LOCATION,
                action="create",
                object_type="EXTERNAL_LOCATION",
                source_name=location.name,
                target_name=location.name,
                depends_on=deps,
                detail={"source_url": location.url},
            )
        )

    # Tier 30-40: containers.
    catalog_step: Dict[str, str] = {}
    for catalog in sorted(inventory.catalogs, key=lambda c: c.name):
        step_id = _step_id("catalog", catalog.name)
        catalog_step[catalog.name] = step_id
        steps.append(
            Step(
                id=step_id,
                tier=TIER_CATALOG,
                action="create",
                object_type="CATALOG",
                source_name=catalog.name,
                target_name=catalog_map.get(catalog.name, catalog.name),
                depends_on=sorted(location_step.values()) if catalog.storage_root else [],
                detail={"isolation_mode": catalog.isolation_mode or "OPEN"},
            )
        )

    schema_step: Dict[str, str] = {}
    for schema in sorted(inventory.schemas, key=lambda s: s.full_name):
        step_id = _step_id("schema", schema.full_name)
        schema_step[schema.full_name] = step_id
        deps = [catalog_step[schema.catalog]] if schema.catalog in catalog_step else []
        steps.append(
            Step(
                id=step_id,
                tier=TIER_SCHEMA,
                action="create",
                object_type="SCHEMA",
                source_name=schema.full_name,
                target_name=target(schema.full_name),
                depends_on=deps,
            )
        )

    # Tier 50: volumes, before tables, because table code often reads from them.
    for volume in sorted(inventory.volumes, key=lambda v: v.full_name):
        parent = volume.schema_full_name
        deps = [schema_step[parent]] if parent in schema_step else []
        steps.append(
            Step(
                id=_step_id("volume", volume.full_name),
                tier=TIER_VOLUME,
                action="create",
                object_type="VOLUME",
                source_name=volume.full_name,
                target_name=target(volume.full_name),
                depends_on=deps,
                detail={"volume_type": volume.volume_type},
            )
        )

    # Tier 60-70: data-bearing objects, then views on top of them.
    known_names = set(inventory.table_index().keys())
    table_step: Dict[str, str] = {}
    data_tables = [t for t in inventory.tables if t.table_type in (MANAGED, EXTERNAL)]
    view_like = [
        t for t in inventory.tables if t.table_type in (VIEW, MATERIALIZED_VIEW, STREAMING_TABLE)
    ]

    for table in sorted(data_tables, key=lambda t: t.full_name):
        step_id = _step_id("table", table.full_name)
        table_step[table.full_name] = step_id
        parent = table.schema_full_name
        deps = [schema_step[parent]] if parent in schema_step else []
        if table.is_clonable:
            strategy, blocked = DEEP_CLONE, None
        elif table.table_type in (MANAGED, EXTERNAL):
            strategy = CTAS
            blocked = None
        else:  # pragma: no cover - defensive
            strategy, blocked = MANUAL, "unrecognised table type"
        detail = {"format": table.data_source_format, "table_type": table.table_type}
        location = target_location_for.get(table.full_name)
        if location:
            detail["target_location"] = location
        elif table.table_type == EXTERNAL:
            blocked = (
                "EXTERNAL table has no target LOCATION -- add a path rule or an explicit "
                "target location before running"
            )
        steps.append(
            Step(
                id=step_id,
                tier=TIER_TABLE,
                action="migrate",
                object_type="TABLE",
                source_name=table.full_name,
                target_name=target(table.full_name),
                strategy=strategy,
                depends_on=deps,
                blocked_reason=blocked,
                detail=detail,
            )
        )
        for constraint in table.constraints:
            steps.append(
                Step(
                    id=_step_id("constraint", "{0}.{1}".format(table.full_name, constraint.name)),
                    tier=TIER_CONSTRAINT,
                    action="create",
                    object_type="CONSTRAINT",
                    source_name="{0}.{1}".format(table.full_name, constraint.name),
                    target_name="{0}.{1}".format(target(table.full_name), constraint.name),
                    depends_on=[step_id],
                    detail={"kind": constraint.kind},
                )
            )

    # Views are ordered among themselves by their own dependency edges.
    view_names = {t.full_name for t in view_like}
    view_deps: Dict[str, List[str]] = {}
    for table in view_like:
        resolved = _view_dependencies(table, known_names)
        missing = [d for d in table.depends_on if d not in known_names]
        if missing:
            dangling[table.full_name] = missing
        view_deps[table.full_name] = resolved

    ordered_views, cycles = _topological_order(view_names, view_deps)

    for name in ordered_views:
        table = inventory.table_index()[name]
        step_id = _step_id("view", name)
        deps = []
        for dep in view_deps.get(name, []):
            if dep in table_step:
                deps.append(table_step[dep])
            elif dep in view_names:
                deps.append(_step_id("view", dep))
        if table.schema_full_name in schema_step:
            deps.append(schema_step[table.schema_full_name])
        blocked = None
        if table.table_type in (MATERIALIZED_VIEW, STREAMING_TABLE):
            strategy = RECREATE_PIPELINE
            blocked = (
                "{0} cannot be CLONEd -- recreate the Lakeflow/DLT pipeline that "
                "produces it and let it refresh in the target".format(table.table_type)
            )
        else:
            strategy = CREATE_VIEW
            if not table.view_definition:
                blocked = "view has no exported definition"
            elif name in dangling:
                # Creating this view would fail at compile time in the target,
                # or -- worse -- succeed against a same-named object that means
                # something different. Either way a person has to decide.
                blocked = "reads objects outside the migration scope: {0}".format(
                    ", ".join(dangling[name])
                )
        if name in {c for cycle in cycles for c in cycle}:
            blocked = "circular view dependency: {0}".format(
                " -> ".join(next(c for c in cycles if name in c))
            )
        steps.append(
            Step(
                id=step_id,
                tier=TIER_VIEW,
                action="create",
                object_type=table.table_type,
                source_name=name,
                target_name=target(name),
                strategy=strategy,
                depends_on=sorted(set(deps)),
                blocked_reason=blocked,
            )
        )

    # Tier 80-85: functions and models.
    for function in sorted(inventory.functions, key=lambda f: f.full_name):
        parent = function.schema_full_name
        deps = [schema_step[parent]] if parent in schema_step else []
        blocked = None
        if function.language not in ("SQL", "PYTHON"):
            blocked = "unsupported function language: {0}".format(function.language)
        steps.append(
            Step(
                id=_step_id("function", function.full_name),
                tier=TIER_FUNCTION,
                action="create",
                object_type="FUNCTION",
                source_name=function.full_name,
                target_name=target(function.full_name),
                depends_on=deps,
                blocked_reason=blocked,
                detail={"language": function.language},
            )
        )

    for model in sorted(inventory.models, key=lambda m: m.full_name):
        parent = model.schema_full_name
        deps = [schema_step[parent]] if parent in schema_step else []
        steps.append(
            Step(
                id=_step_id("model", model.full_name),
                tier=TIER_MODEL,
                action="create",
                object_type="REGISTERED_MODEL",
                source_name=model.full_name,
                target_name=target(model.full_name),
                strategy=MANUAL,
                depends_on=deps,
                blocked_reason=(
                    "model versions are artifacts, not metadata -- copy them with the "
                    "MLflow client and re-register; a DDL replay cannot move them"
                ),
                detail={"versions": str(model.version_count)},
            )
        )

    # Tier 90: policies that live inside a table.
    for table in sorted(inventory.tables, key=lambda t: t.full_name):
        if not table.row_filter and not table.column_masks:
            continue
        anchor = table_step.get(table.full_name) or _step_id("view", table.full_name)
        steps.append(
            Step(
                id=_step_id("policy", table.full_name),
                tier=TIER_POLICY,
                action="apply",
                object_type="ROW_COLUMN_POLICY",
                source_name=table.full_name,
                target_name=target(table.full_name),
                depends_on=[anchor],
                strategy=MANUAL,
                # DEEP CLONE copies rows, not the row filter or column masks
                # bound to the source table. Re-binding them needs the filter
                # function's argument columns, which the tables API does not
                # return -- so this is surfaced as work, never silently skipped.
                blocked_reason=(
                    "row filter / column masks are not copied by CLONE and must be "
                    "re-bound after the masking functions exist in the target"
                ),
                detail={
                    "row_filter": table.row_filter or "",
                    "masked_columns": ",".join(sorted(table.column_masks)),
                },
            )
        )

    # Tier 95: grants last, top-down within the tier.
    ordered_grants = sorted(
        inventory.grants, key=lambda g: (g.depth, g.full_name, g.principal, g.privilege)
    )
    for grant in ordered_grants:
        steps.append(
            Step(
                id=_step_id(
                    "grant",
                    "{0}|{1}|{2}".format(grant.full_name, grant.principal, grant.privilege),
                ),
                # Depth is folded into the tier so the final sort preserves
                # catalog -> schema -> table ordering. Applying a table grant
                # before its schema grant fails with a misleading permission
                # error, so this ordering is load-bearing, not cosmetic.
                tier=TIER_GRANT + grant.depth,
                action="grant",
                object_type="GRANT",
                source_name=grant.full_name,
                target_name=target(grant.full_name),
                depends_on=[],
                detail={
                    "principal": grant.principal,
                    "privilege": grant.privilege,
                    "securable": grant.object_type,
                },
            )
        )

    steps.sort(key=lambda s: (s.tier, s.source_name, s.id))
    return Plan(steps=steps, dangling_references=dangling, cycles=cycles)


def _topological_order(
    names: Iterable[str], edges: Dict[str, List[str]]
) -> "tuple[List[str], List[List[str]]]":
    """Kahn's algorithm with deterministic tie-breaking, plus cycle extraction.

    Returns ``(ordered_names, cycles)``. Nodes inside a cycle are appended at the
    end in name order so they still appear in the plan -- flagged, not dropped.
    """
    scope = set(names)
    remaining = {
        name: sorted({d for d in edges.get(name, []) if d in scope}) for name in scope
    }
    ordered: List[str] = []
    while True:
        ready = sorted(name for name, deps in remaining.items() if not deps)
        if not ready:
            break
        for name in ready:
            ordered.append(name)
            del remaining[name]
        for deps in remaining.values():
            for name in ready:
                if name in deps:
                    deps.remove(name)

    cycles: List[List[str]] = []
    if remaining:
        cycles = _extract_cycles(remaining)
        ordered.extend(sorted(remaining))
    return ordered, cycles


def _extract_cycles(remaining: Dict[str, List[str]]) -> List[List[str]]:
    """Depth-first back-edge detection over the nodes Kahn's algorithm rejected.

    Only nodes that could not be ordered reach this function, so the graph here
    is the knot itself -- small enough that plain recursion is safe.
    """
    white, grey, black = 0, 1, 2
    color: Dict[str, int] = {node: white for node in remaining}
    path: List[str] = []
    cycles: List[List[str]] = []

    def visit(node: str) -> None:
        color[node] = grey
        path.append(node)
        for child in remaining.get(node, []):
            if child not in color:
                continue
            if color[child] == grey:
                cycles.append(path[path.index(child) :] + [child])
            elif color[child] == white:
                visit(child)
        path.pop()
        color[node] = black

    for node in sorted(remaining):
        if color[node] == white:
            visit(node)
    return cycles


def validate_plan(plan: Plan) -> List[str]:
    """Structural checks on the plan itself, run before anything executes."""
    problems: List[str] = []
    ids = plan.by_id()
    positions = {step.id: index for index, step in enumerate(plan.steps)}
    for step in plan.steps:
        for dep in step.depends_on:
            if dep not in ids:
                problems.append("{0} depends on unknown step {1}".format(step.id, dep))
            elif positions[dep] > positions[step.id]:
                problems.append("{0} is ordered before its dependency {1}".format(step.id, dep))
    return problems


def steps_for_tier(plan: Plan, tier: int) -> Sequence[Step]:
    return [s for s in plan.steps if s.tier == tier]
