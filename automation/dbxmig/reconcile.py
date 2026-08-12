"""Post-migration reconciliation checks.

Reconciliation is the gate between "the migration ran" and "the migration
worked". The checks here encode the rules the runbook states in prose:

* Row counts and schemas must match exactly.
* Object counts must match -- the cheapest way to catch a whole schema that
  never got migrated.
* Delta history must **not** be compared row-for-row. ``CLONE`` never copies
  source history, so a target whose history starts at its own CLONE operation
  is correct. What must be checked is *provenance*: that the last operation is
  a CLONE naming the right source, and not a CTAS or a raw file sync.

Every check returns a ``Finding`` with a severity. Severity 1 blocks cutover.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .models import Column, Inventory

SEV_BLOCKER = 1
SEV_WARNING = 2
SEV_INFO = 3


@dataclass(frozen=True)
class Finding:
    check: str
    obj: str
    severity: int
    detail: str

    @property
    def blocking(self) -> bool:
        return self.severity == SEV_BLOCKER


@dataclass
class ReconciliationReport:
    findings: List[Finding] = field(default_factory=list)
    checked: int = 0

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    @property
    def blockers(self) -> List[Finding]:
        return [f for f in self.findings if f.blocking]

    @property
    def passed(self) -> bool:
        return not self.blockers

    def exit_code(self) -> int:
        return 0 if self.passed else 1

    def summary(self) -> Dict[str, int]:
        counts = {"checked": self.checked, "findings": len(self.findings)}
        for finding in self.findings:
            key = "severity_{0}".format(finding.severity)
            counts[key] = counts.get(key, 0) + 1
        return counts


def compare_row_counts(
    obj: str, source_count: int, target_count: int, tolerance_rows: int = 0
) -> Optional[Finding]:
    delta = abs(source_count - target_count)
    if delta <= tolerance_rows:
        return None
    return Finding(
        check="row_count",
        obj=obj,
        severity=SEV_BLOCKER,
        detail="source={0} target={1} delta={2}".format(source_count, target_count, delta),
    )


def compare_schemas(obj: str, source: Sequence[Column], target: Sequence[Column]) -> List[Finding]:
    """Column-set, type, nullability, and ordering comparison.

    Ordering is a warning rather than a blocker: it breaks positional
    ``INSERT``s and some BI extracts, but does not by itself mean the data is
    wrong.
    """
    findings: List[Finding] = []
    source_index = {c.name: c for c in source}
    target_index = {c.name: c for c in target}

    for name in sorted(set(source_index) - set(target_index)):
        findings.append(
            Finding("schema_missing_column", obj, SEV_BLOCKER, "column absent in target: " + name)
        )
    for name in sorted(set(target_index) - set(source_index)):
        findings.append(
            Finding("schema_extra_column", obj, SEV_BLOCKER, "column only in target: " + name)
        )
    for name in sorted(set(source_index) & set(target_index)):
        src, tgt = source_index[name], target_index[name]
        if _normalise_type(src.type_text) != _normalise_type(tgt.type_text):
            findings.append(
                Finding(
                    "schema_type_mismatch",
                    obj,
                    SEV_BLOCKER,
                    "{0}: source={1} target={2}".format(name, src.type_text, tgt.type_text),
                )
            )
        if src.nullable != tgt.nullable:
            findings.append(
                Finding(
                    "schema_nullability_mismatch",
                    obj,
                    SEV_BLOCKER,
                    "{0}: source nullable={1} target nullable={2}".format(
                        name, src.nullable, tgt.nullable
                    ),
                )
            )
        if src.position != tgt.position:
            findings.append(
                Finding(
                    "schema_column_order",
                    obj,
                    SEV_WARNING,
                    "{0}: source position={1} target position={2}".format(
                        name, src.position, tgt.position
                    ),
                )
            )
    return findings


def _normalise_type(type_text: str) -> str:
    return (type_text or "").strip().upper().replace(" ", "")


def check_clone_provenance(
    obj: str,
    history_rows: Sequence[Dict[str, Any]],
    expected_source: str,
) -> List[Finding]:
    """Verify the target table was produced by a CLONE of the right source.

    ``history_rows`` is ``DESCRIBE HISTORY`` output, newest first. A target
    whose newest operation is ``WRITE``/``CREATE TABLE AS SELECT``/``STREAMING
    UPDATE`` was not cloned -- it was copied some other way, and its Delta log
    may not agree with its data files.
    """
    if not history_rows:
        return [Finding("clone_provenance", obj, SEV_BLOCKER, "target has no Delta history")]
    newest = history_rows[0]
    operation = str(newest.get("operation", "")).upper()
    if "CLONE" not in operation:
        return [
            Finding(
                "clone_provenance",
                obj,
                SEV_BLOCKER,
                "newest operation is {0}, expected CLONE -- target was not produced by "
                "DEEP CLONE".format(operation or "<none>"),
            )
        ]
    parameters = newest.get("operationParameters") or {}
    referenced = str(parameters.get("source") or parameters.get("sourceTable") or "")
    if expected_source and expected_source.lower() not in referenced.lower():
        return [
            Finding(
                "clone_provenance",
                obj,
                SEV_BLOCKER,
                "CLONE source is {0!r}, expected {1!r}".format(referenced, expected_source),
            )
        ]
    return []


def compare_object_counts(source: Inventory, target: Inventory) -> List[Finding]:
    """Whole-estate completeness check. Catches an entire schema that never ran."""
    findings: List[Finding] = []
    source_counts = source.counts()
    target_counts = target.counts()
    for key in sorted(set(source_counts) | set(target_counts)):
        src = source_counts.get(key, 0)
        tgt = target_counts.get(key, 0)
        if src == tgt:
            continue
        # Materialized views and streaming tables are recreated by pipelines and
        # legitimately appear later than the bulk run, so they warn rather than block.
        severity = (
            SEV_WARNING
            if key in ("tables_materialized_view", "tables_streaming_table")
            else SEV_BLOCKER
        )
        findings.append(
            Finding(
                "object_count",
                key,
                severity,
                "source={0} target={1} missing={2}".format(src, tgt, src - tgt),
            )
        )
    return findings


def check_unmigrated_locations(target: Inventory, source_prefixes: Iterable[str]) -> List[Finding]:
    """Flag target objects still pointing at source-cloud storage.

    This is the check that catches the failure nobody plans for: a table that
    reconciles perfectly on row count because it is still reading the source
    bucket across the internet.
    """
    prefixes = [p.lower() for p in source_prefixes if p]
    findings: List[Finding] = []
    for table in target.tables:
        location = (table.storage_location or "").lower()
        if location and any(location.startswith(p) for p in prefixes):
            findings.append(
                Finding(
                    "residual_source_path",
                    table.full_name,
                    SEV_BLOCKER,
                    "target table still points at source storage: " + str(table.storage_location),
                )
            )
    for volume in target.volumes:
        location = (volume.storage_location or "").lower()
        if location and any(location.startswith(p) for p in prefixes):
            findings.append(
                Finding(
                    "residual_source_path",
                    volume.full_name,
                    SEV_BLOCKER,
                    "target volume still points at source storage: " + str(volume.storage_location),
                )
            )
    return findings


def reconcile_inventories(
    source: Inventory,
    target: Inventory,
    source_prefixes: Optional[Iterable[str]] = None,
) -> ReconciliationReport:
    """Metadata-only reconciliation: counts, schemas, and residual source paths.

    Row counts and clone provenance need a live warehouse; they are driven by
    the CLI's ``reconcile`` command against a gateway, using the helpers above.
    """
    report = ReconciliationReport()
    report.findings.extend(compare_object_counts(source, target))
    if source_prefixes:
        report.findings.extend(check_unmigrated_locations(target, source_prefixes))

    target_index = target.table_index()
    for table in source.tables:
        report.checked += 1
        candidate = target_index.get(table.full_name)
        if candidate is None:
            # Fall back to matching on schema+name, which survives a catalog rename.
            matches = [
                t
                for t in target.tables
                if t.schema == table.schema and t.name == table.name
            ]
            candidate = matches[0] if len(matches) == 1 else None
        if candidate is None:
            report.add(
                Finding("missing_object", table.full_name, SEV_BLOCKER, "not present in target")
            )
            continue
        report.findings.extend(compare_schemas(table.full_name, table.columns, candidate.columns))
    return report
