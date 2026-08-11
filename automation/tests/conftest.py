from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbxmig.config import MigrationConfig  # noqa: E402
from dbxmig.models import Inventory  # noqa: E402

FIXTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
FIXTURE_PATH = os.path.join(FIXTURE_DIR, "source_metastore.json")


@pytest.fixture()
def fixture_path() -> str:
    return FIXTURE_PATH


@pytest.fixture()
def raw_inventory() -> dict:
    with open(FIXTURE_PATH, encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture()
def inventory(raw_inventory: dict) -> Inventory:
    return Inventory.from_dict(raw_inventory)


@pytest.fixture()
def config() -> MigrationConfig:
    return MigrationConfig.from_dict(
        {
            "source": {"cloud": "azure", "catalogs": ["prod"]},
            "target": {"cloud": "gcp"},
            "catalog_map": {"prod": "prod_gcp"},
            "path_rules": [
                {
                    "from": "abfss://raw@prodstorage.dfs.core.windows.net/",
                    "to": "gs://acme-prod-raw/",
                }
            ],
            "managed_locations": {"prod_gcp": "gs://acme-prod-managed/catalogs/prod"},
        }
    )
