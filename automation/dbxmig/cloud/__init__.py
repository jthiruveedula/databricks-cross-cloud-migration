"""Cloud-native asset discovery: Azure, AWS, and GCP resources outside Unity Catalog.

See ``base.py`` for the ``CloudAssetAdapter`` interface every provider adapter
implements, and ``merge.py`` for cross-referencing discovered assets against
the workspace inventory's scanned references (``crossrefs.py``).
"""

from __future__ import annotations

from .base import CloudAsset, CloudAssetAdapter
from .merge import AssetEdge, AssetGraph, AssetNode, merge_with_workspace_inventory

__all__ = [
    "CloudAsset",
    "CloudAssetAdapter",
    "AssetGraph",
    "AssetNode",
    "AssetEdge",
    "merge_with_workspace_inventory",
]
