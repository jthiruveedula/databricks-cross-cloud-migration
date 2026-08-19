"""The only module that talks to a Databricks workspace.

Everything else in the toolkit works on plain dataclasses, which is what makes
the plan, DDL, grant, and reconciliation logic testable without credentials and
reviewable without a workspace. Two gateways implement the same surface:

* ``DatabricksGateway`` -- the real one. Imports the SDK lazily so the package
  installs and its tests run with no cloud dependency at all.
* ``FixtureGateway`` -- reads a JSON inventory from disk. Used by the test suite
  and by ``--fixture`` on the CLI, so the whole pipeline can be demonstrated and
  reviewed end to end before anyone points it at production.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .models import Inventory


class Gateway:
    """Interface the inventory and execution paths depend on."""

    read_only: bool = True

    def fetch_inventory(
        self, catalogs: Optional[Sequence[str]] = None, lineage_days: int = 90
    ) -> Inventory:
        raise NotImplementedError

    def execute(self, statement: str) -> Dict[str, Any]:
        raise NotImplementedError

    def query_rows(self, statement: str) -> List[Dict[str, Any]]:
        raise NotImplementedError


@dataclass
class FixtureGateway(Gateway):
    """Offline gateway backed by a JSON inventory file.

    ``execute`` records statements instead of running them, which makes it a
    dry-run driver as well as a test double: the recorded list is exactly the
    SQL a real run would have issued, in order.
    """

    inventory_path: Optional[str] = None
    inventory_data: Optional[Dict[str, Any]] = None
    executed: List[str] = field(default_factory=list)
    query_results: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    read_only: bool = True

    def fetch_inventory(
        self, catalogs: Optional[Sequence[str]] = None, lineage_days: int = 90
    ) -> Inventory:
        data = self.inventory_data
        if data is None:
            if not self.inventory_path:
                raise ValueError("FixtureGateway needs inventory_path or inventory_data")
            with open(self.inventory_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        inventory = Inventory.from_dict(data)
        if catalogs:
            wanted = set(catalogs)
            inventory.catalogs = [c for c in inventory.catalogs if c.name in wanted]
            inventory.schemas = [s for s in inventory.schemas if s.catalog in wanted]
            inventory.tables = [t for t in inventory.tables if t.catalog in wanted]
            inventory.volumes = [v for v in inventory.volumes if v.catalog in wanted]
            inventory.functions = [f for f in inventory.functions if f.catalog in wanted]
            inventory.models = [m for m in inventory.models if m.catalog in wanted]
            inventory.grants = [
                g for g in inventory.grants if g.full_name.split(".")[0] in wanted
            ]
        return inventory

    def execute(self, statement: str) -> Dict[str, Any]:
        self.executed.append(statement)
        return {"status": "recorded", "statement": statement}

    def query_rows(self, statement: str) -> List[Dict[str, Any]]:
        return self.query_results.get(statement, [])


class DatabricksGateway(Gateway):
    """Live gateway. Reads through the SDK, writes through a SQL warehouse.

    Reads use the Unity Catalog APIs rather than ``information_schema`` so the
    inventory is complete for a metastore admin regardless of which catalogs the
    running warehouse can see.
    """

    read_only = False

    def __init__(
        self,
        host: str,
        warehouse_id: str,
        token: Optional[str] = None,
        profile: Optional[str] = None,
        dry_run: bool = False,
    ) -> None:
        self.host = host
        self.warehouse_id = warehouse_id
        self.dry_run = dry_run
        self.executed: List[str] = []
        self._client = self._build_client(host, token, profile)

    @property
    def client(self) -> Any:
        """The underlying SDK client, for callers that need APIs beyond SQL."""
        return self._client

    @staticmethod
    def _build_client(host: str, token: Optional[str], profile: Optional[str]) -> Any:
        try:
            from databricks.sdk import WorkspaceClient  # type: ignore import-not-found
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "databricks-sdk is not installed. Install the live extra:\n"
                "    pip install 'dbxmig[databricks]'"
            ) from exc
        if profile:
            return WorkspaceClient(profile=profile)
        return WorkspaceClient(host=host, token=token)

    # ---- reads ----------------------------------------------------------

    def fetch_inventory(
        self, catalogs: Optional[Sequence[str]] = None, lineage_days: int = 90
    ) -> Inventory:
        from .inventory import export_inventory

        return export_inventory(
            self._client, catalogs, lineage_days=lineage_days, warehouse_id=self.warehouse_id
        )

    # ---- writes ---------------------------------------------------------

    def execute(self, statement: str) -> Dict[str, Any]:
        self.executed.append(statement)
        if self.dry_run:
            return {"status": "dry_run", "statement": statement}
        response = self._client.statement_execution.execute_statement(
            statement=statement,
            warehouse_id=self.warehouse_id,
            wait_timeout="50s",
        )
        status = getattr(getattr(response, "status", None), "state", None)
        state = getattr(status, "value", status)
        if str(state).upper() not in ("SUCCEEDED", "SUCCESS"):
            error = getattr(getattr(response, "status", None), "error", None)
            message = getattr(error, "message", None) or str(state)
            raise RuntimeError("statement failed ({0}): {1}".format(state, message))
        return {"status": "succeeded", "statement": statement}

    def query_rows(self, statement: str) -> List[Dict[str, Any]]:
        response = self._client.statement_execution.execute_statement(
            statement=statement,
            warehouse_id=self.warehouse_id,
            wait_timeout="50s",
        )
        manifest = getattr(response, "manifest", None)
        schema = getattr(manifest, "schema", None)
        columns = [c.name for c in (getattr(schema, "columns", None) or [])]
        result = getattr(response, "result", None)
        data = getattr(result, "data_array", None) or []
        return [dict(zip(columns, row)) for row in data]
