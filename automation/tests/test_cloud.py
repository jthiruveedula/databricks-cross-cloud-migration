"""Cloud discovery adapters, tested against mocked SDK clients -- no real network calls."""

from __future__ import annotations

import pytest

from dbxmig.cloud.aws import AwsAssetAdapter
from dbxmig.cloud.azure import AzureAssetAdapter
from dbxmig.cloud.base import CloudAsset
from dbxmig.cloud.gcp import GcpAssetAdapter
from dbxmig.cloud.merge import merge_with_workspace_inventory
from dbxmig.crossrefs import CrossRef


def test_cloud_asset_round_trips():
    asset = CloudAsset(
        asset_id="arn:aws:s3:::acme-raw",
        cloud="aws",
        account_or_project="123456789012",
        resource_type="s3:bucket",
        name="acme-raw",
        region="us-east-1",
        tags={"domain": "sales"},
        dependencies=["kms:key/abc"],
    )
    assert CloudAsset.from_dict(asset.to_dict()) == asset


class FakeAzureClient:
    def __init__(self, rows):
        self.rows = rows
        self.requested = None

    def resources(self, request):
        self.requested = request
        return {"data": self.rows}


def test_azure_adapter_discovers_and_maps_resource_type():
    client = FakeAzureClient(
        [
            {
                "id": "/subscriptions/sub-1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
                "name": "kv1",
                "type": "microsoft.keyvault/vaults",
                "location": "eastus",
                "resourceGroup": "rg1",
                "subscriptionId": "sub-1",
                "tags": {"env": "prod"},
                "properties": {"sku": "standard"},
            }
        ]
    )
    adapter = AzureAssetAdapter(client=client)
    assets = adapter.discover({"subscriptions": ["sub-1"]})
    assert len(assets) == 1
    asset = assets[0]
    assert asset.resource_type == "key_vault"
    assert asset.account_or_project == "sub-1"
    assert asset.network_context == "rg1"
    assert asset.tags == {"env": "prod"}


def test_azure_adapter_requires_subscriptions():
    with pytest.raises(ValueError):
        AzureAssetAdapter(client=FakeAzureClient([])).discover({})


class FakeAwsClient:
    def __init__(self, resources_by_type):
        self.resources_by_type = resources_by_type
        self.calls = []

    def search(self, QueryString, **kwargs):
        self.calls.append(QueryString)
        resource_type = QueryString.split(":", 1)[1]
        return {"Resources": self.resources_by_type.get(resource_type, [])}


def test_aws_adapter_discovers_across_resource_types():
    client = FakeAwsClient(
        {
            "s3:bucket": [
                {
                    "Arn": "arn:aws:s3:::acme-raw",
                    "OwningAccountId": "123456789012",
                    "ResourceType": "s3:bucket",
                    "Region": "us-east-1",
                    "Properties": [{"Name": "createdAt", "Data": "2024-01-01"}],
                }
            ],
            "kms:key": [],
        }
    )
    adapter = AwsAssetAdapter(client=client)
    assets = adapter.discover({"resource_types": ["s3:bucket", "kms:key"]})
    assert len(assets) == 1
    assert assets[0].name == "acme-raw"
    assert assets[0].raw == {"createdAt": "2024-01-01"}
    assert client.calls == ["resourcetype:s3:bucket", "resourcetype:kms:key"]


def test_aws_adapter_paginates():
    client = FakeAwsClient({})

    def search(QueryString, NextToken=None, **kwargs):
        if NextToken is None:
            return {
                "Resources": [{"Arn": "arn:aws:s3:::a", "OwningAccountId": "1", "ResourceType": "s3:bucket"}],
                "NextToken": "page2",
            }
        return {"Resources": [{"Arn": "arn:aws:s3:::b", "OwningAccountId": "1", "ResourceType": "s3:bucket"}]}

    client.search = search
    adapter = AwsAssetAdapter(client=client)
    assets = adapter.discover({"resource_types": ["s3:bucket"]})
    assert [a.name for a in assets] == ["a", "b"]


class FakeGcpClient:
    def __init__(self, rows):
        self.rows = rows
        self.requested = None

    def list_assets(self, request):
        self.requested = request
        return self.rows


def test_gcp_adapter_discovers():
    client = FakeGcpClient(
        [
            {
                "name": "//storage.googleapis.com/projects/_/buckets/acme-raw",
                "asset_type": "storage.googleapis.com/Bucket",
                "resource": {"location": "us", "data": {"labels": {"domain": "sales"}}},
            }
        ]
    )
    adapter = GcpAssetAdapter(client=client)
    assets = adapter.discover({"project": "acme-prod"})
    assert len(assets) == 1
    asset = assets[0]
    assert asset.name == "acme-raw"
    assert asset.account_or_project == "acme-prod"
    assert asset.tags == {"domain": "sales"}
    assert client.requested["parent"] == "projects/acme-prod"


def test_gcp_adapter_requires_project():
    with pytest.raises(ValueError):
        GcpAssetAdapter(client=FakeGcpClient([])).discover({})


def test_merge_links_crossref_to_matching_cloud_asset():
    asset = CloudAsset(
        asset_id="arn:aws:s3:::acme-raw",
        cloud="aws",
        account_or_project="123456789012",
        resource_type="s3:bucket",
        name="acme-raw",
    )
    finding = CrossRef(
        asset_class="job",
        asset_id="1",
        asset_name="nightly",
        kind="mount",
        reference="/mnt/acme-raw/orders",
        severity="attention",
        breaks="storage mount",
    )
    graph = merge_with_workspace_inventory([asset], [finding])
    assert {n.id for n in graph.nodes} == {"arn:aws:s3:::acme-raw", "job:1"}
    assert len(graph.edges) == 1
    assert graph.edges[0].target == "arn:aws:s3:::acme-raw"


def test_merge_with_no_matching_reference_yields_no_edges():
    asset = CloudAsset(
        asset_id="arn:aws:s3:::other-bucket",
        cloud="aws",
        account_or_project="1",
        resource_type="s3:bucket",
        name="other-bucket",
    )
    finding = CrossRef(
        asset_class="job",
        asset_id="1",
        asset_name="nightly",
        kind="mount",
        reference="/mnt/unrelated/orders",
        severity="attention",
        breaks="storage mount",
    )
    graph = merge_with_workspace_inventory([asset], [finding])
    assert graph.edges == []
