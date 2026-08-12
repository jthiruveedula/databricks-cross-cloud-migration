from __future__ import annotations

from dbxmig.depgraph import (
    CTAS,
    DEEP_CLONE,
    RECREATE_PIPELINE,
    TIER_SCHEMA,
    TIER_TABLE,
    build_plan,
    validate_plan,
)
from dbxmig.models import Inventory


def index_positions(plan) -> dict:
    return {step.id: position for position, step in enumerate(plan.steps)}


def test_plan_is_internally_consistent(inventory: Inventory):
    plan = build_plan(inventory, catalog_map={"prod": "prod_gcp"})
    assert validate_plan(plan) == []


def test_credential_precedes_location_precedes_catalog_precedes_schema(inventory: Inventory):
    plan = build_plan(inventory)
    positions = index_positions(plan)
    assert (
        positions["storage_credential:prod_uc_credential"]
        < positions["external_location:prod_raw"]
        < positions["catalog:prod"]
        < positions["schema:prod.sales"]
        < positions["table:prod.sales.orders"]
    )


def test_view_on_view_is_ordered_after_its_dependency(inventory: Inventory):
    plan = build_plan(inventory)
    positions = index_positions(plan)
    assert (
        positions["view:prod.sales.v_orders_enriched"]
        < positions["view:prod.sales.v_regional_revenue"]
    )
    assert (
        positions["table:prod.sales.orders"]
        < positions["view:prod.sales.v_orders_enriched"]
    )


def test_delta_table_gets_deep_clone_and_csv_gets_ctas(inventory: Inventory):
    plan = build_plan(
        inventory,
        target_location_for={
            "prod.sales.customers": "gs://acme/sales/customers",
            "prod.finance.ledger_csv": "gs://acme/finance/ledger",
        },
    )
    by_id = plan.by_id()
    assert by_id["table:prod.sales.orders"].strategy == DEEP_CLONE
    assert by_id["table:prod.finance.ledger_csv"].strategy == CTAS


def test_external_table_without_a_target_location_is_blocked(inventory: Inventory):
    plan = build_plan(inventory)  # no target_location_for supplied
    step = plan.by_id()["table:prod.sales.customers"]
    assert step.blocked
    assert "LOCATION" in (step.blocked_reason or "")


def test_materialized_view_and_streaming_table_cannot_be_cloned(inventory: Inventory):
    plan = build_plan(inventory)
    by_id = plan.by_id()
    for name in ("view:prod.sales.mv_daily_sales", "view:prod.sales.st_order_events"):
        step = by_id[name]
        assert step.strategy == RECREATE_PIPELINE
        assert step.blocked
        assert "CLONE" in (step.blocked_reason or "")


def test_out_of_scope_reference_is_reported_not_silently_dropped(inventory: Inventory):
    plan = build_plan(inventory)
    assert plan.dangling_references["prod.finance.v_external_feed"] == [
        "other_metastore.finance.adjustments"
    ]


def test_registered_model_is_flagged_as_artifact_work(inventory: Inventory):
    plan = build_plan(inventory)
    step = plan.by_id()["model:prod.sales.churn_model"]
    assert step.blocked
    assert "MLflow" in (step.blocked_reason or "")


def test_unsupported_function_language_is_blocked(inventory: Inventory):
    plan = build_plan(inventory)
    assert plan.by_id()["function:prod.finance.fx_convert"].blocked
    assert not plan.by_id()["function:prod.sales.mask_email"].blocked


def test_row_and_column_policies_come_after_their_table(inventory: Inventory):
    plan = build_plan(inventory)
    positions = index_positions(plan)
    assert (
        positions["table:prod.sales.customers"] < positions["policy:prod.sales.customers"]
    )


def test_grants_are_last_and_top_down(inventory: Inventory):
    plan = build_plan(inventory)
    grant_steps = [s for s in plan.steps if s.object_type == "GRANT"]
    assert grant_steps, "fixture has grants"
    assert plan.steps[-1].object_type == "GRANT"
    depths = [s.source_name.count(".") for s in grant_steps]
    assert depths == sorted(depths), "catalog grants must precede schema then table grants"


def test_catalog_rename_is_applied_to_every_target_name(inventory: Inventory):
    plan = build_plan(inventory, catalog_map={"prod": "prod_gcp"})
    step = plan.by_id()["table:prod.sales.orders"]
    assert step.source_name == "prod.sales.orders"
    assert step.target_name == "prod_gcp.sales.orders"


def test_circular_views_are_flagged_not_dropped():
    inventory = Inventory.from_dict(
        {
            "catalogs": [{"name": "c"}],
            "schemas": [{"catalog": "c", "name": "s"}],
            "tables": [
                {
                    "catalog": "c",
                    "schema": "s",
                    "name": "a",
                    "table_type": "VIEW",
                    "view_definition": "SELECT 1",
                    "depends_on": ["c.s.b"],
                },
                {
                    "catalog": "c",
                    "schema": "s",
                    "name": "b",
                    "table_type": "VIEW",
                    "view_definition": "SELECT 1",
                    "depends_on": ["c.s.a"],
                },
            ],
        }
    )
    plan = build_plan(inventory)
    assert plan.cycles, "a mutual view dependency must be reported"
    assert plan.by_id()["view:c.s.a"].blocked
    assert plan.by_id()["view:c.s.b"].blocked
    # Both still appear in the plan so nothing is lost.
    assert len([s for s in plan.steps if s.tier == 70]) == 2


def test_plan_is_deterministic(inventory: Inventory):
    first = [s.id for s in build_plan(inventory, catalog_map={"prod": "prod_gcp"}).steps]
    second = [s.id for s in build_plan(inventory, catalog_map={"prod": "prod_gcp"}).steps]
    assert first == second


def test_constraints_follow_their_table(inventory: Inventory):
    plan = build_plan(inventory)
    positions = index_positions(plan)
    assert (
        positions["table:prod.sales.orders"]
        < positions["constraint:prod.sales.orders.pk_orders"]
    )
    assert all(
        s.tier > TIER_SCHEMA for s in plan.steps if s.object_type == "CONSTRAINT"
    )
    assert all(
        s.tier >= TIER_TABLE for s in plan.steps if s.object_type == "CONSTRAINT"
    )
