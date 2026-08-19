"""DatabricksGateway.fetch_inventory forwards warehouse_id and lineage_days.

Constructed via ``object.__new__`` to skip ``__init__``'s SDK-dependent
``_build_client`` call -- databricks-sdk is an optional extra, not installed
in the test environment, and this test only needs to prove the forwarding,
not exercise the real client.
"""

from __future__ import annotations

from dbxmig.gateway import DatabricksGateway


def test_fetch_inventory_forwards_warehouse_id_and_lineage_days(monkeypatch):
    gateway = object.__new__(DatabricksGateway)
    gateway.warehouse_id = "WH-1"
    gateway._client = object()
    gateway.dry_run = True
    gateway.executed = []

    captured = {}

    def fake_export_inventory(client, catalogs, lineage_days=90, warehouse_id=None):
        captured["client"] = client
        captured["catalogs"] = catalogs
        captured["lineage_days"] = lineage_days
        captured["warehouse_id"] = warehouse_id
        return "inventory-stand-in"

    import dbxmig.inventory as inventory_module

    monkeypatch.setattr(inventory_module, "export_inventory", fake_export_inventory)

    result = gateway.fetch_inventory(["prod"], lineage_days=30)

    assert result == "inventory-stand-in"
    assert captured == {
        "client": gateway._client,
        "catalogs": ["prod"],
        "lineage_days": 30,
        "warehouse_id": "WH-1",
    }
