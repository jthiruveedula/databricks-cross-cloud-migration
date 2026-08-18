"""The ``CloudAssetAdapter`` interface and the ``CloudAsset`` record every provider returns.

Workspace and metastore inventory (``inventory.py``, ``workspace.py``) capture
what Databricks knows about. A cross-cloud migration also has to know what
each cloud's control plane knows about -- Key Vaults, S3 buckets, VPCs --
since that's what ``crossrefs.py``'s scanned references (a secret scope, a
storage URI, an instance profile ARN) actually resolve to. Every adapter here
is read-only: list/describe calls against the source cloud, never a write.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class CloudAsset:
    asset_id: str
    cloud: str  # azure | aws | gcp
    account_or_project: str
    resource_type: str
    name: str
    region: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    owner: str = ""
    network_context: str = ""
    dependencies: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "cloud": self.cloud,
            "account_or_project": self.account_or_project,
            "resource_type": self.resource_type,
            "name": self.name,
            "region": self.region,
            "tags": dict(self.tags),
            "owner": self.owner,
            "network_context": self.network_context,
            "dependencies": list(self.dependencies),
            "raw": dict(self.raw),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "CloudAsset":
        return cls(
            asset_id=raw["asset_id"],
            cloud=raw["cloud"],
            account_or_project=raw.get("account_or_project", ""),
            resource_type=raw.get("resource_type", ""),
            name=raw.get("name", ""),
            region=raw.get("region", ""),
            tags=dict(raw.get("tags") or {}),
            owner=raw.get("owner", ""),
            network_context=raw.get("network_context", ""),
            dependencies=list(raw.get("dependencies") or []),
            raw=dict(raw.get("raw") or {}),
        )


class CloudAssetAdapter(abc.ABC):
    """One per cloud. ``discover`` is the only entry point, and it never writes."""

    cloud: str = ""

    @abc.abstractmethod
    def discover(self, scope: Dict[str, Any]) -> List[CloudAsset]:
        """Return every asset in ``scope`` (accounts/projects, resource types, regions)."""
        raise NotImplementedError
