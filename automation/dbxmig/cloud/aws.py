"""AWS asset discovery via Resource Explorer 2.

Read-only: ``resource-explorer-2:Search`` against a single view. Requires an
account-level Resource Explorer index (any account with Resource Explorer
turned on already has one) plus the read-only
``ResourceExplorerReadOnlyAccess`` managed policy -- no per-service
permissions, no writes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import CloudAsset, CloudAssetAdapter

#: Resource Explorer resource-type filters this adapter pulls.
RESOURCE_TYPES = [
    "s3:bucket",
    "kms:key",
    "ec2:vpc-endpoint",
    "route53:hostedzone",
    "glue:database",
    "glue:table",
    "kafka:cluster",
    "redshift:cluster",
]


class AwsAssetAdapter(CloudAssetAdapter):
    cloud = "aws"

    def __init__(self, client: Any = None) -> None:
        self._client = client or self._build_client()

    @staticmethod
    def _build_client() -> Any:
        try:
            import boto3  # type: ignore import-not-found
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "boto3 is not installed. Install the live extra:\n"
                "    pip install 'dbxmig[aws]'"
            ) from exc
        return boto3.client("resource-explorer-2")

    def discover(self, scope: Dict[str, Any]) -> List[CloudAsset]:
        view_arn = scope.get("view_arn")
        resource_types = scope.get("resource_types") or RESOURCE_TYPES
        assets: List[CloudAsset] = []
        for resource_type in resource_types:
            assets.extend(self._search(resource_type, view_arn))
        return assets

    def _search(self, resource_type: str, view_arn: Optional[str]) -> List[CloudAsset]:
        kwargs: Dict[str, Any] = {"QueryString": "resourcetype:{0}".format(resource_type)}
        if view_arn:
            kwargs["ViewArn"] = view_arn
        assets: List[CloudAsset] = []
        next_token = None
        while True:
            if next_token:
                kwargs["NextToken"] = next_token
            response = self._client.search(**kwargs)
            for row in response.get("Resources", []):
                assets.append(self._to_asset(row))
            next_token = response.get("NextToken")
            if not next_token:
                break
        return assets

    @staticmethod
    def _to_asset(row: Dict[str, Any]) -> CloudAsset:
        arn = row.get("Arn", "")
        properties = {p.get("Name"): p.get("Data") for p in row.get("Properties") or []}
        return CloudAsset(
            asset_id=arn,
            cloud="aws",
            account_or_project=row.get("OwningAccountId", ""),
            resource_type=row.get("ResourceType", ""),
            name=arn.rsplit("/", 1)[-1].rsplit(":", 1)[-1] if arn else "",
            region=row.get("Region", ""),
            raw=properties,
        )
