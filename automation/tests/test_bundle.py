from __future__ import annotations

import json
import os

import pytest
import yaml

from dbxmig.bundle import (
    SERVER_OWNED_FIELDS,
    generate_bundle,
    job_resource,
    variable_name,
)
from dbxmig.rewrite import PathRule, Rewriter
from dbxmig.workspace import WorkspaceInventory

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "workspace.json")


@pytest.fixture()
def workspace() -> WorkspaceInventory:
    with open(FIXTURE, encoding="utf-8") as handle:
        return WorkspaceInventory.from_dict(json.load(handle))


@pytest.fixture()
def rewriter() -> Rewriter:
    return Rewriter(
        path_rules=[PathRule("abfss://raw@prodstorage.dfs.core.windows.net/", "gs://acme-raw/")],
        catalog_map={"prod": "prod_gcp"},
    )


def jobs_of(result):
    return yaml.safe_load(result.files["resources/jobs.yml"])["resources"]["jobs"]


def test_bundle_emits_the_expected_file_set(workspace, rewriter):
    result = generate_bundle(workspace, rewriter=rewriter)
    assert set(result.files) == {
        "databricks.yml",
        "resources/jobs.yml",
        "resources/pipelines.yml",
        "resources/sql_warehouses.yml",
        "resources/cluster_policies.yml",
        "resources/instance_pools.yml",
        "REVIEW.md",
    }


def test_root_file_is_valid_yaml_with_a_target(workspace, rewriter):
    root = yaml.safe_load(generate_bundle(workspace, rewriter=rewriter).files["databricks.yml"])
    assert root["bundle"]["name"] == "migrated-estate"
    assert "target" in root["targets"]
    assert "resources/jobs.yml" in root["include"]
    assert root["include"] == sorted(root["include"])


def test_server_owned_fields_are_stripped(workspace, rewriter):
    body = yaml.safe_dump(jobs_of(generate_bundle(workspace, rewriter=rewriter)))
    for forbidden in ("job_id", "creator_user_name", "created_time"):
        assert forbidden not in body
    assert forbidden in SERVER_OWNED_FIELDS


def test_storage_paths_are_rewritten_inside_task_parameters(workspace, rewriter):
    job = jobs_of(generate_bundle(workspace, rewriter=rewriter))["sales_daily_load"]
    params = job["tasks"][0]["notebook_task"]["base_parameters"]
    assert params["src"] == "gs://acme-raw/sales/orders"


def test_init_script_scheme_key_is_remapped_with_the_path(workspace, rewriter):
    job = jobs_of(generate_bundle(workspace, rewriter=rewriter))["sales_daily_load"]
    script = job["job_clusters"][0]["new_cluster"]["init_scripts"][0]
    # Rewritten to GCS, so the key must be `gcs`, not the source's `abfss`.
    assert list(script) == ["gcs"]
    assert script["gcs"]["destination"].startswith("gs://")


def test_workspace_scoped_ids_become_variables_with_no_default(workspace, rewriter):
    result = generate_bundle(workspace, rewriter=rewriter)
    root = yaml.safe_load(result.files["databricks.yml"])
    job = jobs_of(result)["sales_daily_load"]
    assert job["job_clusters"][0]["new_cluster"]["policy_id"] == "${var.policy_pol_standard_etl}"
    assert job["tasks"][1]["sql_task"]["warehouse_id"] == "${var.warehouse_wh_finance_01}"
    for name, spec in root["variables"].items():
        assert "default" not in spec, name  # deploy must fail until it is supplied


def test_source_cloud_node_type_is_forced_to_a_decision(workspace, rewriter):
    job = jobs_of(generate_bundle(workspace, rewriter=rewriter))["sales_daily_load"]
    node_type = job["job_clusters"][0]["new_cluster"]["node_type_id"]
    assert node_type.startswith("${var.node_type_")
    assert "Standard_DS4_v2" not in node_type


def test_schedules_are_paused_by_default(workspace, rewriter):
    job = jobs_of(generate_bundle(workspace, rewriter=rewriter))["sales_daily_load"]
    assert job["schedule"]["pause_status"] == "PAUSED"


def test_no_pause_keeps_the_original_schedule(workspace, rewriter):
    result = generate_bundle(workspace, rewriter=rewriter, pause_schedules=False)
    assert jobs_of(result)["sales_daily_load"]["schedule"]["pause_status"] == "UNPAUSED"


def test_a_job_without_raw_goes_to_review_not_into_the_bundle(workspace, rewriter):
    result = generate_bundle(workspace, rewriter=rewriter)
    assert "finance_ledger_export" not in jobs_of(result)
    reasons = " ".join(r for _, r in result.review)
    assert "finance-ledger-export" in reasons
    assert "--raw" in reasons
    assert result.needs_review()


def test_review_markdown_lists_variables_and_the_deploy_command(workspace, rewriter):
    review = generate_bundle(workspace, rewriter=rewriter).files["REVIEW.md"]
    assert "policy_pol_standard_etl" in review
    assert "databricks bundle deploy" in review
    assert "PAUSED" in review
    assert "Permissions" in review  # ACLs are not carried by a bundle


