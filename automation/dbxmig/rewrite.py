"""Deterministic cross-cloud storage URI and identifier rewriting.

This is the "rule-based core" half of the hybrid pattern the runbook prescribes:
the mechanical 80% is handled here, exactly and repeatably, and only what this
module cannot resolve is escalated -- to a human, or to the gated LLM assist in
``llm.py``. Nothing in this module calls a model or a network.

The single most valuable output is not the rewritten string: it is
``find_unmapped``, which reports source-cloud URIs that *no rule matched*. Those
are the paths that would otherwise be carried into the target verbatim, resolve
against nothing, and surface as a production incident weeks after cutover.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

#: Storage schemes that appear in a Databricks estate. ``dbfs`` is included
#: because legacy mounts (``dbfs:/mnt/...``) are the most common unmapped path
#: found in real inventories, and they must become Volumes or external
#: locations rather than being rewritten to another mount.
URI_SCHEMES = ("abfss", "abfs", "wasbs", "wasb", "s3a", "s3n", "s3", "gs", "dbfs")

_URI_PATTERN = re.compile(
    r"\b(?:" + "|".join(URI_SCHEMES) + r")://[^\s'\"`,;)\]]+"
    r"|\bdbfs:/[^\s'\"`,;)\]]+",
    re.IGNORECASE,
)

_VOLUME_PATTERN = re.compile(r"/Volumes/[A-Za-z0-9_]+/[A-Za-z0-9_]+/[A-Za-z0-9_]+[^\s'\"`,;)\]]*")


@dataclass(frozen=True)
class PathRule:
    """One source-prefix to target-prefix mapping.

    Rules are matched longest-prefix-first, so a specific rule
    (``abfss://data@acct.dfs.core.windows.net/raw/pii/``) always wins over a
    general one (``abfss://data@acct.dfs.core.windows.net/``) regardless of the
    order they were declared in the config.
    """

    source_prefix: str
    target_prefix: str
    note: str = ""

    def matches(self, uri: str) -> bool:
        return uri.lower().startswith(self.source_prefix.lower())

    def apply(self, uri: str) -> str:
        return self.target_prefix + uri[len(self.source_prefix) :]


@dataclass(frozen=True)
class RewriteResult:
    original: str
    value: str
    rule: Optional[PathRule] = None

    @property
    def changed(self) -> bool:
        return self.original != self.value

    @property
    def mapped(self) -> bool:
        return self.rule is not None


@dataclass
class Rewriter:
    """Applies path rules and catalog renames to URIs, SQL, and free text."""

    path_rules: List[PathRule] = field(default_factory=list)
    #: source catalog name -> target catalog name
    catalog_map: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Longest prefix first; ties broken alphabetically so the ordering is
        # stable across runs and machines.
        self.path_rules = sorted(
            self.path_rules,
            key=lambda r: (-len(r.source_prefix), r.source_prefix),
        )

    # ---- URIs -----------------------------------------------------------

    def rewrite_uri(self, uri: str) -> RewriteResult:
        if not uri:
            return RewriteResult(uri, uri, None)
        for rule in self.path_rules:
            if rule.matches(uri):
                return RewriteResult(uri, rule.apply(uri), rule)
        return RewriteResult(uri, uri, None)

    def find_uris(self, text: str) -> List[str]:
        """Every storage URI in a blob of text, in order of appearance, deduped."""
        if not text:
            return []
        found: List[str] = []
        for match in list(_URI_PATTERN.finditer(text)) + list(_VOLUME_PATTERN.finditer(text)):
            value = match.group(0).rstrip(".,;")
            if value not in found:
                found.append(value)
        return found

    def find_unmapped(self, text: str) -> List[str]:
        """URIs in ``text`` that no rule covers.

        A non-empty result is a migration blocker, not a warning: the object
        would land in the target still pointing at source-cloud storage.
        """
        unmapped = []
        for uri in self.find_uris(text):
            if uri.startswith("/Volumes/"):
                # Volume paths are catalog-qualified, not cloud-qualified;
                # they are handled by the catalog rename, not a path rule.
                continue
            if not self.rewrite_uri(uri).mapped:
                unmapped.append(uri)
        return unmapped

    # ---- Identifiers ----------------------------------------------------

    def rewrite_identifiers(self, sql: str) -> str:
        """Rename source catalogs to target catalogs inside SQL text.

        Matches ``catalog.`` and ``` `catalog`. ``` at an identifier boundary so
        that a catalog named ``sales`` does not corrupt a column named
        ``sales_total`` or a string literal containing the word.
        """
        if not sql or not self.catalog_map:
            return sql
        out = sql
        for source, target in sorted(self.catalog_map.items(), key=lambda kv: -len(kv[0])):
            out = re.sub(
                r"(?<![A-Za-z0-9_.`])`?" + re.escape(source) + r"`?(?=\s*\.)",
                target,
                out,
            )
        return out

    # ---- Combined -------------------------------------------------------

    def rewrite_sql(self, sql: str) -> RewriteResult:
        """Rewrite both storage URIs and catalog identifiers in a SQL body."""
        if not sql:
            return RewriteResult(sql, sql, None)
        out = sql
        for uri in self.find_uris(sql):
            result = self.rewrite_uri(uri)
            if result.changed:
                out = out.replace(uri, result.value)
        out = self.rewrite_identifiers(out)
        return RewriteResult(sql, out, None)

    def rewrite_full_name(self, full_name: str) -> str:
        """Map ``src_catalog.schema.table`` onto its target three-part name."""
        parts = full_name.split(".")
        if not parts:
            return full_name
        parts[0] = self.catalog_map.get(parts[0], parts[0])
        return ".".join(parts)


def parse_uri(uri: str) -> Tuple[str, str, str]:
    """Split a storage URI into ``(scheme, container_or_bucket, path)``.

    Handles the three cloud shapes plus legacy DBFS mounts::

        abfss://container@account.dfs.core.windows.net/path -> (abfss, container@account..., /path)
        s3://bucket/path                                    -> (s3, bucket, /path)
        gs://bucket/path                                    -> (gs, bucket, /path)
        dbfs:/mnt/legacy/path                               -> (dbfs, mnt, /legacy/path)
    """
    if not uri:
        return ("", "", "")
    lowered = uri.lower()
    if lowered.startswith("dbfs:/") and not lowered.startswith("dbfs://"):
        remainder = uri[len("dbfs:/") :].lstrip("/")
        head, _, tail = remainder.partition("/")
        return ("dbfs", head, "/" + tail if tail else "/")
    if "://" not in uri:
        return ("", "", uri)
    scheme, _, remainder = uri.partition("://")
    head, _, tail = remainder.partition("/")
    return (scheme.lower(), head, "/" + tail if tail else "/")


def rules_from_config(raw_rules: Iterable[Dict[str, str]]) -> List[PathRule]:
    rules: List[PathRule] = []
    for raw in raw_rules or []:
        source = raw.get("from") or raw.get("source_prefix")
        target = raw.get("to") or raw.get("target_prefix")
        if not source or target is None:
            raise ValueError("path rule needs both 'from' and 'to': {0!r}".format(raw))
        rules.append(PathRule(source, target, raw.get("note", "")))
    return rules


def coverage_report(rewriter: Rewriter, texts: Sequence[Tuple[str, str]]) -> Dict[str, List[str]]:
    """Map ``object name -> unmapped URIs`` across many objects at once.

    ``texts`` is a sequence of ``(object_name, text)`` pairs -- storage
    locations, view bodies, function definitions, job parameters.
    """
    report: Dict[str, List[str]] = {}
    for name, text in texts:
        unmapped = rewriter.find_unmapped(text or "")
        if unmapped:
            report[name] = unmapped
    return report
