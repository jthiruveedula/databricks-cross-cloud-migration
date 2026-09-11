from __future__ import annotations

import pytest

from dbxmig.config import ConfigError, MigrationConfig
from dbxmig.grants import PrincipalMap
from dbxmig.handoff import (
    CREDENTIAL_TYPE,
    ROUTES,
    generate_handoff,
    replicator_group,
    scoped_catalogs,
    unmapped_locations,
    unrouted,
    workspace_migration_config,
)
from dbxmig.models import ExternalLocation, Inventory

yaml = pytest.importorskip("yaml")


def _load(result, name: str) -> dict:
    return yaml.safe_load(result.files[name])


def test_scope_follows_the_config_not_the_inventory(config: MigrationConfig, inventory: Inventory):
    assert scoped_catalogs(config, inventory) == ["prod"]
    # An empty source.catalogs means everything discovered -- the same
    # convention both accelerators use for an empty filter.
    wide = MigrationConfig.from_dict({"source": {"cloud": "azure"}, "target": {"cloud": "gcp"}})
    assert scoped_catalogs(wide, inventory) == sorted({c.name for c in inventory.catalogs})


def test_workspace_migration_config_scopes_and_never_carries_a_secret(
    config: MigrationConfig, inventory: Inventory
):
    emitted = workspace_migration_config(config, inventory)
    assert emitted["catalog_filter"] == "prod"
    assert emitted["dry_run"] is True
    assert emitted["on_target_collision"] == "fail"
    # The scope names a secret scope/key; the secret itself stays in Databricks.
    assert emitted["spn_secret_scope"] and "secret_value" not in emitted


def test_an_empty_inventory_never_widens_a_scoped_migration(config: MigrationConfig):
    # An empty catalog_filter means "everything" to both accelerators. A scoped
    # config whose inventory resolved to nothing must not become a full-metastore
    # migration by omission.
    emitted = workspace_migration_config(config, Inventory(catalogs=[]))
    assert emitted["catalog_filter"] == "prod"


def test_replicator_group_reuses_path_rules_and_principal_map(config: MigrationConfig):
    group = replicator_group(config, "prod", PrincipalMap(mapping={"grp-a": "grp-a@acme.com"}))
    assert group["replication_group"] == "prod_to_prod_gcp"
    assert group["cloud_url_mapping"] == {
        "abfss://raw@prodstorage.dfs.core.windows.net/": "gs://acme-prod-raw/"
    }
    assert group["principal_mapping"] == {"grp-a": "grp-a@acme.com"}
    assert group["storage_credential_config"]["target_credential_type"] == CREDENTIAL_TYPE["gcp"]
    # Functions and models are "in development" upstream -- never requested here.
    assert "functions" not in group["uc_object_types"]
    assert "models" not in group["uc_object_types"]


def test_unrouted_names_what_no_accelerator_moves(inventory: Inventory):
    names = {name for name, _ in unrouted(inventory)}
    expected = {
        t.full_name
        for t in inventory.tables
        if t.table_type in ("MATERIALIZED_VIEW", "STREAMING_TABLE")
    }
    expected |= {
        f.full_name for f in inventory.functions if f.language.upper() not in ("SQL", "PYTHON")
    }
    assert names == expected
    assert expected, "the fixture is supposed to contain objects nothing migrates"


def test_unmapped_locations_are_reported_not_written_out_incomplete(
    config: MigrationConfig, inventory: Inventory
):
    holes = unmapped_locations(config, inventory)
    assert holes, "the fixture has an external table with no mapped path"
    for _, uri in holes:
        assert not uri.startswith("gs://")


def test_external_locations_are_checked_for_unmapped_storage(config: MigrationConfig):
    # The replicator replicates external locations, so one pointing at storage
    # with no path rule is the same hole as an unmapped table -- reported, not
    # emitted into an incomplete cloud_url_mapping.
    inventory = Inventory(
        external_locations=[
            ExternalLocation(
                name="legacy",
                url="abfss://old@acct.dfs.core.windows.net/x",
                credential_name="legacy-cred",
            )
        ]
    )
    assert unmapped_locations(config, inventory) == [
        ("legacy", "abfss://old@acct.dfs.core.windows.net/x")
    ]


def test_an_unknown_target_cloud_is_refused_not_guessed(config: MigrationConfig):
    unknown = MigrationConfig.from_dict({"source": {"cloud": "azure"}, "target": {}})
    with pytest.raises(ConfigError, match="target.cloud"):
        replicator_group(unknown, "prod")


def test_generate_handoff_emits_every_config_and_flags_review(
    config: MigrationConfig, inventory: Inventory
):
    result = generate_handoff(config, inventory, PrincipalMap(mapping={"grp-a": "grp-a@acme.com"}))
    assert set(result.files) == {
        "workspace-migration/config.yaml",
        "databricks-replicator/environments.yaml",
        "databricks-replicator/prod_to_prod_gcp.yaml",
        "HANDOFF.md",
    }
    env = _load(result, "databricks-replicator/environments.yaml")
    assert list(env["environments"]) == ["azure_to_gcp"]
    assert _load(result, "workspace-migration/config.yaml")["catalog_filter"] == "prod"

    note = result.files["HANDOFF.md"]
    for route in ROUTES:
        assert route.object_class in note
    for name, _ in result.unrouted:
        assert name in note
    assert result.needs_review()


def test_a_clean_inventory_needs_no_review(config: MigrationConfig):
    result = generate_handoff(config, Inventory(catalogs=[]))
    assert not result.needs_review()
    assert "Nothing in this inventory falls outside" in result.files["HANDOFF.md"]
