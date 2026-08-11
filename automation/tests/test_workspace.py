from __future__ import annotations

import json
import os

import pytest

from dbxmig.workspace import (
    ASSET_CLASSES,
    WorkspaceInventory,
    collect_workspace_inventory,
    csv_rows,
    flatten_cluster,
    flatten_job,
    owner_hint,
)

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "workspace.json")


@pytest.fixture()
def workspace() -> WorkspaceInventory:
    with open(FIXTURE, encoding="utf-8") as handle:
        return WorkspaceInventory.from_dict(json.load(handle))


class Obj:
    """Minimal stand-in for an SDK response object."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_round_trip_preserves_every_asset_class(workspace: WorkspaceInventory):
    restored = WorkspaceInventory.from_dict(workspace.to_dict())
    assert restored.counts() == workspace.counts()
    assert set(restored.to_dict()["assets"]) == set(ASSET_CLASSES)


def test_every_asset_class_has_an_owner_hint():
    for asset_class in ASSET_CLASSES:
        assert owner_hint(asset_class) != "Migration lead", asset_class


def test_flatten_job_extracts_the_dependencies_that_decide_the_wave():
    job = Obj(
        job_id=1,
        creator_user_name="a@b.c",
        settings=Obj(
            name="nightly",
            run_as_user_name="svc",
            schedule=Obj(quartz_cron_expression="0 0 2 * * ?", pause_status=Obj(value="UNPAUSED")),
            job_clusters=[Obj(new_cluster=Obj(policy_id="POL-1"))],
            tasks=[
                Obj(notebook_task=Obj(notebook_path="/Repos/x"), sql_task=None),
                Obj(notebook_task=None, sql_task=Obj(warehouse_id="WH-1")),
            ],
            tags={"domain": "sales"},
        ),
    )
    row = flatten_job(job)
    assert row["cluster_policy_ids"] == ["POL-1"]
    assert row["warehouse_ids"] == ["WH-1"]
    assert row["notebook_paths"] == ["/Repos/x"]
    assert row["task_count"] == 2
    assert row["paused"] is False


def test_flatten_cluster_captures_init_scripts_and_cloud_identity():
    cluster = Obj(
        cluster_id="c1",
        cluster_name="etl",
        spark_version="15.4",
        node_type_id="Standard_DS4_v2",
        policy_id="POL-1",
        aws_attributes=Obj(instance_profile_arn="arn:aws:iam::1:instance-profile/x"),
        init_scripts=[Obj(abfss=Obj(destination="abfss://a@b/c.sh"))],
        spark_conf={"k": "v"},
    )
    row = flatten_cluster(cluster)
    assert row["init_scripts"] == ["abfss://a@b/c.sh"]
    assert row["instance_profile_arn"] == "arn:aws:iam::1:instance-profile/x"
    assert row["policy_id"] == "POL-1"


def test_a_failing_api_is_recorded_as_failed_not_empty():
    class Boom:
        def list(self, **kwargs):
            raise RuntimeError("403 Forbidden")

    class Client:
        config = Obj(host="https://x")
        jobs = Boom()
        pipelines = Obj(list_pipelines=lambda: [])
        clusters = Boom()
        cluster_policies = Boom()
        instance_pools = Boom()
        warehouses = Boom()
        lakeview = Boom()
        queries = Boom()
        alerts = Boom()
        secrets = Obj(list_scopes=lambda: [])
        repos = Boom()
        groups = Boom()
        service_principals = Boom()

    inventory = collect_workspace_inventory(Client(), include_acls=False)
    failed = {r.asset_class for r in inventory.failed_classes()}
    assert "jobs" in failed
    assert "403 Forbidden" in next(r.reason for r in inventory.results if r.asset_class == "jobs")
    # An API that legitimately returned nothing is ok-but-empty, not failed.
    pipelines = next(r for r in inventory.results if r.asset_class == "pipelines")
    assert pipelines.ok and pipelines.collected == 0
    assert "empty" in pipelines.reason or "no rows" in pipelines.reason


def test_secret_values_are_never_collected():
    class Client:
        config = Obj(host="https://x")
        jobs = Obj(list=lambda **k: [])
        pipelines = Obj(list_pipelines=lambda: [])
        clusters = Obj(list=lambda: [])
        cluster_policies = Obj(list=lambda: [])
        instance_pools = Obj(list=lambda: [])
        warehouses = Obj(list=lambda: [])
        lakeview = Obj(list=lambda: [])
        queries = Obj(list=lambda: [])
        alerts = Obj(list=lambda: [])
        repos = Obj(list=lambda: [])
        groups = Obj(list=lambda: [])
        service_principals = Obj(list=lambda: [])
        secrets = Obj(
            list_scopes=lambda: [Obj(name="prod", backend_type=Obj(value="DATABRICKS"))],
            list_secrets=lambda scope: [Obj(key="api_token")],
        )

    inventory = collect_workspace_inventory(Client(), include_acls=False)
    scope = inventory.rows("secret_scopes")[0]
    assert scope["key_names"] == ["api_token"]
    assert "value" not in json.dumps(scope).lower().replace("key_names", "")


def test_empty_classes_are_listed_so_they_can_be_confirmed(workspace: WorkspaceInventory):
    workspace.assets["alerts"] = []
    assert "alerts" in workspace.empty_classes()


def test_csv_export_flattens_lists_and_dicts_into_cells(workspace: WorkspaceInventory):
    rows = csv_rows(workspace, "jobs")
    header, first = rows[0], rows[1]
    assert "cluster_policy_ids" in header
    tags_index = header.index("tags")
    assert "domain=sales" in first[tags_index]
    assert all(isinstance(cell, str) for cell in first)


def test_csv_export_of_an_empty_class_is_empty_not_a_lone_header(workspace: WorkspaceInventory):
    workspace.assets["alerts"] = []
    assert csv_rows(workspace, "alerts") == []


def test_workspace_local_groups_are_distinguishable_from_account_groups(
    workspace: WorkspaceInventory,
):
    kinds = {g["display_name"]: g["meta_resource_type"] for g in workspace.rows("groups")}
    assert kinds["sales-eng"] == "WorkspaceGroup"
    assert kinds["data-readers"] == "Group"


def test_object_acls_are_a_separate_permission_system(workspace: WorkspaceInventory):
    acls = workspace.rows("object_acls")
    assert {a["object_type"] for a in acls} == {"jobs", "clusters"}
    assert any(a["permission_level"] == "CAN_RESTART" for a in acls)
