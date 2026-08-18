"""Cross-reference cloud assets against the workspace inventory's scanned references.

``crossrefs.py`` extracts references out of jobs/notebooks/pipelines -- mount
paths, instance-profile ARNs, secret scopes, workspace URLs. This module
matches those references' names against the cloud assets discovered here so a
job's ``/mnt/sales-raw`` reference resolves to the actual ADLS/S3 asset it
depends on, producing one graph the migration can reason over.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Set

from .base import CloudAsset


@dataclass
class AssetNode:
    id: str
    kind: str  # "cloud" | "workspace"
    label: str
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "label": self.label, "raw": self.raw}


@dataclass
class AssetEdge:
    source: str
    target: str
    relation: str

    def to_dict(self) -> Dict[str, Any]:
        return {"source": self.source, "target": self.target, "relation": self.relation}


@dataclass
class AssetGraph:
    nodes: List[AssetNode] = field(default_factory=list)
    edges: List[AssetEdge] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }


def _reference_matches(reference: str, asset: CloudAsset) -> bool:
    """A crossref names a path/ARN/URI; a cloud asset names itself and its id.

    Match if either names the other -- an asset id containing the reference
    (a mount path naming a storage account) or the reference containing the
    asset's short name (a secret scope naming a vault).
    """
    if not reference or not asset.name:
        return False
    reference_l = reference.lower()
    name_l = asset.name.lower()
    return name_l in reference_l or reference_l in asset.asset_id.lower()


def merge_with_workspace_inventory(cloud_assets: Iterable[CloudAsset], crossref_findings: Iterable[Any]) -> AssetGraph:
    """Build a unified graph of cloud assets and the workspace assets that reference them.

    ``crossref_findings`` is the ``CrossRef`` list from ``crossrefs.py``
    (``asset_class``, ``asset_id``, ``asset_name``, ``kind``, ``reference``).
    """
    graph = AssetGraph()
    cloud_assets = list(cloud_assets)
    for asset in cloud_assets:
        graph.nodes.append(AssetNode(id=asset.asset_id, kind="cloud", label=asset.name, raw=asset.to_dict()))

    seen_workspace: Set[str] = set()
    for finding in crossref_findings:
        workspace_id = "{0}:{1}".format(finding.asset_class, finding.asset_id)
        if workspace_id not in seen_workspace:
            seen_workspace.add(workspace_id)
            graph.nodes.append(
                AssetNode(id=workspace_id, kind="workspace", label=finding.asset_name or finding.asset_id)
            )
        for asset in cloud_assets:
            if _reference_matches(finding.reference, asset):
                graph.edges.append(AssetEdge(source=workspace_id, target=asset.asset_id, relation=finding.kind))
    return graph
