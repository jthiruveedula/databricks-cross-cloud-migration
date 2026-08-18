"""Business ownership & criticality enrichment for wave planning.

``waveplan.py`` scores clusters on criticality, risk tolerance, data size,
and owner readiness -- none of which the toolkit can observe from workspace
metadata. Today an unscored cluster silently defaults to 1 (safest) on every
factor, which is correct only because no better information was supplied --
that is not the same thing as "reviewed and confirmed low risk". This module
makes the gap visible instead of quiet: it reads a human-supplied ownership
mapping (CSV or YAML) and reports, by name, every asset with no entry in it,
so an unowned tier-1 system cannot slide through wave 1 unnoticed.
"""

from __future__ import annotations

import csv
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import yaml

#: 1 (lowest) - 4 (highest), matching the RTO/RPO tiers a DR runbook would use.
MIN_TIER = 1
MAX_TIER = 4


@dataclass(frozen=True)
class OwnershipRecord:
    asset_label: str
    business_owner: str = ""
    technical_owner: str = ""
    domain: str = ""
    classification: str = ""
    criticality_tier: int = MIN_TIER
    rto_minutes: Optional[int] = None
    rpo_minutes: Optional[int] = None
    downstream_consumer_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _int_or(row: Mapping[str, Any], key: str, default: Any) -> Any:
    value = row.get(key)
    if value in (None, ""):
        return default
    return int(value)


def _coerce(row: Mapping[str, Any]) -> OwnershipRecord:
    tier = _int_or(row, "criticality_tier", MIN_TIER)
    return OwnershipRecord(
        asset_label=str(row["asset_label"]),
        business_owner=str(row.get("business_owner", "")),
        technical_owner=str(row.get("technical_owner", "")),
        domain=str(row.get("domain", "")),
        classification=str(row.get("classification", "")),
        criticality_tier=max(MIN_TIER, min(MAX_TIER, tier)),
        rto_minutes=_int_or(row, "rto_minutes", None),
        rpo_minutes=_int_or(row, "rpo_minutes", None),
        downstream_consumer_count=_int_or(row, "downstream_consumer_count", 0),
    )


def load_ownership(path: str) -> Dict[str, OwnershipRecord]:
    """Load an ``asset_label -> ownership metadata`` mapping from CSV or YAML.

    CSV: one row per asset, header includes ``asset_label`` plus any subset
    of the other ``OwnershipRecord`` fields. YAML: a mapping of
    ``asset_label`` to a dict of the same fields. Labels match
    ``CrossRefReport.all_asset_labels()``'s ``"asset_class:name"`` format.
    """
    ext = os.path.splitext(path)[1].lower()
    records: Dict[str, OwnershipRecord] = {}
    if ext in (".yaml", ".yml"):
        with open(path, "r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
        for label, fields in raw.items():
            row = dict(fields or {})
            row["asset_label"] = label
            records[label] = _coerce(row)
    else:
        with open(path, "r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                record = _coerce(row)
                records[record.asset_label] = record
    return records


def unowned(all_labels: Iterable[str], ownership: Mapping[str, OwnershipRecord]) -> List[str]:
    """Every asset label with no ownership entry -- flagged, never defaulted."""
    return sorted(label for label in set(all_labels) if label not in ownership)


def cluster_manual_scores(
    clusters: Sequence[Sequence[str]], ownership: Mapping[str, OwnershipRecord]
) -> Dict[str, Dict[str, int]]:
    """Derive ``waveplan.build_wave_plan``'s ``manual_scores`` from ownership.

    A cluster's criticality is its highest-tier member -- the worst case in
    the group, since shared-reference clustering already forbids splitting it
    across waves. A cluster with no owned member at all is left out entirely
    (see ``unowned`` for surfacing that gap on its own) rather than scored
    from nothing.
    """
    scores: Dict[str, Dict[str, int]] = {}
    for cluster in clusters:
        members = list(cluster)
        if not members:
            continue
        records = [ownership[m] for m in members if m in ownership]
        if not records:
            continue
        entry: Dict[str, int] = {"criticality": max(r.criticality_tier for r in records)}
        consumers = max((r.downstream_consumer_count for r in records), default=0)
        if consumers:
            entry["dependency_count"] = min(5, max(1, consumers))
        scores[members[0]] = entry
    return scores


def cluster_domains(
    clusters: Sequence[Sequence[str]], ownership: Mapping[str, OwnershipRecord]
) -> Dict[str, List[str]]:
    """Distinct domains touched by each cluster.

    More than one means the cluster's shared reference crosses a domain
    boundary -- worth a second look before scheduling, since it means two
    different teams' assets are locked into the same wave together.
    """
    domains: Dict[str, List[str]] = {}
    for cluster in clusters:
        members = list(cluster)
        if not members:
            continue
        found = sorted(
            {ownership[m].domain for m in members if m in ownership and ownership[m].domain}
        )
        domains[members[0]] = found
    return domains
