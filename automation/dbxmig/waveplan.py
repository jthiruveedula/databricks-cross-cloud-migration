"""Turn the shared-references signal into an actual wave plan.

[Wave planning](/execution/wave-planning) calls the shared-references table
from ``dbxmig crossrefs`` "the wave-planning signal" and describes a
five-factor weighted scoring model for assigning dependency-chain clusters to
waves -- but until this module, nothing in the toolkit consumed either one.
The clustering and scoring were both left as manual work.

This closes half of that gap deterministically (clustering, scoring
mechanics, threshold assignment) and leaves the other half explicit rather
than fabricated: business criticality, risk tolerance, data size, and owner
readiness are organizational judgment calls this toolkit cannot observe from
workspace metadata. They are accepted as an optional manual-scores input;
any cluster without one gets the lowest (safest) score on every unscored
factor rather than a silently invented number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

#: Weights and factor names mirror wave-planning.mdx's scoring model exactly:
#: score = 0.30*criticality + 0.25*dependency_count + 0.20*risk_tolerance
#:       + 0.15*data_size + 0.10*owner_readiness
WEIGHTS: Dict[str, float] = {
    "criticality": 0.30,
    "dependency_count": 0.25,
    "risk_tolerance": 0.20,
    "data_size": 0.15,
    "owner_readiness": 0.10,
}

#: (score ceiling, wave) pairs, exclusive on the ceiling -- matches the
#: worked example's "score < 2.0 -> Wave 1, 2.0-3.5 -> Wave 2, > 3.5 -> Wave 3".
DEFAULT_THRESHOLDS: Tuple[Tuple[float, int], ...] = ((2.0, 1), (3.5, 2), (float("inf"), 3))


def cluster_assets(
    shared_references: Mapping[str, Sequence[str]],
    all_assets: Optional[Iterable[str]] = None,
) -> List[List[str]]:
    """Union-find over the shared-references table into dependency-chain clusters.

    Two assets that share a cluster policy, secret scope, or storage prefix
    cannot be split across waves without the earlier wave depending on
    something the later one owns -- so they belong in the same cluster no
    matter how many *other* references separate them. ``all_assets``, if
    given, adds every asset with zero shared references as its own
    one-member cluster instead of leaving it out of the plan entirely.
    """
    parent: Dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for holders in shared_references.values():
        for holder in holders:
            find(holder)
        for holder in holders[1:]:
            union(holders[0], holder)

    for asset in all_assets or []:
        find(asset)

    groups: Dict[str, List[str]] = {}
    for asset in parent:
        groups.setdefault(find(asset), []).append(asset)
    return [sorted(members) for members in sorted(groups.values(), key=lambda m: (-len(m), m))]


@dataclass
class ClusterScore:
    members: List[str]
    dependency_count: int = 1
    criticality: int = 1
    risk_tolerance: int = 1
    data_size: int = 1
    owner_readiness: int = 1

    @property
    def cluster_id(self) -> str:
        return self.members[0] if self.members else ""

    @property
    def weighted_score(self) -> float:
        return (
            WEIGHTS["criticality"] * self.criticality
            + WEIGHTS["dependency_count"] * self.dependency_count
            + WEIGHTS["risk_tolerance"] * self.risk_tolerance
            + WEIGHTS["data_size"] * self.data_size
            + WEIGHTS["owner_readiness"] * self.owner_readiness
        )


def score_clusters(
    clusters: Sequence[Sequence[str]],
    manual_scores: Optional[Mapping[str, Mapping[str, int]]] = None,
) -> List[ClusterScore]:
    """Score each cluster on the wave-planning formula.

    ``dependency_count`` (1-5) defaults from cluster size -- the one factor
    the toolkit can actually observe, since more members sharing a reference
    means more cross-references to reason about. It can still be overridden
    manually, since raw member count is a proxy, not the real thing.
    ``manual_scores`` is keyed by a cluster's id (its alphabetically-lowest
    member); an unscored cluster defaults to 1 -- lowest, i.e. earliest-wave
    -- on every factor rather than inflating its score with a guess.
    """
    manual_scores = manual_scores or {}
    scores: List[ClusterScore] = []
    for cluster in clusters:
        members = list(cluster)
        cluster_id = members[0] if members else ""
        overrides = manual_scores.get(cluster_id, {})
        default_dependency_count = min(5, max(1, len(members)))
        scores.append(
            ClusterScore(
                members=members,
                dependency_count=int(overrides.get("dependency_count", default_dependency_count)),
                criticality=int(overrides.get("criticality", 1)),
                risk_tolerance=int(overrides.get("risk_tolerance", 1)),
                data_size=int(overrides.get("data_size", 1)),
                owner_readiness=int(overrides.get("owner_readiness", 1)),
            )
        )
    return scores


def assign_wave(score: float, thresholds: Sequence[Tuple[float, int]] = DEFAULT_THRESHOLDS) -> int:
    """Higher score = later wave -- harder-to-get-wrong clusters go after tooling is proven."""
    for ceiling, wave in thresholds:
        if score < ceiling:
            return wave
    return thresholds[-1][1]


@dataclass
class WavePlan:
    clusters: List[ClusterScore] = field(default_factory=list)
    thresholds: Tuple[Tuple[float, int], ...] = DEFAULT_THRESHOLDS

    def by_wave(self) -> Dict[int, List[ClusterScore]]:
        out: Dict[int, List[ClusterScore]] = {}
        for cluster in self.clusters:
            wave = assign_wave(cluster.weighted_score, self.thresholds)
            out.setdefault(wave, []).append(cluster)
        for wave in out:
            out[wave].sort(key=lambda c: c.weighted_score)
        return out


def build_wave_plan(
    shared_references: Mapping[str, Sequence[str]],
    manual_scores: Optional[Mapping[str, Mapping[str, int]]] = None,
    all_assets: Optional[Iterable[str]] = None,
    thresholds: Tuple[Tuple[float, int], ...] = DEFAULT_THRESHOLDS,
) -> WavePlan:
    clusters = cluster_assets(shared_references, all_assets=all_assets)
    scores = score_clusters(clusters, manual_scores)
    return WavePlan(clusters=scores, thresholds=thresholds)
