"""Azure asset discovery via Azure Resource Graph.

Read-only: a single Resource Graph query per scope, no per-resource detail
calls. Requires only the built-in ``Reader`` role on the target
subscriptions -- Resource Graph exposes everything Reader can see already.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from .base import CloudAsset, CloudAssetAdapter

#: Azure resource types this adapter pulls, mapped to a short resource_type label.
RESOURCE_TYPES = {
    "microsoft.keyvault/vaults": "key_vault",
    "microsoft.storage/storageaccounts": "adls_gen2",
    "microsoft.eventhub/namespaces": "event_hub",
    "microsoft.datafactory/factories": "adf",
    "microsoft.network/privateendpoints": "private_endpoint",
    "microsoft.network/virtualnetworks": "vnet",
}

_QUERY = "Resources | where type in ({0}) | project id, name, type, location, resourceGroup, subscriptionId, tags, properties".format(
    ", ".join("'{0}'".format(t) for t in RESOURCE_TYPES)
)


class AzureAssetAdapter(CloudAssetAdapter):
    cloud = "azure"

    def __init__(self, client: Any = None) -> None:
        self._client = client or self._build_client()

    @staticmethod
    def _build_client() -> Any:
        try:
            from azure.identity import DefaultAzureCredential  # type: ignore import-not-found
            from azure.mgmt.resourcegraph import ResourceGraphClient  # type: ignore import-not-found
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "azure-mgmt-resourcegraph is not installed. Install the live extra:\n"
                "    pip install 'dbxmig[azure]'"
            ) from exc
        return ResourceGraphClient(DefaultAzureCredential())

    def discover(self, scope: Dict[str, Any]) -> List[CloudAsset]:
        subscriptions: Sequence[str] = scope.get("subscriptions") or []
        if not subscriptions:
            raise ValueError("azure scope requires 'subscriptions': [<subscription id>, ...]")
        response = self._client.resources(self._request(list(subscriptions)))
        rows = response.data if hasattr(response, "data") else response.get("data", [])
        return [self._to_asset(row) for row in rows]

    @staticmethod
    def _request(subscriptions: List[str]) -> Any:
        """A ``QueryRequest`` when the SDK is installed, a plain dict otherwise.

        The live client requires the typed request; a test-injected mock
        client only cares that it receives *something* naming the query.
        """
        try:
            from azure.mgmt.resourcegraph.models import QueryRequest  # type: ignore import-not-found
        except ImportError:
            return {"subscriptions": subscriptions, "query": _QUERY}
        return QueryRequest(subscriptions=subscriptions, query=_QUERY)

    def _to_asset(self, row: Any) -> CloudAsset:
        get = row.get if isinstance(row, dict) else (lambda k, d=None: getattr(row, k, d))
        resource_type = RESOURCE_TYPES.get(str(get("type", "")).lower(), get("type", ""))
        return CloudAsset(
            asset_id=str(get("id", "")),
            cloud=self.cloud,
            account_or_project=str(get("subscriptionId", "")),
            resource_type=resource_type,
            name=str(get("name", "")),
            region=str(get("location", "")),
            tags=dict(get("tags") or {}),
            network_context=str(get("resourceGroup", "")),
            raw=dict(get("properties") or {}),
        )
