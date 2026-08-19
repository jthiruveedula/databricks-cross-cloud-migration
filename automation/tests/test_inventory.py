"""Live Unity Catalog export: ``_build_table``'s SDK-object -> ``Table`` mapping.

No other test file covers ``inventory.py`` -- these are narrow regression
tests for the fields that used to silently drop on a live (non-fixture)
``dbxmig inventory`` run: partition columns, column masks, and the foreign
key parent-table reference.
"""

from __future__ import annotations

from types import SimpleNamespace

from dbxmig.inventory import _build_table


def _column(name, partition_index=None, mask=None):
    return SimpleNamespace(
        name=name,
        type_text="STRING",
        nullable=True,
        comment=None,
        position=0,
        partition_index=partition_index,
        mask=mask,
    )


def test_partition_columns_are_ordered_by_partition_index():
    raw = SimpleNamespace(
        name="orders",
        columns=[
            _column("region", partition_index=1),
            _column("order_id"),
            _column("year", partition_index=0),
        ],
        table_constraints=[],
    )
    table = _build_table("prod", "sales", raw)
    assert table.partition_columns == ["year", "region"]


def test_column_mask_is_captured_from_the_column():
    raw = SimpleNamespace(
        name="customers",
        columns=[_column("ssn", mask=SimpleNamespace(function_name="prod.security.mask_ssn"))],
        table_constraints=[],
    )
    table = _build_table("prod", "sales", raw)
    assert table.column_masks == {"ssn": "prod.security.mask_ssn"}


def test_column_with_no_mask_is_absent_from_column_masks():
    raw = SimpleNamespace(name="customers", columns=[_column("email")], table_constraints=[])
    table = _build_table("prod", "sales", raw)
    assert table.column_masks == {}


def test_foreign_key_definition_includes_references_clause():
    raw = SimpleNamespace(
        name="orders",
        columns=[],
        table_constraints=[
            SimpleNamespace(
                foreign_key_constraint=SimpleNamespace(
                    name="fk_customer",
                    child_columns=["customer_id"],
                    parent_table="prod.sales.customers",
                    parent_columns=["customer_id"],
                ),
                primary_key_constraint=None,
                named_table_constraint=None,
            )
        ],
    )
    table = _build_table("prod", "sales", raw)
    assert len(table.constraints) == 1
    constraint = table.constraints[0]
    assert constraint.kind == "FOREIGN_KEY"
    assert constraint.definition == "customer_id REFERENCES prod.sales.customers(customer_id)"


def test_foreign_key_with_no_parent_table_stays_bare():
    raw = SimpleNamespace(
        name="orders",
        columns=[],
        table_constraints=[
            SimpleNamespace(
                foreign_key_constraint=SimpleNamespace(
                    name="fk_customer", child_columns=["customer_id"], parent_table=None
                ),
                primary_key_constraint=None,
                named_table_constraint=None,
            )
        ],
    )
    table = _build_table("prod", "sales", raw)
    assert table.constraints[0].definition == "customer_id"
