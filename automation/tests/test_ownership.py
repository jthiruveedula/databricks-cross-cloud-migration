"""Ownership enrichment: load, unowned flagging, and wave-plan wiring."""

from __future__ import annotations

from dbxmig.ownership import (
    OwnershipRecord,
    cluster_domains,
    cluster_manual_scores,
    load_ownership,
    unowned,
)
from dbxmig.waveplan import build_wave_plan

CSV_CONTENT = (
    "asset_label,business_owner,domain,criticality_tier,downstream_consumer_count\n"
    "job:nightly,priya@acme.com,sales,4,6\n"
    "job:batch,raj@acme.com,finance,2,\n"
)


def test_load_ownership_csv(tmp_path):
    path = tmp_path / "ownership.csv"
    path.write_text(CSV_CONTENT, encoding="utf-8")
    records = load_ownership(str(path))
    assert set(records) == {"job:nightly", "job:batch"}
    assert records["job:nightly"].criticality_tier == 4
    assert records["job:nightly"].downstream_consumer_count == 6
    assert records["job:batch"].downstream_consumer_count == 0


def test_load_ownership_yaml(tmp_path):
    path = tmp_path / "ownership.yaml"
    path.write_text(
        "job:nightly:\n  criticality_tier: 4\n  domain: sales\n"
        "job:batch:\n  criticality_tier: 2\n",
        encoding="utf-8",
    )
    records = load_ownership(str(path))
    assert records["job:nightly"].domain == "sales"
    assert records["job:batch"].criticality_tier == 2


def test_criticality_tier_is_clamped_to_1_4():
    record = OwnershipRecord(asset_label="x", criticality_tier=9)
    # clamping happens in _coerce (the CSV/YAML load path), not the dataclass itself
    from dbxmig.ownership import _coerce

    assert _coerce({"asset_label": "x", "criticality_tier": 9}).criticality_tier == 4
    assert _coerce({"asset_label": "x", "criticality_tier": 0}).criticality_tier == 1
    assert record.criticality_tier == 9  # direct construction is not clamped


def test_unowned_flags_assets_missing_from_the_mapping():
    ownership = {"job:a": OwnershipRecord(asset_label="job:a")}
    assert unowned(["job:a", "job:b", "job:c"], ownership) == ["job:b", "job:c"]


def test_cluster_manual_scores_takes_the_worst_case_tier_in_the_cluster():
    ownership = {
        "job:a": OwnershipRecord(
            asset_label="job:a", criticality_tier=2, downstream_consumer_count=3
        ),
        "job:b": OwnershipRecord(asset_label="job:b", criticality_tier=4),
    }
    scores = cluster_manual_scores([["job:a", "job:b"]], ownership)
    assert scores["job:a"] == {"criticality": 4, "dependency_count": 3}


def test_cluster_manual_scores_skips_clusters_with_no_owned_member():
    scores = cluster_manual_scores([["job:unowned"]], {})
    assert scores == {}


def test_cluster_domains_lists_distinct_domains_touched():
    ownership = {
        "job:a": OwnershipRecord(asset_label="job:a", domain="sales"),
        "job:b": OwnershipRecord(asset_label="job:b", domain="finance"),
    }
    domains = cluster_domains([["job:a", "job:b"]], ownership)
    assert domains["job:a"] == ["finance", "sales"]


def test_build_wave_plan_uses_ownership_as_default_but_explicit_scores_win():
    ownership = {"job:a": OwnershipRecord(asset_label="job:a", criticality_tier=4, domain="sales")}
    shared = {"secret=x": ["job:a", "job:b"]}

    plan_from_ownership = build_wave_plan(shared, ownership=ownership)
    cluster = plan_from_ownership.clusters[0]
    assert cluster.criticality == 4
    assert cluster.domains == ["sales"]

    plan_with_override = build_wave_plan(
        shared, manual_scores={"job:a": {"criticality": 1}}, ownership=ownership
    )
    assert plan_with_override.clusters[0].criticality == 1
