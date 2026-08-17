from __future__ import annotations

from dbxmig.waveplan import assign_wave, build_wave_plan, cluster_assets, score_clusters


def test_shared_reference_unions_two_assets_into_one_cluster():
    shared = {"secret_scope=creds": ["job:a", "job:b"]}
    clusters = cluster_assets(shared)
    assert clusters == [["job:a", "job:b"]]


def test_transitive_sharing_merges_three_assets_via_two_references():
    # a shares with b via one reference, b shares with c via another --
    # a and c must still land in the same cluster.
    shared = {
        "secret_scope=creds": ["job:a", "job:b"],
        "cluster_policy=shared_policy": ["job:b", "job:c"],
    }
    clusters = cluster_assets(shared)
    assert clusters == [["job:a", "job:b", "job:c"]]


def test_unrelated_assets_stay_in_separate_clusters():
    shared = {
        "secret_scope=creds_a": ["job:a", "job:b"],
        "secret_scope=creds_c": ["job:c", "job:d"],
    }
    clusters = cluster_assets(shared)
    assert sorted(clusters) == [["job:a", "job:b"], ["job:c", "job:d"]]


def test_all_assets_seeds_singleton_clusters_for_untouched_assets():
    shared = {"secret_scope=creds": ["job:a", "job:b"]}
    clusters = cluster_assets(shared, all_assets=["job:a", "job:b", "job:standalone"])
    assert sorted(clusters) == [["job:a", "job:b"], ["job:standalone"]]


def test_dependency_count_defaults_from_cluster_size():
    clusters = [["job:a", "job:b", "job:c"]]
    scores = score_clusters(clusters)
    assert scores[0].dependency_count == 3
    # every unscored judgment factor defaults to 1, the safest/earliest value
    assert scores[0].criticality == 1
    assert scores[0].risk_tolerance == 1
    assert scores[0].data_size == 1
    assert scores[0].owner_readiness == 1


def test_manual_scores_override_by_cluster_id():
    clusters = [["job:a", "job:b"]]
    manual = {
        "job:a": {"criticality": 5, "risk_tolerance": 5, "data_size": 3, "owner_readiness": 4}
    }
    scores = score_clusters(clusters, manual_scores=manual)
    assert scores[0].criticality == 5
    assert scores[0].owner_readiness == 4


def test_weighted_score_matches_the_documented_formula():
    clusters = [["job:a"]]
    manual = {
        "job:a": {
            "criticality": 5,
            "dependency_count": 4,
            "risk_tolerance": 5,
            "data_size": 3,
            "owner_readiness": 4,
        }
    }
    scores = score_clusters(clusters, manual_scores=manual)
    expected = 0.30 * 5 + 0.25 * 4 + 0.20 * 5 + 0.15 * 3 + 0.10 * 4
    assert scores[0].weighted_score == expected


def test_assign_wave_uses_documented_thresholds():
    assert assign_wave(1.30) == 1
    assert assign_wave(2.0) == 2
    assert assign_wave(3.00) == 2
    assert assign_wave(4.35) == 3


def test_low_score_clusters_land_in_wave_one_by_default():
    shared = {"secret_scope=creds": ["job:a", "job:b"]}
    plan = build_wave_plan(shared)
    by_wave = plan.by_wave()
    # 2-member cluster, unscored on everything else -> low weighted score
    assert 1 in by_wave
    assert by_wave[1][0].members == ["job:a", "job:b"]


def test_high_criticality_cluster_lands_in_a_later_wave():
    shared = {"secret_scope=creds": ["job:a", "job:b"]}
    manual = {
        "job:a": {
            "criticality": 5,
            "risk_tolerance": 5,
            "data_size": 5,
            "owner_readiness": 5,
        }
    }
    plan = build_wave_plan(shared, manual_scores=manual)
    by_wave = plan.by_wave()
    assert 1 not in by_wave
    assert 3 in by_wave


def test_custom_thresholds_are_respected():
    tight = ((1.0, 1), (float("inf"), 2))
    assert assign_wave(1.30, thresholds=tight) == 2
    assert assign_wave(0.90, thresholds=tight) == 1