def test_pipeline_spec_is_emitted_and_rewritten(workspace, rewriter):
    result = generate_bundle(workspace, rewriter=rewriter)
    pipelines = yaml.safe_load(result.files["resources/pipelines.yml"])["resources"]["pipelines"]
    spec = pipelines["orders_bronze_silver"]
    assert spec["storage"].startswith("gs://acme-raw/")
    assert spec["catalog"] == "prod_gcp"  # catalog rename applied
    assert "pipeline_id" not in spec and "state" not in spec


def test_variable_names_are_stable_across_regeneration(workspace, rewriter):
    first = generate_bundle(workspace, rewriter=rewriter)
    second = generate_bundle(workspace, rewriter=rewriter)
    assert sorted(first.variables) == sorted(second.variables)
    assert first.files["resources/jobs.yml"] == second.files["resources/jobs.yml"]


def test_variable_name_slugs_are_readable():
    assert variable_name("policy", "POL-STANDARD-ETL") == "policy_pol_standard_etl"
    assert variable_name("pool", "") == "pool_unnamed"


def test_duplicate_job_names_get_distinct_resource_keys(rewriter):
    raw = {"settings": {"name": "same", "tasks": []}}
    inventory = WorkspaceInventory(
        assets={
            "jobs": [
                {"job_id": "1", "name": "same", "raw": raw},
                {"job_id": "2", "name": "same", "raw": raw},
            ]
        }
    )
    jobs = yaml.safe_load(
        generate_bundle(inventory, rewriter=rewriter).files["resources/jobs.yml"]
    )["resources"]["jobs"]
    assert set(jobs) == {"same", "same_2"}


def test_job_resource_reports_a_reason_rather_than_guessing():
    key, body, reason = job_resource({"name": "n", "raw": {}}, None, {})
    assert key is None and body is None
    assert "--raw" in reason


def test_target_host_is_written_when_configured(workspace, rewriter):
    result = generate_bundle(workspace, rewriter=rewriter, target_host="https://x.gcp.databricks.com")
    root = yaml.safe_load(result.files["databricks.yml"])
    assert root["targets"]["target"]["workspace"]["host"] == "https://x.gcp.databricks.com"


# ---- dependency resources ------------------------------------------------


def resources_of(result, filename, kind):
    return yaml.safe_load(result.files["resources/{0}.yml".format(filename)])["resources"][kind]


def test_warehouses_policies_and_pools_are_emitted(workspace, rewriter):
    result = generate_bundle(workspace, rewriter=rewriter)
    assert "resources/sql_warehouses.yml" in result.files
    assert "resources/cluster_policies.yml" in result.files
    assert "resources/instance_pools.yml" in result.files


def test_pool_node_type_is_variabilized_like_a_cluster_node_type(workspace, rewriter):
    pools = resources_of(
        generate_bundle(workspace, rewriter=rewriter), "instance_pools", "instance_pools"
    )
    node_type = pools["warm_ds4"]["node_type_id"]
    assert node_type.startswith("${var.node_type_")
    assert "Standard_DS4_v2" not in node_type


def test_warehouse_channel_becomes_a_nested_object(workspace, rewriter):
    warehouses = resources_of(
        generate_bundle(workspace, rewriter=rewriter), "sql_warehouses", "sql_warehouses"
    )
    assert warehouses["finance_bi"]["channel"] == {"name": "CHANNEL_NAME_CURRENT"}


def test_warehouse_fields_are_renamed_to_bundle_names(workspace, rewriter):
    warehouses = resources_of(
        generate_bundle(workspace, rewriter=rewriter), "sql_warehouses", "sql_warehouses"
    )
    body = warehouses["finance_bi"]
    assert body["min_num_clusters"] == 1 and body["max_num_clusters"] == 4
    assert "min_clusters" not in body
    # The source warehouse id must never appear -- the target assigns its own.
    assert "warehouse_id" not in body


def test_pool_name_uses_the_bundle_field_name(workspace, rewriter):
    pools = resources_of(
        generate_bundle(workspace, rewriter=rewriter), "instance_pools", "instance_pools"
    )
    assert pools["warm_ds4"]["instance_pool_name"] == "warm-ds4"


def test_include_list_covers_every_generated_resource_file(workspace, rewriter):
    result = generate_bundle(workspace, rewriter=rewriter)
    root = yaml.safe_load(result.files["databricks.yml"])
    generated = sorted(f for f in result.files if f.startswith("resources/"))
    assert root["include"] == generated


def test_review_explains_the_deploy_order_dependency(workspace, rewriter):
    review = generate_bundle(workspace, rewriter=rewriter).files["REVIEW.md"]
    assert "Deploy order" in review
    assert "before the jobs" in review


def test_include_filter_limits_what_is_generated(workspace, rewriter):
    result = generate_bundle(workspace, rewriter=rewriter, include=("jobs",))
    assert "resources/sql_warehouses.yml" not in result.files
    assert "resources/jobs.yml" in result.files
