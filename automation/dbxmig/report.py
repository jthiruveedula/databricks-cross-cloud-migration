"""Human-readable reports.

The gap report is the most important output the toolkit produces. A plan that
says "412 steps, ready to run" is worth less than one that says "412 steps, and
these 7 things will not migrate unless a person deals with them first". Every
report here is written so it can be pasted into a migration status update or
attached to a change record as evidence.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from .crossrefs import CrossRefReport, coverage_gaps, wave_hints
from .depgraph import Plan
from .grants import GrantDiff, GrantTranslation
from .models import Inventory
from .reconcile import ReconciliationReport
from .rewrite import Rewriter
from .workspace import ASSET_CLASSES, WorkspaceInventory, owner_hint


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    if not rows:
        return "_none_\n"
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |")
    return "\n".join(out) + "\n"


def inventory_summary(inventory: Inventory) -> str:
    counts = inventory.counts()
    rows = [[key, str(value)] for key, value in sorted(counts.items()) if value]
    return "\n".join(
        [
            "## Source inventory",
            "",
            "Metastore: `{0}` ({1}, {2})  ".format(
                inventory.metastore_name or "unnamed",
                inventory.cloud or "cloud unknown",
                inventory.region or "region unknown",
            ),
            "Captured: {0}".format(inventory.captured_at or "unknown"),
            "",
            _table(["Object type", "Count"], rows),
        ]
    )


def plan_summary(plan: Plan) -> str:
    strategy_rows = [[k, str(v)] for k, v in sorted(plan.counts_by_strategy().items())]
    return "\n".join(
        [
            "## Plan",
            "",
            "{0} steps, {1} executable, {2} blocked.".format(
                len(plan.steps), len(plan.executable_steps), len(plan.blocked_steps)
            ),
            "",
            _table(["Strategy", "Steps"], strategy_rows),
        ]
    )


def gap_report(
    plan: Plan,
    rewriter: Rewriter,
    inventory: Inventory,
    grant_translation: Optional[GrantTranslation] = None,
) -> str:
    """Everything that will not migrate on its own, in one place."""
    sections: List[str] = ["## Gaps requiring a decision", ""]

    blocked_rows = [
        [step.object_type, step.source_name, step.blocked_reason or ""]
        for step in plan.blocked_steps
    ]
    sections.append("### Blocked steps")
    sections.append("")
    sections.append(_table(["Object type", "Object", "Why"], blocked_rows))

    unmapped_rows: List[List[str]] = []
    for table in inventory.tables:
        for uri in rewriter.find_unmapped(table.storage_location or ""):
            unmapped_rows.append(["TABLE", table.full_name, uri])
        for uri in rewriter.find_unmapped(table.view_definition or ""):
            unmapped_rows.append([table.table_type, table.full_name, uri])
    for volume in inventory.volumes:
        for uri in rewriter.find_unmapped(volume.storage_location or ""):
            unmapped_rows.append(["VOLUME", volume.full_name, uri])
    for location in inventory.external_locations:
        for uri in rewriter.find_unmapped(location.url):
            unmapped_rows.append(["EXTERNAL_LOCATION", location.name, uri])
    sections.append("### Storage paths with no rule")
    sections.append("")
    sections.append(
        "These would land in the target still pointing at source-cloud storage.\n"
        if unmapped_rows
        else ""
    )
    sections.append(_table(["Object type", "Object", "Unmapped URI"], unmapped_rows))

    dangling_rows = [
        [name, ", ".join(refs)] for name, refs in sorted(plan.dangling_references.items())
    ]
    sections.append("### References outside the migration scope")
    sections.append("")
    sections.append(_table(["Object", "Reads from"], dangling_rows))

    if plan.cycles:
        sections.append("### Circular view dependencies")
        sections.append("")
        sections.append(_table(["Cycle"], [[" -> ".join(cycle)] for cycle in plan.cycles]))

    if grant_translation is not None and grant_translation.unmapped_principals:
        sections.append("### Principals with no target mapping")
        sections.append("")
        sections.append(
            _table(
                ["Source principal"], [[p] for p in grant_translation.unmapped_principals]
            )
        )

    manual_rows: List[List[str]] = []
    for connection in inventory.connections:
        manual_rows.append(["CONNECTION", str(connection.get("name", "")), "recreate by hand"])
    for share in inventory.shares:
        manual_rows.append(
            ["SHARE", str(share.get("name", "")), "recreate and re-invite recipients"]
        )
    for recipient in inventory.recipients:
        manual_rows.append(
            ["RECIPIENT", str(recipient.get("name", "")), "new activation link required"]
        )
    if manual_rows:
        sections.append("### Metastore-level objects the toolkit does not create")
        sections.append("")
        sections.append(_table(["Object type", "Name", "Action"], manual_rows))

    return "\n".join(sections)


def reconciliation_summary(report: ReconciliationReport) -> str:
    rows = [
        [str(f.severity), f.check, f.obj, f.detail]
        for f in sorted(report.findings, key=lambda f: (f.severity, f.check, f.obj))
    ]
    verdict = "PASS" if report.passed else "FAIL -- {0} blocker(s)".format(len(report.blockers))
    return "\n".join(
        [
            "## Reconciliation",
            "",
            "Objects checked: {0}. Verdict: **{1}**".format(report.checked, verdict),
            "",
            _table(["Sev", "Check", "Object", "Detail"], rows),
        ]
    )


def grant_diff_summary(diff: GrantDiff) -> str:
    missing = [
        [g.object_type, g.full_name, g.principal, g.privilege] for g in diff.missing_in_target
    ]
    extra = [[g.object_type, g.full_name, g.principal, g.privilege] for g in diff.extra_in_target]
    return "\n".join(
        [
            "## Grant diff",
            "",
            "### Missing in target ({0})".format(len(missing)),
            "",
            _table(["Securable", "Object", "Principal", "Privilege"], missing),
            "### Present in target but not expected ({0})".format(len(extra)),
            "",
            _table(["Securable", "Object", "Principal", "Privilege"], extra),
        ]
    )


def full_report(
    inventory: Inventory,
    plan: Plan,
    rewriter: Rewriter,
    grant_translation: Optional[GrantTranslation] = None,
    reconciliation: Optional[ReconciliationReport] = None,
) -> str:
    parts = [
        "# Metastore migration report",
        "",
        inventory_summary(inventory),
        plan_summary(plan),
        gap_report(plan, rewriter, inventory, grant_translation),
    ]
    if reconciliation is not None:
        parts.append(reconciliation_summary(reconciliation))
    return "\n".join(parts)


def workspace_summary(inventory: WorkspaceInventory) -> str:
    """Per-asset-class counts, owner, and collection status.

    The owner column is there because the question that stalls discovery is
    never "what is the API" -- it is "who is chasing the dashboards".
    """
    rows: List[List[str]] = []
    for asset_class in ASSET_CLASSES:
        result = next((r for r in inventory.results if r.asset_class == asset_class), None)
        if result is None:
            status = "not collected"
        elif not result.ok:
            status = "FAILED: " + result.reason
        elif result.collected == 0:
            status = "empty -- confirm"
        else:
            status = "ok"
        rows.append(
            [asset_class, str(len(inventory.rows(asset_class))), owner_hint(asset_class), status]
        )
    return "\n".join(
        [
            "## Workspace inventory",
            "",
            "Captured: {0}  ".format(inventory.captured_at or "unknown"),
            "Workspace: {0}".format(inventory.workspace_host or "unknown"),
            "",
            _table(["Asset class", "Count", "Usually owned by", "Status"], rows),
        ]
    )


def crossref_summary(inventory: WorkspaceInventory, report: CrossRefReport) -> str:
    """What each asset depends on, what breaks, and what must move together."""
    blocker_rows = [
        [f.asset_class, f.asset_name or f.asset_id, f.location, f.kind, f.reference, f.breaks]
        for f in report.blockers
    ]
    attention_rows = [
        [f.asset_class, f.asset_name or f.asset_id, f.location, f.kind, f.reference, f.breaks]
        for f in report.findings
        if f.severity == "attention"
    ]
    kind_rows = [[k, str(v)] for k, v in sorted(report.by_kind().items())]
    hints = wave_hints(report)

    sections = [
        "## Cross-references",
        "",
        "{0} reference(s) found across {1} asset(s). {2} blocker(s).".format(
            len(report.findings), len(report.by_asset()), len(report.blockers)
        ),
        "",
        _table(["Reference kind", "Count"], kind_rows),
        "### Blockers — fix before scheduling a wave",
        "",
        _table(
            ["Asset class", "Asset", "Where", "Kind", "Reference", "What breaks"], blocker_rows
        ),
        "### Needs attention — carry into the wave plan",
        "",
        _table(["Asset class", "Asset", "Where", "Kind", "Reference", "Note"], attention_rows),
        "### Shared references — these assets must move together",
        "",
        _table(["Shared dependency"], [[h] for h in hints]),
    ]
    gaps = coverage_gaps(inventory)
    if gaps:
        sections.extend(
            [
                "### Coverage gaps",
                "",
                _table(["Asset class"], [[g] for g in gaps]),
            ]
        )
    return "\n".join(sections)


def counts_delta(source: Inventory, target: Inventory) -> Dict[str, int]:
    source_counts = source.counts()
    target_counts = target.counts()
    return {
        key: source_counts.get(key, 0) - target_counts.get(key, 0)
        for key in sorted(set(source_counts) | set(target_counts))
    }
