from __future__ import annotations

import json
import os

import pytest

from dbxmig.config import ConfigError, MigrationConfig, load_config, parse_config_text


def test_token_is_read_from_the_environment_not_the_file(monkeypatch):
    config = MigrationConfig.from_dict({"source": {"token_env": "TEST_DBX_TOKEN"}})
    monkeypatch.setenv("TEST_DBX_TOKEN", "secret-value")
    assert config.source.token == "secret-value"


def test_no_token_env_means_no_token():
    assert MigrationConfig.from_dict({}).source.token is None


def test_llm_enabled_without_an_endpoint_is_rejected():
    with pytest.raises(ConfigError) as exc:
        MigrationConfig.from_dict({"llm": {"enabled": True}})
    assert "endpoint" in str(exc.value)


def test_catalog_rename_outside_scope_is_rejected():
    with pytest.raises(ConfigError) as exc:
        MigrationConfig.from_dict(
            {"source": {"catalogs": ["prod"]}, "catalog_map": {"dev": "dev_gcp"}}
        )
    assert "not in source.catalogs" in str(exc.value)


def test_two_catalogs_colliding_on_one_target_is_rejected():
    with pytest.raises(ConfigError) as exc:
        MigrationConfig.from_dict(
            {
                "source": {"catalogs": ["a", "b"]},
                "catalog_map": {"a": "merged", "b": "merged"},
            }
        )
    assert "merged" in str(exc.value)


def test_no_op_path_rule_is_rejected():
    with pytest.raises(ConfigError) as exc:
        MigrationConfig.from_dict({"path_rules": [{"from": "s3://x/", "to": "s3://x/"}]})
    assert "no-op" in str(exc.value)


def test_target_location_prefers_an_explicit_override():
    config = MigrationConfig.from_dict(
        {
            "path_rules": [{"from": "abfss://a@b.dfs.core.windows.net/", "to": "gs://t/"}],
            "table_locations": {"c.s.t": "gs://override/here"},
        }
    )
    assert config.target_location_for("c.s.t", "abfss://a@b.dfs.core.windows.net/x") == (
        "gs://override/here"
    )


def test_target_location_falls_back_to_path_rules():
    config = MigrationConfig.from_dict(
        {"path_rules": [{"from": "abfss://a@b.dfs.core.windows.net/", "to": "gs://t/"}]}
    )
    assert config.target_location_for("c.s.t", "abfss://a@b.dfs.core.windows.net/x") == "gs://t/x"


def test_unmapped_location_returns_none_rather_than_inventing_a_path():
    config = MigrationConfig.from_dict({})
    assert config.target_location_for("c.s.t", "abfss://a@b.dfs.core.windows.net/x") is None


def test_json_config_parses_without_pyyaml():
    parsed = parse_config_text(json.dumps({"catalog_map": {"a": "b"}}), "config.json")
    assert parsed == {"catalog_map": {"a": "b"}}


def test_non_mapping_root_is_rejected():
    with pytest.raises(ConfigError):
        parse_config_text("- a\n- b", "config.yaml")


def test_example_config_in_the_repo_is_valid():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config = load_config(os.path.join(here, "examples", "migration.example.yaml"))
    assert config.problems() == []
    assert config.catalog_map == {"prod": "prod_gcp"}
    assert config.source.token_env == "DBX_SOURCE_TOKEN"


def test_fixture_config_in_the_repo_is_valid():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config = load_config(os.path.join(here, "examples", "migration.fixture.yaml"))
    assert config.problems() == []
