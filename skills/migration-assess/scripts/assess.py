#!/usr/bin/env python3
"""Assess a codebase for Databricks cross-cloud migration readiness.

Deterministic regex scan over source files -- no LLM call, no dependency
beyond the standard library, so it runs anywhere the agent runs. The agent
reads this script's compact report, not the raw codebase: the same
token-saving shape as `dbxmig crossrefs`/`gaps` in the companion runbook
(https://github.com/jthiruveedula/databricks-cross-cloud-migration), whose
cloud-identity patterns this script mirrors.

Usage:
    python3 assess.py [path] [--format json|markdown] [-o out.md]

Exit code is 1 when findings exist (an intentional CI gate, matching
dbxmig's own convention), 0 otherwise.
"""

from __future__ import annotations

import argparse
import bisect
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Sequence, Tuple

# ---------------------------------------------------------------------------
# File walk -- mirrors dbxmig/crossrefs.py's SOURCE_EXTENSIONS/SKIP_DIRS/
# MAX_FILE_BYTES exactly, so a finding here and a finding from that toolkit
# never disagree about what counts as "source" in the same estate.
# ---------------------------------------------------------------------------

SOURCE_EXTENSIONS = (
    ".py", ".sql", ".scala", ".r", ".ipynb", ".json", ".yml", ".yaml", ".sh", ".conf", ".tf",
)
SKIP_DIRS = frozenset(
    {".git", "node_modules", ".venv", "venv", "__pycache__", ".terraform", "dist", "build"}
)
MAX_FILE_BYTES = 2_000_000


