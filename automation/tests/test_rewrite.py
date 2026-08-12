from __future__ import annotations

from dbxmig.rewrite import PathRule, Rewriter, coverage_report, parse_uri, rules_from_config


def make_rewriter() -> Rewriter:
    return Rewriter(
        path_rules=[
            PathRule("abfss://raw@prodstorage.dfs.core.windows.net/", "gs://acme-raw/"),
            PathRule(
                "abfss://raw@prodstorage.dfs.core.windows.net/pii/",
                "gs://acme-pii-restricted/",
            ),
            PathRule("dbfs:/mnt/legacy/", "/Volumes/prod_gcp/sales/legacy/"),
        ],
        catalog_map={"prod": "prod_gcp"},
    )


def test_longest_prefix_wins_regardless_of_declaration_order():
    rewriter = make_rewriter()
    result = rewriter.rewrite_uri(
        "abfss://raw@prodstorage.dfs.core.windows.net/pii/customers"
    )
    assert result.value == "gs://acme-pii-restricted/customers"
    assert result.rule is not None
    assert result.rule.source_prefix.endswith("/pii/")


def test_general_rule_still_applies_to_non_specific_paths():
    rewriter = make_rewriter()
    result = rewriter.rewrite_uri(
        "abfss://raw@prodstorage.dfs.core.windows.net/sales/orders"
    )
    assert result.value == "gs://acme-raw/sales/orders"


def test_unmapped_uri_is_returned_unchanged_and_flagged():
    rewriter = make_rewriter()
    result = rewriter.rewrite_uri("abfss://archive@legacy.dfs.core.windows.net/x")
    assert not result.mapped
    assert not result.changed
    assert result.value == "abfss://archive@legacy.dfs.core.windows.net/x"


def test_find_unmapped_is_the_gap_signal():
    rewriter = make_rewriter()
    sql = (
        "SELECT * FROM delta.`abfss://raw@prodstorage.dfs.core.windows.net/ok` "
        "UNION ALL SELECT * FROM delta.`abfss://archive@legacy.dfs.core.windows.net/bad`"
    )
    unmapped = rewriter.find_unmapped(sql)
    assert unmapped == ["abfss://archive@legacy.dfs.core.windows.net/bad"]


def test_volume_paths_are_not_reported_as_unmapped():
    rewriter = make_rewriter()
    assert rewriter.find_unmapped("SELECT * FROM csv.`/Volumes/prod/sales/landing/a.csv`") == []


def test_dbfs_mount_is_rewritten_to_a_volume():
    rewriter = make_rewriter()
    result = rewriter.rewrite_uri("dbfs:/mnt/legacy/2024/part-0.parquet")
    assert result.value == "/Volumes/prod_gcp/sales/legacy/2024/part-0.parquet"


def test_catalog_rename_respects_identifier_boundaries():
    rewriter = make_rewriter()
    sql = (
        "SELECT prod_total, `prod`.sales.orders.amount "
        "FROM prod.sales.orders WHERE x = 'prod.sales'"
    )
    out = rewriter.rewrite_identifiers(sql)
    assert "prod_gcp.sales.orders" in out
    # A column that merely starts with the catalog name must not be touched.
    assert "prod_total" in out
    assert "prod_gcp_total" not in out


def test_rewrite_sql_handles_uris_and_identifiers_together():
    rewriter = make_rewriter()
    sql = (
        "CREATE VIEW prod.sales.v AS SELECT * FROM prod.sales.orders "
        "WHERE path = 'abfss://raw@prodstorage.dfs.core.windows.net/sales'"
    )
    out = rewriter.rewrite_sql(sql).value
    assert "prod_gcp.sales.orders" in out
    assert "gs://acme-raw/sales" in out


def test_rewrite_full_name_maps_only_the_catalog_part():
    rewriter = make_rewriter()
    assert rewriter.rewrite_full_name("prod.sales.orders") == "prod_gcp.sales.orders"
    assert rewriter.rewrite_full_name("other.sales.orders") == "other.sales.orders"


def test_parse_uri_across_clouds():
    assert parse_uri("s3://bucket/a/b") == ("s3", "bucket", "/a/b")
    assert parse_uri("gs://bucket/a") == ("gs", "bucket", "/a")
    scheme, container, path = parse_uri("abfss://raw@acct.dfs.core.windows.net/a/b")
    assert scheme == "abfss"
    assert container == "raw@acct.dfs.core.windows.net"
    assert path == "/a/b"
    assert parse_uri("dbfs:/mnt/legacy/a") == ("dbfs", "mnt", "/legacy/a")


def test_rules_from_config_rejects_incomplete_rules():
    try:
        rules_from_config([{"from": "s3://a/"}])
    except ValueError as exc:
        assert "from" in str(exc)
    else:  # pragma: no cover - the call must raise
        raise AssertionError("expected ValueError for a rule with no target")


def test_coverage_report_groups_unmapped_by_object():
    rewriter = make_rewriter()
    report = coverage_report(
        rewriter,
        [
            ("prod.sales.orders", "abfss://raw@prodstorage.dfs.core.windows.net/ok"),
            ("prod.finance.ledger", "abfss://archive@legacy.dfs.core.windows.net/bad"),
        ],
    )
    assert list(report) == ["prod.finance.ledger"]
