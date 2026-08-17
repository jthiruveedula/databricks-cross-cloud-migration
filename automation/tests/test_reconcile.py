from __future__ import annotations

import copy

from dbxmig.gateway import FixtureGateway
from dbxmig.models import Column, Inventory, Table
from dbxmig.reconcile import (
    SEV_BLOCKER,
    SEV_WARNING,
    check_clone_provenance,
    check_unmigrated_locations,
    checksum_query,
    compare_checksums,
    compare_object_counts,
    compare_row_counts,
    compare_schemas,
    reconcile_clone_provenance,
    reconcile_inventories,
    reconcile_live,
)


def test_row_counts_must_match_exactly_by_default():
    assert compare_row_counts("t", 100, 100) is None
    finding = compare_row_counts("t", 100, 99)
    assert finding is not None and finding.blocking


def test_row_count_tolerance_is_respected():
    assert compare_row_counts("t", 100, 99, tolerance_rows=1) is None


def test_schema_comparison_catches_type_and_nullability_drift():
    source = [Column("a", "BIGINT", nullable=False, position=0)]
    target = [Column("a", "INT", nullable=True, position=0)]
    checks = {f.check for f in compare_schemas("t", source, target)}
    assert "schema_type_mismatch" in checks
    assert "schema_nullability_mismatch" in checks


def test_column_order_drift_is_a_warning_not_a_blocker():
    source = [Column("a", "INT", position=0), Column("b", "INT", position=1)]
    target = [Column("a", "INT", position=1), Column("b", "INT", position=0)]
    findings = compare_schemas("t", source, target)
    assert findings
    assert all(f.severity == SEV_WARNING for f in findings)


def test_type_comparison_ignores_whitespace_and_case():
    source = [Column("a", "decimal(18, 2)", position=0)]
    target = [Column("a", "DECIMAL(18,2)", position=0)]
    assert compare_schemas("t", source, target) == []


def test_missing_and_extra_columns_both_block():
    source = [Column("a", "INT", position=0)]
    target = [Column("b", "INT", position=0)]
    checks = {f.check for f in compare_schemas("t", source, target)}
    assert checks == {"schema_missing_column", "schema_extra_column"}


def test_clone_provenance_accepts_a_real_clone():
    history = [
        {
            "operation": "CLONE",
            "operationParameters": {"source": "prod.sales.orders"},
        }
    ]
    assert check_clone_provenance("t", history, "prod.sales.orders") == []


def test_ctas_masquerading_as_a_migration_is_caught():
    history = [{"operation": "CREATE TABLE AS SELECT", "operationParameters": {}}]
    findings = check_clone_provenance("t", history, "prod.sales.orders")
    assert findings and findings[0].blocking
    assert "expected CLONE" in findings[0].detail


def test_clone_from_the_wrong_source_is_caught():
    history = [{"operation": "CLONE", "operationParameters": {"source": "dev.sales.orders"}}]
    findings = check_clone_provenance("t", history, "prod.sales.orders")
    assert findings and findings[0].blocking


def test_empty_history_blocks():
    assert check_clone_provenance("t", [], "prod.sales.orders")[0].blocking


def test_target_still_pointing_at_source_storage_is_a_blocker(inventory: Inventory):
    findings = check_unmigrated_locations(
        inventory, ["abfss://raw@prodstorage.dfs.core.windows.net/"]
    )
    names = {f.obj for f in findings}
    assert "prod.sales.customers" in names
    assert "prod.sales.landing" in names
    assert all(f.severity == SEV_BLOCKER for f in findings)


def test_object_counts_flag_a_whole_missing_schema(inventory: Inventory, raw_inventory: dict):
    trimmed = copy.deepcopy(raw_inventory)
    trimmed["schemas"] = [s for s in trimmed["schemas"] if s["name"] != "finance"]
    trimmed["tables"] = [t for t in trimmed["tables"] if t["schema"] != "finance"]
    findings = compare_object_counts(inventory, Inventory.from_dict(trimmed))
    assert any(f.obj == "schemas" and f.blocking for f in findings)


def test_pipeline_outputs_warn_rather_than_block(inventory: Inventory, raw_inventory: dict):
    trimmed = copy.deepcopy(raw_inventory)
    trimmed["tables"] = [
        t for t in trimmed["tables"] if t["table_type"] != "MATERIALIZED_VIEW"
    ]
    findings = compare_object_counts(inventory, Inventory.from_dict(trimmed))
    mv = [f for f in findings if f.obj == "tables_materialized_view"]
    assert mv and mv[0].severity == SEV_WARNING


