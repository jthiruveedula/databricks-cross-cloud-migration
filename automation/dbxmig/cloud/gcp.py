"""GCP asset discovery via Cloud Asset Inventory.

Read-only: a single ``list_assets`` call per project. Requires only the
built-in ``roles/cloudasset.viewer`` role -- no per-service permissions,
no writes.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .base import CloudAsset, CloudAssetAdapter

ASSET_TYPES = [
    "storage.googleapis.com/Bucket",
    "cloudkms.googleapis.com/CryptoKey",
    "compute.googleapis.com/Network",
    "compute.googleapis.com/ServiceAttachment",
    "pubsub.googleapis.com/Topic",
    "dataflow.googleapis.com/Job",
    "bigquery.googleapis.com/Dataset",
]


class GcpAssetAdapter(CloudAssetAdapter):
    cloud = "gcp"

    def __init__(self, client: Any = None) -> None:
        self._client = client or self._build_client()

    @staticmethod
    def _build_client() -> Any:
        try:
            from google.cloud import asset_v1  # type: ignore import-not-found
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "google-cloud-asset is not installed. Install the live extra:\n"
                "    pip install 'dbxmig[gcp]'"
            ) from exc
        return asset_v1.AssetServiceClient()

    def discover(self, scope: Dict[str, Any]) -> List[CloudAsset]:
        project = scope.get("project")
        if not project:
            raise ValueError("gcp scope requires 'project': '<project id>'")
        asset_types = scope.get("asset_types") or ASSET_TYPES
        request = {
            "parent": "projects/{0}".format(project),
            "asset_types": list(asset_types),
            "content_type": "RESOURCE",
        }
        response = self._client.list_assets(request=request)
        return [self._to_asset(row, project) for row in response]

    @staticmethod
    def _to_asset(row: Any, project: str) -> CloudAsset:
        get = row.get if isinstance(row, dict) else (lambda k, d=None: getattr(row, k, d))
        name = str(get("name", ""))
        resource = get("resource", {}) or {}
        resource_get = (
            resource.get
            if isinstance(resource, dict)
            else (lambda k, d=None: getattr(resource, k, d))
        )
        data = resource_get("data", {}) or {}
        data_get = data.get if isinstance(data, dict) else (lambda k, d=None: getattr(data, k, d))
        return CloudAsset(
            asset_id=name,
            cloud="gcp",
            account_or_project=project,
            resource_type=str(get("asset_type", "")),
            name=name.rsplit("/", 1)[-1],
            region=str(resource_get("location", "")),
            tags=dict(data_get("labels", {}) or {}),
            raw=dict(data) if isinstance(data, dict) else {},
        )
