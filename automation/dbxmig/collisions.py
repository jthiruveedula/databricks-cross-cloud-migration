"""Preflight: what already exists in the target under the names we intend to create.

Every ``CREATE`` this toolkit emits is idempotent -- ``IF NOT EXISTS`` throughout.
That makes re-runs and resumes safe, and it makes collisions *invisible*. Those
are the same property, and on a shared target metastore the second one is a
liability.

A Unity Catalog metastore is one per region per Databricks account, so any other
team migrating into the same target region lands in the same three-level
namespace. There is no second metastore in the region to escape into. Two
consequences the rest of the toolkit could not see before this module existed:

* ``CREATE CATALOG IF NOT EXISTS prod`` against *their* ``prod`` succeeds. The
  migration then proceeds inside another team's governance boundary, under their
  owner and their grants, and every later step reports success.

* ``CREATE TABLE IF NOT EXISTS`` against an existing target table is a no-op. The
  table does not migrate, ``apply`` still reports success, and the omission
  surfaces only if someone reconciles row counts afterwards.

Both are the failure shape this toolkit exists to refuse: not an error, an
*absence* that reports as fine. So collisions are computed before anything is
generated, and an owner mismatch is fatal rather than advisory.

This is a preflight over two inventories. It runs offline and executes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from .models import Inventory
from .rewrite import Rewriter

FATAL = "fatal"
WARN = "warn"

#: Object kinds in the order a reader should be shown them -- broadest blast
#: radius first, because a catalog collision makes every finding under it moot.
_KIND_ORDER = ("catalog", "schema", "table", "volume", "external_location")


@dataclass(frozen=True)
class Collision:
    """One target object that already exists under a name the plan would create."""

    kind: str
    target_name: str
    severity: str
    reason: str
    source_name: Optional[str] = None
    target_owner: Optional[str] = None

    def sort_key(self) -> tuple:
        kind_rank = _KIND_ORDER.index(self.kind) if self.kind in _KIND_ORDER else len(_KIND_ORDER)
        return (0 if self.severity == FATAL else 1, kind_rank, self.target_name)


@dataclass(frozen=True)
class CollisionReport:
    collisions: Sequence[Collision]

    @property
    def fatal(self) -> List[Collision]:
        return [c for c in self.collisions if c.severity == FATAL]

    @property
    def warnings(self) -> List[Collision]:
        return [c for c in self.collisions if c.severity == WARN]

    def __bool__(self) -> bool:
        return bool(self.collisions)


def _same_principal(a: Optional[str], b: Optional[str]) -> bool:
    """Owner comparison that treats unknown as *not* a match.

    An absent owner on either side means we cannot prove the object is ours, and
    the safe reading of "cannot prove" is to make the operator look.
    """
    if not a or not b:
        return False
    return a.strip().lower() == b.strip().lower()


def _owner_verdict(kind: str, target_name: str, source_owner, target_owner, source_name):
    """Shared classification for the owned securables (catalog, schema, volume)."""
    if _same_principal(source_owner, target_owner):
        return Collision(
            kind=kind,
            target_name=target_name,
            severity=WARN,
            reason=(
                "already exists and is owned by the same principal -- consistent with a "
                "resumed or re-run migration, but confirm before continuing"
            ),
            source_name=source_name,
            target_owner=target_owner,
        )
    return Collision(
        kind=kind,
        target_name=target_name,
        severity=FATAL,
        reason=(
            "already exists in the target under a different owner ({0}). CREATE ... "
            "IF NOT EXISTS will succeed silently and this migration will land inside "
            "an object it does not own".format(target_owner or "unknown")
        ),
        source_name=source_name,
        target_owner=target_owner,
    )


def _normalize_url(url: str) -> str:
    return url.rstrip("/").lower()


def _overlaps(a: str, b: str) -> bool:
    """True when two external-location URLs are the same or nested.

    Unity Catalog rejects a new external location whose URL overlaps an existing
    one, so a nested path is a hard failure at apply time, not a warning.
    """
    a, b = _normalize_url(a), _normalize_url(b)
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def detect(
    source: Inventory,
    target: Inventory,
    rewriter: Rewriter,
    catalog_map: Optional[Dict[str, str]] = None,
) -> CollisionReport:
    """Compare intended target names against what the target metastore already holds."""
    catalog_map = catalog_map or {}
    found: List[Collision] = []

    target_catalogs = {c.name.lower(): c for c in target.catalogs}
    target_schemas = {s.full_name.lower(): s for s in target.schemas}
    target_tables = {t.full_name.lower(): t for t in target.tables}
    target_volumes = {v.full_name.lower(): v for v in target.volumes}

    for catalog in source.catalogs:
        name = catalog_map.get(catalog.name, catalog.name)
        existing = target_catalogs.get(name.lower())
        if existing is not None:
            found.append(
                _owner_verdict("catalog", name, catalog.owner, existing.owner, catalog.name)
            )

    for schema in source.schemas:
        name = rewriter.rewrite_full_name(schema.full_name)
        existing = target_schemas.get(name.lower())
        if existing is not None:
            found.append(
                _owner_verdict("schema", name, schema.owner, existing.owner, schema.full_name)
            )

    # Tables are not an ownership question. An existing target table means the
    # emitted CREATE TABLE IF NOT EXISTS is a no-op, so the table simply does not
    # migrate -- and apply reports success either way.
    for table in source.tables:
        name = rewriter.rewrite_full_name(table.full_name)
        existing = target_tables.get(name.lower())
        if existing is None:
            continue
        found.append(
            Collision(
                kind="table",
                target_name=name,
                severity=FATAL,
                reason=(
                    "a table already exists at this name. CREATE TABLE IF NOT EXISTS is a "
                    "no-op against it, so this table would not migrate and apply would "
                    "still report success"
                ),
                source_name=table.full_name,
                target_owner=existing.owner,
            )
        )

    for volume in source.volumes:
        name = rewriter.rewrite_full_name(volume.full_name)
        existing = target_volumes.get(name.lower())
        if existing is not None:
            found.append(
                _owner_verdict("volume", name, volume.owner, existing.owner, volume.full_name)
            )

    # External locations collide on URL as well as on name: UC refuses a location
    # whose path overlaps an existing one, whatever it is called.
    for location in source.external_locations:
        rewritten = rewriter.rewrite_uri(location.url)
        if not rewritten.mapped:
            continue
        for existing in target.external_locations:
            if not _overlaps(rewritten.value, existing.url):
                continue
            same_name = existing.name.lower() == location.name.lower()
            exact = _normalize_url(rewritten.value) == _normalize_url(existing.url)
            if same_name and exact:
                reason = "already exists with the same name and URL -- consistent with a re-run"
                severity = WARN
            else:
                reason = (
                    "target URL overlaps external location {0!r} ({1}). Unity Catalog "
                    "rejects overlapping external locations, so this CREATE fails at "
                    "apply time".format(existing.name, existing.url)
                )
                severity = FATAL
            found.append(
                Collision(
                    kind="external_location",
                    target_name=location.name,
                    severity=severity,
                    reason=reason,
                    source_name=location.url,
                    target_owner=None,
                )
            )
            break

    found.sort(key=lambda c: c.sort_key())
    return CollisionReport(collisions=tuple(found))


def render(report: CollisionReport) -> str:
    """Markdown for the gap report and for stdout."""
    lines = ["## Target collisions", ""]
    if not report.collisions:
        lines.append(
            "No object in the target metastore uses a name this migration intends to "
            "create. Note this is only true of the target inventory as captured -- "
            "re-run the check if another team migrates into the region before cutover."
        )
        lines.append("")
        return "\n".join(lines)

    lines.append(
        "A Unity Catalog metastore is shared by every workspace in its region, so these "
        "names are already taken by something. Every `CREATE` this toolkit emits is "
        "`IF NOT EXISTS`, which means none of these would raise an error at apply time."
    )
    lines.append("")
    lines.append("| Severity | Kind | Target name | Why it matters |")
    lines.append("|---|---|---|---|")
    for c in report.collisions:
        marker = "**FATAL**" if c.severity == FATAL else "warn"
        lines.append(
            "| {0} | {1} | `{2}` | {3} |".format(
                marker, c.kind.replace("_", " "), c.target_name, c.reason
            )
        )
    lines.append("")
    if report.fatal:
        lines.append(
            "Resolve every FATAL row before generating DDL. For a catalog or schema owned "
            "by another team, the fix is a naming convention agreed at the account level, "
            "not a rename after the fact: renaming a catalog breaks every fully-qualified "
            "reference in every notebook, job, view definition, and grant that names it."
        )
        lines.append("")
    return "\n".join(lines)
