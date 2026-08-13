"""The preflight has to catch what IF NOT EXISTS hides.

Each test here is a scenario the rest of the toolkit reports as a clean success.
"""

from __future__ import annotations

import pytest

from dbxmig.collisions import FATAL, WARN, detect, render
from dbxmig.models import Inventory


def _target(**overrides) -> Inventory:
    """A target metastore holding whatever the scenario needs, and nothing else."""
    base = {
        "metastore_id": "99999999-0000-0000-0000-000000000000",
        "metastore_name": "prod-us-central1",
        "cloud": "gcp",
        "region": "us-central1",
        "catalogs": [],
        "schemas": [],
        "tables": [],
        "volumes": [],
        "external_locations": [],
    }
    base.update(overrides)
    return Inventory.from_dict(base)


def test_empty_target_has_no_collisions(inventory, config):
    report = detect(inventory, _target(), config.rewriter(), config.catalog_map)
    assert not report
    assert "No object in the target metastore" in render(report)


def test_catalog_owned_by_another_team_is_fatal(inventory, config):
    """The scenario the module exists for: their prod_gcp absorbs our migration."""
    target = _target(catalogs=[{"name": "prod_gcp", "owner": "warehouse-team"}])
    report = detect(inventory, target, config.rewriter(), config.catalog_map)

    assert len(report.fatal) == 1
    hit = report.fatal[0]
    assert hit.kind == "catalog"
    assert hit.target_name == "prod_gcp"
    assert hit.target_owner == "warehouse-team"
    assert "does not own" in hit.reason


def test_catalog_owned_by_us_is_only_a_warning(inventory, config):
    """Same owner reads as a resumed run, which is legitimate but worth confirming."""
    target = _target(catalogs=[{"name": "prod_gcp", "owner": "platform-admins"}])
    report = detect(inventory, target, config.rewriter(), config.catalog_map)

    assert not report.fatal
    assert [c.severity for c in report.warnings] == [WARN]
    assert "resumed" in report.warnings[0].reason


def test_unknown_owner_does_not_count_as_a_match(inventory, config):
    """Cannot prove it is ours, so make the operator look rather than assume."""
    target = _target(catalogs=[{"name": "prod_gcp"}])
    report = detect(inventory, target, config.rewriter(), config.catalog_map)

    assert len(report.fatal) == 1
    assert "unknown" in report.fatal[0].reason


def test_owner_comparison_ignores_case_and_padding(inventory, config):
    target = _target(catalogs=[{"name": "prod_gcp", "owner": "  Platform-Admins "}])
    report = detect(inventory, target, config.rewriter(), config.catalog_map)
    assert not report.fatal


def test_existing_target_table_is_fatal_because_the_create_is_a_no_op(inventory, config):
    """The silent-omission case: apply succeeds and the table never migrates."""
    target = _target(
        tables=[
            {
                "catalog": "prod_gcp",
                "schema": "sales",
                "name": "orders",
                "table_type": "MANAGED",
                "owner": "platform-admins",
            }
        ]
    )
    report = detect(inventory, target, config.rewriter(), config.catalog_map)

    tables = [c for c in report.collisions if c.kind == "table"]
    assert len(tables) == 1
    assert tables[0].severity == FATAL
    assert tables[0].target_name == "prod_gcp.sales.orders"
    # Ownership is irrelevant here -- our own table is just as invisible.
    assert "would not migrate" in tables[0].reason


def test_schema_collision_is_reported_under_its_target_name(inventory, config):
    target = _target(schemas=[{"catalog": "prod_gcp", "name": "sales", "owner": "other-team"}])
    report = detect(inventory, target, config.rewriter(), config.catalog_map)

    schemas = [c for c in report.collisions if c.kind == "schema"]
    assert [s.target_name for s in schemas] == ["prod_gcp.sales"]
    assert schemas[0].severity == FATAL


def test_overlapping_external_location_url_is_fatal_even_under_a_different_name(inventory, config):
    """UC refuses overlapping locations, so a nested path fails at apply time."""
    target = _target(
        external_locations=[
            {"name": "warehouse_raw", "url": "gs://acme-prod-raw/subdir", "credential_name": "c"}
        ]
    )
    report = detect(inventory, target, config.rewriter(), config.catalog_map)

    locs = [c for c in report.collisions if c.kind == "external_location"]
    assert locs and locs[0].severity == FATAL
    assert "overlaps" in locs[0].reason
    assert "warehouse_raw" in locs[0].reason


def test_identical_external_location_is_a_warning(inventory, config):
    target = _target(
        external_locations=[
            {"name": "prod_raw", "url": "gs://acme-prod-raw/", "credential_name": "c"}
        ]
    )
    report = detect(inventory, target, config.rewriter(), config.catalog_map)

    locs = [c for c in report.collisions if c.kind == "external_location"]
    assert locs and locs[0].severity == WARN


def test_unmapped_source_path_is_not_compared(inventory, config):
    """A path with no rewrite rule is already a gap; do not also guess at overlap."""
    target = _target(
        external_locations=[
            {
                "name": "x",
                "url": "abfss://raw@prodstorage.dfs.core.windows.net/",
                "credential_name": "c",
            }
        ]
    )
    report = detect(inventory, target, config.rewriter(), config.catalog_map)
    assert not [c for c in report.collisions if c.kind == "external_location"]


def test_fatal_rows_sort_ahead_of_warnings_and_catalogs_ahead_of_tables(inventory, config):
    target = _target(
        catalogs=[{"name": "prod_gcp", "owner": "platform-admins"}],  # warn
        tables=[
            {
                "catalog": "prod_gcp",
                "schema": "sales",
                "name": "orders",
                "table_type": "MANAGED",
            }
        ],  # fatal
    )
    report = detect(inventory, target, config.rewriter(), config.catalog_map)
    assert [c.severity for c in report.collisions] == [FATAL, WARN]


def test_render_spells_out_that_nothing_would_error(inventory, config):
    target = _target(catalogs=[{"name": "prod_gcp", "owner": "warehouse-team"}])
    out = render(detect(inventory, target, config.rewriter(), config.catalog_map))

    assert "IF NOT EXISTS" in out
    assert "**FATAL**" in out
    assert "renaming a catalog breaks every fully-qualified reference" in out


@pytest.mark.parametrize(
    "target_url,expect_hit",
    [
        ("gs://acme-prod-raw", True),  # same path, trailing slash only difference
        ("gs://acme-prod-raw/nested/deep", True),  # target nested under ours
        ("gs://acme-prod-rawer", False),  # prefix string match that is not a path match
        ("gs://other-bucket/", False),
    ],
)
def test_url_overlap_is_path_aware_not_string_prefix(inventory, config, target_url, expect_hit):
    target = _target(
        external_locations=[{"name": "other", "url": target_url, "credential_name": "c"}]
    )
    report = detect(inventory, target, config.rewriter(), config.catalog_map)
    hits = [c for c in report.collisions if c.kind == "external_location"]
    assert bool(hits) is expect_hit
