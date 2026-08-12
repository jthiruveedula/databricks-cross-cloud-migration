"""Replay workspace object ACLs into the target.

Unity Catalog grants and workspace object permissions are two different
systems. ``grants.py`` covers the first. This covers the second: who may run a
job, restart a cluster, attach to a pool, use a warehouse, or edit a pipeline —
none of which appears in ``information_schema``, and none of which is included
in a workspace export.

The collector already gathers these. Until now nothing replayed them, which
made "replay them from the object-ACL inventory" advice with no implementation
behind it.

Two facts shape the design:

* **Target object IDs differ from source.** A recreated job gets a new id, so an
  ACL keyed on the source id is meaningless. The plan is therefore keyed on
  object *name*, and resolved against the target at apply time.
* **Names are not guaranteed unique.** Two jobs may legitimately share a name,
  which makes name-based resolution ambiguous for those objects. Ambiguity is
  reported rather than resolved by guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from .grants import PrincipalMap, UnmappedPrincipalError
from .workspace import WorkspaceInventory

#: Databricks permissions API object type -> the SDK/list call used to find the
#: target object by name at replay time.
OBJECT_TYPE_LOOKUP = {
    "jobs": ("jobs", "name"),
    "clusters": ("clusters", "cluster_name"),
    "instance-pools": ("instance_pools", "instance_pool_name"),
    "sql/warehouses": ("warehouses", "name"),
    "pipelines": ("pipelines", "name"),
    "cluster-policies": ("cluster_policies", "name"),
}

#: Set by object ownership, not by an access-control entry. Attempting to grant
#: it through the permissions API is not how ownership transfers.
NON_REPLAYABLE_LEVELS = frozenset({"IS_OWNER"})


@dataclass(frozen=True)
class AclEntry:
    object_type: str
    object_name: str
    principal: str
    permission_level: str

    def key(self) -> Tuple[str, str, str, str]:
        return (self.object_type, self.object_name, self.principal, self.permission_level)


@dataclass
class AclPlan:
    entries: List[AclEntry] = field(default_factory=list)
    skipped: List[Tuple[str, str]] = field(default_factory=list)
    unmapped_principals: List[str] = field(default_factory=list)
    #: Object names shared by more than one object of the same type. Name-based
    #: resolution cannot pick between them, so they need a human.
    ambiguous: List[Tuple[str, str]] = field(default_factory=list)
    #: ACL entries granted to an individual rather than a group. Each one is a
    #: migration decision: most should become a group membership instead.
    individual_grants: List[AclEntry] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.unmapped_principals and not self.ambiguous

    def counts_by_type(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for entry in self.entries:
            out[entry.object_type] = out.get(entry.object_type, 0) + 1
        return out


def _looks_like_user(principal: str) -> bool:
    """An email-shaped principal is a person, not a group.

    Not a hard rule -- a group *can* be named like an email -- but it is the
    signal worth surfacing, because a per-person workspace ACL is usually an
    accident that should become a group membership in the target.
    """
    return "@" in principal


def build_acl_plan(
    inventory: WorkspaceInventory,
    principal_map: PrincipalMap,
    strict: bool = True,
) -> AclPlan:
    """Translate collected ACLs into a name-keyed, target-ready plan."""
    plan = AclPlan()
    rows = inventory.rows("object_acls")

    principals = {str(r.get("principal", "")) for r in rows if r.get("principal")}
    missing = sorted(
        p for p in principals if p not in principal_map.mapping and p not in principal_map.retired
    )
    if missing:
        plan.unmapped_principals = missing
        if strict:
            raise UnmappedPrincipalError(
                "no target mapping for {0} principal(s) holding workspace ACLs: {1}".format(
                    len(missing), ", ".join(missing)
                )
            )

    # A name shared by two objects of the same type cannot be resolved by name.
    seen: Dict[Tuple[str, str], set] = {}
    for row in rows:
        key = (str(row.get("object_type", "")), str(row.get("object_name", "")))
        seen.setdefault(key, set()).add(str(row.get("object_id", "")))
    for (object_type, object_name), ids in sorted(seen.items()):
        if len(ids) > 1 and object_name:
            plan.ambiguous.append((object_type, object_name))
    ambiguous_keys = set(plan.ambiguous)

    for row in sorted(
        rows,
        key=lambda r: (
            str(r.get("object_type", "")),
            str(r.get("object_name", "")),
            str(r.get("principal", "")),
            str(r.get("permission_level", "")),
        ),
    ):
        object_type = str(row.get("object_type", ""))
        object_name = str(row.get("object_name", ""))
        principal = str(row.get("principal", ""))
        level = str(row.get("permission_level", "")).upper()

        if not object_name:
            plan.skipped.append((str(row.get("object_id", "")), "object has no name to resolve by"))
            continue
        if object_type not in OBJECT_TYPE_LOOKUP:
            plan.skipped.append((object_name, "unsupported object type: " + object_type))
            continue
        if level in NON_REPLAYABLE_LEVELS:
            plan.skipped.append(
                (object_name, "{0} is set by ownership, not by an ACL entry".format(level))
            )
            continue
        if (object_type, object_name) in ambiguous_keys:
            plan.skipped.append(
                (object_name, "name is shared by more than one {0}".format(object_type))
            )
            continue
        if principal in principal_map.retired:
            plan.skipped.append((object_name, "principal retired: " + principal))
            continue
        target_principal = principal_map.mapping.get(principal)
        if target_principal is None:
            plan.skipped.append((object_name, "principal unmapped: " + principal))
            continue

        entry = AclEntry(object_type, object_name, target_principal, level)
        plan.entries.append(entry)
        if _looks_like_user(target_principal):
            plan.individual_grants.append(entry)

    return plan


def replay_script(plan: AclPlan) -> str:
    """Emit a runnable replay script.

    Written out rather than executed for the same reason the DDL is: a
    permissions change across an estate should be reviewable as a diff before
    anyone runs it.
    """
    lines = [
        '"""Replay workspace object ACLs into the target.',
        "",
        "Generated by `dbxmig acls`. Review before running.",
        "",
        "Objects are resolved by NAME because target ids differ from source.",
        "Anything the plan could not resolve is in the accompanying report, not",
        "silently dropped here.",
        '"""',
        "",
        "from databricks.sdk import WorkspaceClient",
        "from databricks.sdk.service import iam",
        "",
        "w = WorkspaceClient()  # target workspace",
        "",
        "ACLS = [",
    ]
    for entry in plan.entries:
        lines.append(
            "    ({0!r}, {1!r}, {2!r}, {3!r}),".format(
                entry.object_type, entry.object_name, entry.principal, entry.permission_level
            )
        )
    lines.extend(
        [
            "]",
            "",
            "",
            "def resolve(object_type, name):",
            '    """Find the TARGET object id for a source object name."""',
            "    listers = {",
            '        "jobs": lambda: [(j.job_id, j.settings.name) for j in w.jobs.list()],',
            '        "clusters": lambda: [',
            "            (c.cluster_id, c.cluster_name) for c in w.clusters.list()",
            "        ],",
            '        "instance-pools": lambda: [',
            "            (p.instance_pool_id, p.instance_pool_name)",
            "            for p in w.instance_pools.list()",
            "        ],",
            '        "sql/warehouses": lambda: [(x.id, x.name) for x in w.warehouses.list()],',
            '        "pipelines": lambda: [',
            "            (p.pipeline_id, p.name) for p in w.pipelines.list_pipelines()",
            "        ],",
            '        "cluster-policies": lambda: [',
            "            (p.policy_id, p.name) for p in w.cluster_policies.list()",
            "        ],",
            "    }",
            "    matches = [str(i) for i, n in listers[object_type]() if n == name]",
            "    if len(matches) != 1:",
            "        raise LookupError(",
            '            f"{object_type} {name!r} resolved to {len(matches)} objects in target"',
            "        )",
            "    return matches[0]",
            "",
            "",
            "# Group by object so each object's ACL is set in one call. update() is",
            "# additive; it does not remove permissions the target already has.",
            "by_object = {}",
            "for object_type, name, principal, level in ACLS:",
            "    by_object.setdefault((object_type, name), []).append((principal, level))",
            "",
            "for (object_type, name), grants in sorted(by_object.items()):",
            "    object_id = resolve(object_type, name)",
            "    w.permissions.update(",
            "        request_object_type=object_type,",
            "        request_object_id=object_id,",
            "        access_control_list=[",
            "            iam.AccessControlRequest(",
            "                group_name=principal, permission_level=iam.PermissionLevel(level)",
            "            )",
            "            for principal, level in grants",
            "        ],",
            "    )",
            '    print(f"set {len(grants)} permission(s) on {object_type} {name}")',
            "",
        ]
    )
    return "\n".join(lines)


