"""Cross-reference scanning: turn an asset list into a dependency and risk list.

An inventory that says "you have 412 jobs" is a count. What a migration
actually needs to know is which of those jobs will fail in the target and why —
and every one of those reasons is a *reference* from one asset to something
else: a storage path, a secret, a cluster policy, a warehouse, an IAM identity.

This module reads a collected workspace inventory and extracts those
references. Each finding names the asset, the reference, and what breaks. That
list is the input to wave planning: assets sharing a reference belong in the
same wave, and assets with an unresolvable reference are blocked before
anything is scheduled.

Everything here is deterministic string analysis over already-collected data —
no network, no model, no workspace.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .rewrite import Rewriter
from .workspace import WorkspaceInventory

#: `dbutils.secrets.get(scope="x", key="y")` in any of its argument spellings.
_SECRET_CALL = re.compile(
    r"""dbutils\s*\.\s*secrets\s*\.\s*get\s*\(\s*
        (?:scope\s*=\s*)?['"]([^'"]+)['"]\s*,\s*
        (?:key\s*=\s*)?['"]([^'"]+)['"]""",
    re.IGNORECASE | re.VERBOSE,
)
#: `{{secrets/scope/key}}` -- the Spark-conf and job-parameter spelling.
_SECRET_REF = re.compile(r"\{\{\s*secrets\s*/\s*([^/}]+)\s*/\s*([^}]+?)\s*\}\}")
_MOUNT = re.compile(r"(?:dbfs:)?/mnt/[A-Za-z0-9._\-/]+")
_INSTANCE_PROFILE = re.compile(r"arn:aws:iam::\d{12}:instance-profile/[A-Za-z0-9+=,.@_\-/]+")
_WORKSPACE_URL = re.compile(
    r"https://(?:adb-\d+\.\d+\.azuredatabricks\.net"
    r"|[a-z0-9-]+\.cloud\.databricks\.com"
    r"|\d+\.\d+\.gcp\.databricks\.com)",
    re.IGNORECASE,
)

SEV_BLOCKER = "blocker"
SEV_ATTENTION = "attention"
SEV_INFO = "info"


@dataclass(frozen=True)
class CrossRef:
    """One reference from an asset to something it needs in the target."""

    asset_class: str
    asset_id: str
    asset_name: str
    kind: str
    reference: str
    severity: str
    breaks: str
    #: Where inside the asset the reference was found -- "line 42" for a source
    #: file, empty for a reference read out of structured API metadata.
    location: str = ""

    def key(self) -> str:
        return "|".join(
            [self.asset_class, self.asset_id, self.kind, self.reference, self.location]
        )


@dataclass
class CrossRefReport:
    findings: List[CrossRef] = field(default_factory=list)

    def add(self, finding: CrossRef) -> None:
        self.findings.append(finding)

    @property
    def blockers(self) -> List[CrossRef]:
        return [f for f in self.findings if f.severity == SEV_BLOCKER]

    def by_kind(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for finding in self.findings:
            out[finding.kind] = out.get(finding.kind, 0) + 1
        return out

    def by_asset(self) -> Dict[str, List[CrossRef]]:
        """Findings grouped per asset -- the per-owner worklist."""
        out: Dict[str, List[CrossRef]] = {}
        for finding in self.findings:
            label = "{0}:{1}".format(finding.asset_class, finding.asset_name or finding.asset_id)
            out.setdefault(label, []).append(finding)
        return out

    def shared_references(self, minimum: int = 2) -> Dict[str, List[str]]:
        """References used by ``minimum`` or more assets.

        This is the wave-planning signal. Two jobs sharing a secret scope, a
        cluster policy, or a storage prefix cannot be placed in different waves
        without the earlier wave depending on something the later one owns.
        """
        index: Dict[str, List[str]] = {}
        for finding in self.findings:
            label = "{0}:{1}".format(finding.asset_class, finding.asset_name or finding.asset_id)
            holders = index.setdefault("{0}={1}".format(finding.kind, finding.reference), [])
            if label not in holders:
                holders.append(label)
        return {ref: sorted(holders) for ref, holders in index.items() if len(holders) >= minimum}


def _texts_of(row: Dict[str, Any]) -> str:
    """Every string in a row, concatenated, for pattern scanning."""
    parts: List[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            for key, item in value.items():
                parts.append(str(key))
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    walk(row)
    return "\n".join(parts)


def _asset_identity(asset_class: str, row: Dict[str, Any]) -> "tuple[str, str]":
    for key in (
        "job_id",
        "cluster_id",
        "pipeline_id",
        "policy_id",
        "warehouse_id",
        "instance_pool_id",
        "dashboard_id",
        "query_id",
        "alert_id",
        "repo_id",
        "scope",
    ):
        if row.get(key):
            return (str(row[key]), str(row.get("name", "") or row.get("scope", "")))
    return ("", str(row.get("name", "")))


def scan(
    inventory: WorkspaceInventory,
    rewriter: Optional[Rewriter] = None,
    known_scopes: Optional[Iterable[str]] = None,
) -> CrossRefReport:
    """Extract every migration-relevant reference from a workspace inventory.

    ``rewriter`` supplies the source→target path rules. With it, a storage URI
    that has no rule becomes a blocker instead of an informational note — which
    is the whole difference between "we listed the paths" and "we know which
    paths will break".
    """
    report = CrossRefReport()
    scope_names = {s for s in (known_scopes or [])}
    if not scope_names:
        scope_names = {str(r.get("scope", "")) for r in inventory.rows("secret_scopes")}

    policy_ids = {str(r.get("policy_id", "")) for r in inventory.rows("cluster_policies")}
    warehouse_ids = {str(r.get("warehouse_id", "")) for r in inventory.rows("sql_warehouses")}
    pool_ids = {str(r.get("instance_pool_id", "")) for r in inventory.rows("instance_pools")}

    for asset_class, rows in inventory.assets.items():
        if asset_class in ("object_acls", "groups", "service_principals"):
            continue
        for row in rows:
            asset_id, asset_name = _asset_identity(asset_class, row)
            _scan_blob(
                report,
                asset_class,
                asset_id,
                asset_name,
                _texts_of(row),
                rewriter,
                scope_names,
            )
            _scan_structured_ids(
                report, asset_class, asset_id, asset_name, row, policy_ids, warehouse_ids, pool_ids
            )

    return _dedupe(report)


def _scan_blob(
    report: CrossRefReport,
    asset_class: str,
    asset_id: str,
    asset_name: str,
    blob: str,
    rewriter: Optional[Rewriter],
    scope_names: "set",
    with_lines: bool = False,
) -> None:
    """Apply every pattern to one blob of text.

    Shared by the metadata scan and the source-file scan so a hardcoded path is
    described identically whether it was found in a job definition or on line
    88 of a notebook -- the migration consequence is the same, and a reviewer
    should not have to learn two vocabularies.
    """
    starts = _line_starts(blob) if with_lines else None

    def at(offset: int) -> str:
        return _line_of(starts, offset) if starts is not None else ""

    for uri in (rewriter.find_uris(blob) if rewriter else _default_uris(blob)):
        if uri.startswith("/Volumes/"):
            continue
        if _MOUNT.search(uri):
            # Reported below as a dbfs_mount, which carries the more useful
            # instruction. Emitting both doubles the row count without adding
            # a decision.
            continue
        mapped = rewriter.rewrite_uri(uri).mapped if rewriter else False
        report.add(
            CrossRef(
                asset_class,
                asset_id,
                asset_name,
                "storage_uri",
                uri,
                SEV_INFO if mapped else SEV_BLOCKER,
                "resolves to source-cloud storage in the target"
                if not mapped
                else "rewritten by a path rule",
                at(blob.find(uri)),
            )
        )

    for match in _MOUNT.finditer(blob):
        report.add(
            CrossRef(
                asset_class,
                asset_id,
                asset_name,
                "dbfs_mount",
                match.group(0),
                SEV_BLOCKER,
                "DBFS mounts do not migrate -- retire to a Volume or external location",
                at(match.start()),
            )
        )

    for pattern in (_SECRET_CALL, _SECRET_REF):
        for match in pattern.finditer(blob):
            scope, key = match.group(1).strip(), match.group(2).strip()
            known = scope in scope_names
            report.add(
                CrossRef(
                    asset_class,
                    asset_id,
                    asset_name,
                    "secret",
                    "{0}/{1}".format(scope, key),
                    SEV_ATTENTION if known else SEV_BLOCKER,
                    "secret values cannot be exported -- re-source from the system of record"
                    if known
                    else "references a scope not present in the inventory",
                    at(match.start()),
                )
            )

    for match in _INSTANCE_PROFILE.finditer(blob):
        report.add(
            CrossRef(
                asset_class,
                asset_id,
                asset_name,
                "cloud_identity",
                match.group(0),
                SEV_BLOCKER,
                "AWS instance profile has no equivalent in the target cloud",
                at(match.start()),
            )
        )

    for match in _WORKSPACE_URL.finditer(blob):
        report.add(
            CrossRef(
                asset_class,
                asset_id,
                asset_name,
                "hardcoded_workspace_url",
                match.group(0),
                SEV_BLOCKER,
                "points at the source workspace after cutover",
                at(match.start()),
            )
        )


def _scan_structured_ids(
    report: CrossRefReport,
    asset_class: str,
    asset_id: str,
    asset_name: str,
    row: Dict[str, Any],
    policy_ids: "set",
    warehouse_ids: "set",
    pool_ids: "set",
) -> None:
    """References that come from typed fields rather than from free text.

    An asset is not a dependency of itself: a cluster-policy row naturally
    contains its own ``policy_id``. Only cross-class references are edges.
    """
    policy_refs = _as_list(row.get("cluster_policy_ids")) + _as_list(row.get("policy_id"))
    for policy_id in policy_refs:
        if not policy_id or asset_class == "cluster_policies":
            continue
        report.add(
            CrossRef(
                asset_class,
                asset_id,
                asset_name,
                "cluster_policy",
                str(policy_id),
                SEV_ATTENTION if policy_id in policy_ids else SEV_BLOCKER,
                "policy must exist in the target before this can be created"
                if policy_id in policy_ids
                else "references a policy absent from the inventory",
            )
        )

    warehouse_refs = _as_list(row.get("warehouse_ids")) + _as_list(row.get("warehouse_id"))
    for warehouse_id in warehouse_refs:
        if not warehouse_id or asset_class == "sql_warehouses":
            continue
        report.add(
            CrossRef(
                asset_class,
                asset_id,
                asset_name,
                "sql_warehouse",
                str(warehouse_id),
                SEV_ATTENTION if warehouse_id in warehouse_ids else SEV_BLOCKER,
                "warehouse id changes in the target -- every reference needs rewriting",
            )
        )

    pool_id = str(row.get("instance_pool_id", "") or "")
    if pool_id and asset_class != "instance_pools":
        report.add(
            CrossRef(
                asset_class,
                asset_id,
                asset_name,
                "instance_pool",
                pool_id,
                SEV_ATTENTION if pool_id in pool_ids else SEV_BLOCKER,
                "pool must exist in the target before the cluster can start",
            )
        )


def _line_starts(text: str) -> List[int]:
    starts = [0]
    for index, char in enumerate(text):
        if char == "\n":
            starts.append(index + 1)
    return starts


def _line_of(starts: Optional[List[int]], offset: int) -> str:
    if starts is None or offset < 0:
        return ""
    low, high = 0, len(starts) - 1
    while low < high:
        mid = (low + high + 1) // 2
        if starts[mid] <= offset:
            low = mid
        else:
            high = mid - 1
    return "line {0}".format(low + 1)


def _default_uris(text: str) -> List[str]:
    return Rewriter().find_uris(text)


def _as_list(value: Any) -> List[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v]
    return [str(value)]


def _dedupe(report: CrossRefReport) -> CrossRefReport:
    seen = set()
    out = CrossRefReport()
    for finding in report.findings:
        if finding.key() in seen:
            continue
        seen.add(finding.key())
        out.add(finding)
    return out


#: File types a Databricks workspace export or a Repos checkout actually
#: contains. Everything else in a repo (images, wheels, parquet) is skipped.
SOURCE_EXTENSIONS = (
    ".py",
    ".sql",
    ".scala",
    ".r",
    ".ipynb",
    ".json",
    ".yml",
    ".yaml",
    ".sh",
    ".conf",
    ".tf",
)

#: Directories never worth walking.
SKIP_DIRS = frozenset(
    {".git", "node_modules", ".venv", "venv", "__pycache__", ".terraform", "dist", "build"}
)

#: A single file bigger than this is data, not code.
MAX_FILE_BYTES = 2_000_000


def notebook_source(text: str, filename: str) -> str:
    """Return scannable text for one file.

    ``.ipynb`` is JSON with the code buried in ``cells[].source``; scanning the
    raw JSON works but reports useless line numbers and matches metadata. This
    extracts the source cells so a reported line means something to whoever has
    to fix it.
    """
    if not filename.lower().endswith(".ipynb"):
        return text
    try:
        import json as _json

        notebook = _json.loads(text)
    except ValueError:
        return text
    lines: List[str] = []
    for cell in notebook.get("cells") or []:
        source = cell.get("source")
        if isinstance(source, list):
            lines.extend(str(s).rstrip("\n") for s in source)
        elif isinstance(source, str):
            lines.extend(source.split("\n"))
    return "\n".join(lines)


def scan_source_tree(
    root: str,
    rewriter: Optional[Rewriter] = None,
    known_scopes: Optional[Iterable[str]] = None,
    extensions: Sequence[str] = SOURCE_EXTENSIONS,
) -> CrossRefReport:
    """Scan exported notebooks and source files for the same references.

    ``scan()`` reads asset *metadata* -- a job's configured policy, a cluster's
    init script path. It cannot see a storage path hardcoded on line 88 of a
    notebook, and that is where most of them are. This closes that half: same
    patterns, same vocabulary, plus a line number.

    Point it at an unzipped workspace export, a Repos checkout, or the source
    directory of an Asset Bundle.
    """
    report = CrossRefReport()
    scope_names = {s for s in (known_scopes or [])}
    lowered = tuple(e.lower() for e in extensions)

    for directory, subdirs, filenames in os.walk(root):
        subdirs[:] = [d for d in subdirs if d not in SKIP_DIRS and not d.startswith(".")]
        for filename in sorted(filenames):
            if not filename.lower().endswith(lowered):
                continue
            path = os.path.join(directory, filename)
            try:
                if os.path.getsize(path) > MAX_FILE_BYTES:
                    continue
                with open(path, "r", encoding="utf-8", errors="replace") as handle:
                    text = handle.read()
            except OSError:
                continue
            relative = os.path.relpath(path, root)
            _scan_blob(
                report,
                "source_file",
                relative,
                relative,
                notebook_source(text, filename),
                rewriter,
                scope_names,
                with_lines=True,
            )
    return _dedupe(report)


def merge(*reports: CrossRefReport) -> CrossRefReport:
    """Combine metadata and source-file scans into one deduplicated report."""
    out = CrossRefReport()
    for report in reports:
        for finding in report.findings:
            out.add(finding)
    return _dedupe(out)


def coverage_gaps(inventory: WorkspaceInventory) -> List[str]:
    """Asset classes that produced nothing, phrased as questions to answer.

    An empty inventory section is the most dangerous state in discovery,
    because it reads as "done" in every progress report.
    """
    gaps: List[str] = []
    for result in inventory.results:
        if not result.ok:
            gaps.append(
                "{0}: collection FAILED ({1}) -- this is a permissions or API problem, "
                "not an empty estate".format(result.asset_class, result.reason)
            )
        elif result.collected == 0:
            gaps.append(
                "{0}: zero rows -- confirm the estate genuinely has none before "
                "signing discovery off".format(result.asset_class)
            )
    return gaps


def wave_hints(report: CrossRefReport, minimum: int = 2) -> List[str]:
    """Human-readable 'these must move together' statements."""
    hints: List[str] = []
    for reference, holders in sorted(report.shared_references(minimum).items()):
        hints.append(
            "{0} is shared by {1}: {2}".format(reference, len(holders), ", ".join(holders))
        )
    return hints


def to_rows(report: CrossRefReport) -> List[Sequence[str]]:
    """Header + rows, for CSV export into whatever tracker the programme uses."""
    out: List[Sequence[str]] = [
        [
            "severity",
            "asset_class",
            "asset_name",
            "asset_id",
            "location",
            "kind",
            "reference",
            "breaks",
        ]
    ]
    order = {SEV_BLOCKER: 0, SEV_ATTENTION: 1, SEV_INFO: 2}
    for finding in sorted(
        report.findings,
        key=lambda f: (order.get(f.severity, 9), f.asset_class, f.asset_name, f.kind, f.reference),
    ):
        out.append(
            [
                finding.severity,
                finding.asset_class,
                finding.asset_name,
                finding.asset_id,
                finding.location,
                finding.kind,
                finding.reference,
                finding.breaks,
            ]
        )
    return out