def walk_source(root: str) -> Iterable[Tuple[str, str]]:
    """Yield (path, text) for every source file under root, skip the rest."""
    for dirpath, subdirs, filenames in os.walk(root):
        subdirs[:] = [d for d in subdirs if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if not name.endswith(SOURCE_EXTENSIONS):
                continue
            path = os.path.join(dirpath, name)
            try:
                if os.path.getsize(path) > MAX_FILE_BYTES:
                    continue
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    yield path, handle.read()
            except OSError:
                continue


# ---------------------------------------------------------------------------
# Categories. Each is (regex, category, migration_kind, recommended_tool, why).
# migration_kind buckets a codebase into what it's actually doing, so the
# report can point at the one accelerator that matches -- not a generic list.
# ---------------------------------------------------------------------------

METADATA_MIGRATION = "metadata/table migration"
JOB_MIGRATION = "job/workflow migration"
DATA_VALIDATION = "data validation"
ML_MIGRATION = "MLflow/model registry migration"

# Cloud-identity patterns copied verbatim from dbxmig/crossrefs.py -- the same
# ones that toolkit uses to flag cross-cloud identity blockers, so a finding
# here and a `dbxmig crossrefs` finding never drift apart.
_AWS_INSTANCE_PROFILE = re.compile(r"arn:aws:iam::\d{12}:instance-profile/[A-Za-z0-9+=,.@_\-/]+")
_AZURE_MANAGED_IDENTITY = re.compile(
    r"/subscriptions/[0-9a-f-]+/resourcegroups/[^/\s'\"]+/providers/"
    r"Microsoft\.ManagedIdentity/userAssignedIdentities/[^\s'\"]+",
    re.IGNORECASE,
)
_GCP_SERVICE_ACCOUNT = re.compile(r"[a-z0-9-]+@[a-z0-9-]+\.iam\.gserviceaccount\.com")

CHECKS: Tuple[Tuple[re.Pattern, str, str, str, str], ...] = (
    (
        re.compile(r"(?:dbfs:)?/dbfs/[A-Za-z0-9._\-/]+|dbfs:/[A-Za-z0-9._\-/]+"),
        "dbfs-path",
        METADATA_MIGRATION,
        "dbxmig gaps / governance/external-locations-and-volumes",
        "DBFS-root paths aren't governed by Unity Catalog and don't carry across clouds -- "
        "retarget to a UC volume or external location before migrating.",
    ),
    (
        re.compile(r"\bhive_metastore\.[a-zA-Z0-9_.]+"),
        "legacy-hive-reference",
        METADATA_MIGRATION,
        "governance/ucx-strategy, dbxmig gaps",
        "A hardcoded hive_metastore reference needs the Hive-to-UC upgrade (UCX) before this "
        "code means anything in a UC-native target.",
    ),
    (
        re.compile(r"models:/[^/'\"\s]+/(Production|Staging|Archived|None)\b"),
        "stage-based-model-uri",
        ML_MIGRATION,
        "mlflow-export-import, ml/model-registry",
        "Stages don't exist in Unity Catalog's model registry -- this URI breaks on a UC-native "
        "target and needs rewriting to a catalog.schema.model + alias form.",
    ),
    (
        re.compile(r"\brun\.data\.metrics\b(?!.*get_metric_history)"),
        "mlflow-metric-history-truncation",
        ML_MIGRATION,
        "mlflow-export-import, ml/mlflow",
        "run.data.metrics is the LATEST value per key, not the series -- re-logging from it "
        "silently drops every training curve to one point.",
    ),
    (
        re.compile(r"\.search_runs\s*\("),
        "mlflow-search-runs-pagination",
        ML_MIGRATION,
        "mlflow-export-import, ml/mlflow",
        "search_runs caps at 1000 results by default -- confirm this call pages via page_token "
        "or a >1000-run experiment silently migrates only its first page.",
    ),
    (
        re.compile(r"databricks\s+jobs\s+(list|create)\b"),
        "manual-job-cli-loop",
        JOB_MIGRATION,
        "Terraform Exporter, bundle-init, pipelines/workflows-jobs",
        "A per-job CLI export/import loop is the fallback path, not the fast one, past a "
        "handful of jobs -- see the bulk Terraform Exporter / bundle-init path.",
    ),
    (
        re.compile(
            r"\b(i3\.[a-z0-9]+|m5\.[a-z0-9]+|r5\.[a-z0-9]+"
            r"|Standard_[A-Z0-9_]+|n1-standard-\d+|n2-standard-\d+|e2-standard-\d+)\b"
        ),
        "hardcoded-node-type",
        JOB_MIGRATION,
        "Terraform Exporter (-targetCloud/-nodeTypeMappingFile), cloud-mappings",
        "A cloud-specific instance type hardcoded in cluster config needs cross-cloud "
        "translation -- the Exporter's -nodeTypeMappingFile automates most of this.",
    ),
    (_AWS_INSTANCE_PROFILE, "cloud-identity-aws", METADATA_MIGRATION,
     "dbxmig crossrefs --target-cloud", "AWS instance profile -- blocks a non-AWS target."),
    (_AZURE_MANAGED_IDENTITY, "cloud-identity-azure", METADATA_MIGRATION,
     "dbxmig crossrefs --target-cloud", "Azure managed identity -- blocks a non-Azure target."),
    (_GCP_SERVICE_ACCOUNT, "cloud-identity-gcp", METADATA_MIGRATION,
     "dbxmig crossrefs --target-cloud", "GCP service account -- blocks a non-GCP target."),
    (
        re.compile(r"\bassert\s+\w*count\w*\s*==\s*\w*count\w*|SELECT\s+COUNT\(\*\)"),
        "hand-rolled-row-count-check",
        DATA_VALIDATION,
        "databrickslabs/lakebridge Reconcile, validation/data-reconciliation",
        "A hand-written row-count assertion is a fallback, not the fast path -- Lakebridge "
        "Reconcile does row/schema/aggregate checks with sampling built in.",
    ),
)


@dataclass
class Finding:
    path: str
    line: int
    category: str
    migration_kind: str
    tool: str
    why: str
    snippet: str


@dataclass
class Report:
    findings: List[Finding] = field(default_factory=list)
    files_scanned: int = 0

    def by_kind(self) -> Dict[str, List[Finding]]:
        out: Dict[str, List[Finding]] = {}
        for f in self.findings:
            out.setdefault(f.migration_kind, []).append(f)
        return out


def _line_starts(text: str) -> List[int]:
    """Byte offset each line starts at, for an O(log n) offset->line lookup
    instead of re-scanning from position 0 for every match (crossrefs.py
    solves the same problem the same way -- this mirrors it)."""
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _line_of(starts: List[int], offset: int) -> int:
    return bisect.bisect_right(starts, offset)


def assess(root: str) -> Report:
    report = Report()
    for path, text in walk_source(root):
        report.files_scanned += 1
        lines = text.splitlines()
        starts = _line_starts(text)
        rel_path = os.path.relpath(path, root)
        for pattern, category, kind, tool, why in CHECKS:
            for match in pattern.finditer(text):
                line_no = _line_of(starts, match.start())
                snippet = lines[line_no - 1].strip()[:160] if line_no <= len(lines) else ""
                report.findings.append(
                    Finding(
                        path=rel_path,
                        line=line_no,
                        category=category,
                        migration_kind=kind,
                        tool=tool,
                        why=why,
                        snippet=snippet,
                    )
                )
    return report


def render_markdown(report: Report) -> str:
    lines = [
        "# Migration assessment",
        "",
        f"Scanned {report.files_scanned} source file(s); {len(report.findings)} finding(s).",
        "",
    ]
    by_kind = report.by_kind()
    if not by_kind:
        lines.append("Nothing flagged -- no known migration blocker pattern matched.")
        return "\n".join(lines) + "\n"

    for kind in sorted(by_kind):
        findings = by_kind[kind]
        tools = sorted({f.tool for f in findings})
        lines.append(f"## {kind} ({len(findings)} finding(s))")
        lines.append("")
        lines.append(f"**Recommended tool(s):** {'; '.join(tools)}")
        lines.append("")
        lines.append("| File | Line | Category | Why |")
        lines.append("|---|---|---|---|")
        for f in sorted(findings, key=lambda f: (f.path, f.line)):
            lines.append(f"| `{f.path}` | {f.line} | {f.category} | {f.why} |")
        lines.append("")
    return "\n".join(lines)


def render_json(report: Report) -> str:
    return json.dumps(
        {"files_scanned": report.files_scanned, "findings": [asdict(f) for f in report.findings]},
        indent=2,
        sort_keys=True,
    )


def main(argv: Sequence[str] = ()) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=".", help="root directory to scan")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("-o", "--out", help="write report here instead of stdout")
    args = parser.parse_args(argv or sys.argv[1:])

    report = assess(args.path)
    content = render_json(report) if args.format == "json" else render_markdown(report)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(content)
    else:
        sys.stdout.write(content if content.endswith("\n") else content + "\n")

    return 1 if report.findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