def to_rows(plan: AclPlan) -> List[Sequence[str]]:
    out: List[Sequence[str]] = [["object_type", "object_name", "principal", "permission_level"]]
    for entry in plan.entries:
        out.append([entry.object_type, entry.object_name, entry.principal, entry.permission_level])
    return out


def summary(plan: AclPlan) -> str:
    """Markdown report: what will replay, and what needs a person."""

    def table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
        if not rows:
            return "_none_\n"
        out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
        for row in rows:
            out.append("| " + " | ".join(str(c) for c in row) + " |")
        return "\n".join(out) + "\n"

    sections = [
        "## Workspace object ACLs",
        "",
        "{0} entry/entries across {1} object type(s).".format(
            len(plan.entries), len(plan.counts_by_type())
        ),
        "",
        table(
            ["Object type", "Entries"],
            [[k, str(v)] for k, v in sorted(plan.counts_by_type().items())],
        ),
        "### Granted to an individual rather than a group",
        "",
        "Each of these is a decision: in the target it is usually a group membership.",
        "",
        table(
            ["Object type", "Object", "Principal", "Level"],
            [
                [e.object_type, e.object_name, e.principal, e.permission_level]
                for e in plan.individual_grants
            ],
        ),
        "### Ambiguous object names — cannot be resolved by name",
        "",
        table(["Object type", "Object"], [[t, n] for t, n in plan.ambiguous]),
        "### Skipped",
        "",
        table(["Object", "Reason"], [[o, r] for o, r in plan.skipped]),
    ]
    if plan.unmapped_principals:
        sections.extend(
            [
                "### Principals with no target mapping",
                "",
                table(["Principal"], [[p] for p in plan.unmapped_principals]),
            ]
        )
    return "\n".join(sections)


def diff(expected: Sequence[AclEntry], actual: Sequence[AclEntry]) -> Dict[str, List[AclEntry]]:
    """Compare an expected ACL set against what the target reports."""
    expected_index = {e.key(): e for e in expected}
    actual_index = {a.key(): a for a in actual}
    missing = sorted(set(expected_index) - set(actual_index))
    extra = sorted(set(actual_index) - set(expected_index))
    return {
        "missing_in_target": [expected_index[k] for k in missing],
        "extra_in_target": [actual_index[k] for k in extra],
    }


def entries_from_inventory(inventory: WorkspaceInventory) -> List[AclEntry]:
    """Read a collected inventory's ACLs as entries, for diffing a target."""
    return [
        AclEntry(
            str(r.get("object_type", "")),
            str(r.get("object_name", "")),
            str(r.get("principal", "")),
            str(r.get("permission_level", "")).upper(),
        )
        for r in inventory.rows("object_acls")
    ]