def test_identical_inventories_reconcile_clean(inventory: Inventory, raw_inventory: dict):
    report = reconcile_inventories(inventory, Inventory.from_dict(raw_inventory))
    assert report.passed
    assert report.exit_code() == 0


def test_missing_table_in_target_fails_reconciliation(inventory: Inventory, raw_inventory: dict):
    trimmed = copy.deepcopy(raw_inventory)
    trimmed["tables"] = [t for t in trimmed["tables"] if t["name"] != "orders"]
    report = reconcile_inventories(inventory, Inventory.from_dict(trimmed))
    assert not report.passed
    assert any(f.check == "missing_object" for f in report.findings)


def test_checksum_query_is_order_independent_aggregate():
    query = checksum_query("prod.sales.orders", ["id", "amount"])
    assert query == (
        "SELECT COUNT(*) AS cnt, SUM(xxhash64(id, amount)) AS agg_hash FROM prod.sales.orders"
    )


def test_matching_checksums_pass():
    row = {"cnt": 100, "agg_hash": 12345}
    assert compare_checksums("t", row, dict(row)) is None


def test_checksum_mismatch_reports_row_count_first():
    source = {"cnt": 100, "agg_hash": 111}
    target = {"cnt": 99, "agg_hash": 111}
    finding = compare_checksums("t", source, target)
    assert finding is not None and finding.blocking
    assert "row count differs" in finding.detail


def test_checksum_mismatch_with_matching_counts_reports_hash_drift():
    source = {"cnt": 100, "agg_hash": 111}
    target = {"cnt": 100, "agg_hash": 222}
    finding = compare_checksums("t", source, target)
    assert finding is not None and finding.blocking
    assert "aggregate hash differs" in finding.detail


def _table(name: str = "orders") -> Table:
    return Table(
        catalog="prod",
        schema="sales",
        name=name,
        columns=[Column("id", "BIGINT"), Column("amount", "DECIMAL(18,2)")],
    )


def test_reconcile_live_passes_when_checksums_match():
    table = _table()
    query = checksum_query(table.full_name, ["id", "amount"])
    row = {"cnt": 10, "agg_hash": 999}
    source_gw = FixtureGateway(query_results={query: [row]})
    target_gw = FixtureGateway(query_results={query: [dict(row)]})
    report = reconcile_live(source_gw, target_gw, [table])
    assert report.passed
    assert report.checked == 1


def test_reconcile_live_catches_a_drifted_table():
    table = _table()
    query = checksum_query(table.full_name, ["id", "amount"])
    source_gw = FixtureGateway(query_results={query: [{"cnt": 10, "agg_hash": 999}]})
    target_gw = FixtureGateway(query_results={query: [{"cnt": 9, "agg_hash": 999}]})
    report = reconcile_live(source_gw, target_gw, [table])
    assert not report.passed
    assert report.findings[0].check == "checksum"


def test_reconcile_live_flags_empty_result_instead_of_crashing():
    table = _table()
    source_gw = FixtureGateway(query_results={})
    target_gw = FixtureGateway(query_results={})
    report = reconcile_live(source_gw, target_gw, [table])
    assert not report.passed
    assert "no rows on source" in report.findings[0].detail


def test_reconcile_clone_provenance_live_uses_describe_history():
    table = _table()
    history_query = "DESCRIBE HISTORY {0} LIMIT 5".format(table.full_name)
    target_gw = FixtureGateway(
        query_results={
            history_query: [
                {"operation": "CLONE", "operationParameters": {"source": "dev.sales.orders"}}
            ]
        }
    )
    report = reconcile_clone_provenance(target_gw, [table], lambda name: "dev.sales.orders")
    assert report.passed
    assert report.checked == 1


def test_reconcile_clone_provenance_live_catches_a_ctas():
    table = _table()
    history_query = "DESCRIBE HISTORY {0} LIMIT 5".format(table.full_name)
    target_gw = FixtureGateway(
        query_results={history_query: [{"operation": "CREATE TABLE AS SELECT"}]}
    )
    report = reconcile_clone_provenance(target_gw, [table], lambda name: "dev.sales.orders")
    assert not report.passed


def test_renamed_catalog_still_matches_on_schema_and_name(raw_inventory: dict):
    source = Inventory.from_dict(raw_inventory)
    renamed = copy.deepcopy(raw_inventory)
    for key in ("catalogs", "schemas", "tables", "volumes", "functions", "models"):
        for item in renamed.get(key, []):
            if key == "catalogs":
                item["name"] = "prod_gcp"
            elif "catalog" in item:
                item["catalog"] = "prod_gcp"
    target = Inventory.from_dict(renamed)
    report = reconcile_inventories(source, target)
    assert not [f for f in report.findings if f.check == "missing_object"]
