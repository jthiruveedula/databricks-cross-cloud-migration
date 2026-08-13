from __future__ import annotations

from dbxmig.ddl import (
    add_constraint,
    clone_at_version,
    create_catalog,
    create_external_location,
    create_view,
    create_volume,
    ctas,
    deep_clone,
    quote_ident,
    quote_literal,
    quote_name,
    set_table_properties,
    set_table_tags,
    table_ddl_bundle,
)
from dbxmig.models import Catalog, Inventory, Volume


def test_identifier_quoting_escapes_backticks():
    assert quote_ident("we`ird") == "`we``ird`"
    assert quote_name("a.b.c") == "`a`.`b`.`c`"


def test_literal_quoting_escapes_quotes_and_backslashes():
    assert quote_literal("it's") == "'it\\'s'"
    assert quote_literal("a\\b") == "'a\\\\b'"


def test_catalog_ddl_is_idempotent_and_sets_managed_location():
    statement = create_catalog(Catalog(name="prod"), "prod_gcp", "gs://bucket/managed")
    assert statement.startswith("CREATE CATALOG IF NOT EXISTS `prod_gcp`")
    assert "MANAGED LOCATION 'gs://bucket/managed'" in statement


def test_deep_clone_is_idempotent_by_default():
    statement = deep_clone("a.b.c", "x.b.c", "gs://bucket/x")
    assert statement == (
        "CREATE TABLE IF NOT EXISTS `x`.`b`.`c` DEEP CLONE `a`.`b`.`c` LOCATION 'gs://bucket/x';"
    )


def test_clone_at_version_pins_a_pre_cutover_snapshot():
    assert clone_at_version("a.b.c", "x.b.c", 42) == (
        "CREATE OR REPLACE TABLE `x`.`b`.`c` DEEP CLONE `a`.`b`.`c` VERSION AS OF 42;"
    )


def test_ctas_carries_partitioning():
    statement = ctas("a.b.c", "x.b.c", partition_columns=["dt"])
    assert "PARTITIONED BY (`dt`)" in statement
    assert statement.endswith("AS SELECT * FROM `a`.`b`.`c`;")


def test_external_volume_requires_a_location():
    volume = Volume(catalog="c", schema="s", name="v", volume_type="EXTERNAL")
    try:
        create_volume(volume, "c.s.v")
    except ValueError as exc:
        assert "target location" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for external volume with no location")


def test_managed_volume_needs_no_location():
    volume = Volume(catalog="c", schema="s", name="v", volume_type="MANAGED")
    assert create_volume(volume, "c.s.v") == "CREATE VOLUME IF NOT EXISTS `c`.`s`.`v`;"


def test_external_location_binds_its_credential():
    statement = create_external_location("loc", "gs://b/p", "cred", read_only=True)
    assert "WITH (STORAGE CREDENTIAL `cred`)" in statement
    assert statement.endswith("READ_ONLY;")


def test_delta_protocol_properties_are_not_replayed():
    statement = set_table_properties(
        "c.s.t",
        {
            "delta.minReaderVersion": "2",
            "delta.minWriterVersion": "7",
            "delta.feature.deletionVectors": "supported",
            "delta.columnMapping.mode": "name",
            "business_owner": "sales",
        },
    )
    assert statement is not None
    assert "business_owner" in statement
    assert "minReaderVersion" not in statement
    assert "columnMapping" not in statement


def test_properties_statement_is_none_when_nothing_is_replayable():
    assert set_table_properties("c.s.t", {"delta.minReaderVersion": "2"}) is None


def test_tags_are_emitted_sorted():
    statement = set_table_tags("c.s.t", {"b": "2", "a": "1"})
    assert statement == "ALTER TABLE `c`.`s`.`t` SET TAGS ('a' = '1', 'b' = '2');"


def test_not_null_constraint_is_a_column_alteration():
    assert add_constraint("c.s.t", "nn", "NOT_NULL", "col") == (
        "ALTER TABLE `c`.`s`.`t` ALTER COLUMN `col` SET NOT NULL;"
    )


def test_check_and_primary_key_constraints():
    assert "CHECK (amount >= 0)" in add_constraint("c.s.t", "chk", "CHECK", "amount >= 0")
    # `PRIMARY KEY id` is a syntax error. The column list has to be parenthesized
    # whether or not the inventory exported it that way.
    assert "PRIMARY KEY (id)" in add_constraint("c.s.t", "pk", "PRIMARY_KEY", "id")
    assert "PRIMARY KEY (a, b)" in add_constraint("c.s.t", "pk", "PRIMARY_KEY", "(a, b)")


def test_foreign_key_rewrites_the_parent_onto_its_target_name():
    """Left alone the parent names a catalog that does not exist in the target."""
    statement = add_constraint(
        "prod_gcp.sales.orders",
        "fk_cust",
        "FOREIGN_KEY",
        "(customer_id) REFERENCES prod.sales.customers",
        lambda name: name.replace("prod.", "prod_gcp.", 1),
    )
    assert "FOREIGN KEY (customer_id)" in statement
    assert "REFERENCES `prod_gcp`.`sales`.`customers`" in statement
    assert "`prod`.`sales`" not in statement


def test_foreign_key_keeps_the_parent_column_list_and_normalizes_its_own():
    statement = add_constraint(
        "c.s.t",
        "fk",
        "FOREIGN_KEY",
        "customer_id REFERENCES c.s.customers (customer_id)",
    )
    assert "FOREIGN KEY (customer_id) REFERENCES `c`.`s`.`customers` (customer_id);" in statement


def test_foreign_key_without_a_references_clause_is_blocked_not_dropped():
    statement = add_constraint("c.s.t", "fk", "FOREIGN_KEY", "(customer_id)")
    assert statement.startswith("-- BLOCKED constraint fk")
    assert "no REFERENCES clause" in statement


def test_view_ddl_replaces_and_strips_trailing_semicolon():
    statement = create_view("c.s.v", "SELECT 1;", comment="hi")
    assert statement.startswith("CREATE OR REPLACE VIEW `c`.`s`.`v` COMMENT 'hi' AS")
    assert statement.endswith("SELECT 1;")
    assert ";;" not in statement


def test_table_bundle_emits_clone_then_metadata_in_order(inventory: Inventory):
    orders = inventory.table_index()["prod.sales.orders"]
    statements = table_ddl_bundle(orders, "prod_gcp.sales.orders", "DEEP_CLONE")
    assert statements[0].startswith(
        "CREATE TABLE IF NOT EXISTS `prod_gcp`.`sales`.`orders` DEEP CLONE"
    )
    joined = "\n".join(statements)
    assert "COMMENT ON TABLE" in joined
    assert "COMMENT ON COLUMN `prod_gcp`.`sales`.`orders`.`order_id`" in joined
    assert "SET TAGS" in joined
    assert "ADD CONSTRAINT `pk_orders` PRIMARY KEY (order_id)" in joined
    # The source's Delta protocol pins must not be replayed onto the target.
    assert "minWriterVersion" not in joined
