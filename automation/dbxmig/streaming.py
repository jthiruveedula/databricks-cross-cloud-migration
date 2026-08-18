"""Streaming and event-driven workload discovery.

``workspace.py`` collects jobs and pipelines as static configuration --
schedule, cluster, notebook path. None of that says whether a job is a batch
run or a Structured Streaming query that never stops, what it checkpoints to,
or what external broker it reads from. That distinction decides the whole
migration approach for the asset: a batch job just runs in the target: a
streaming query has to be re-pointed at a checkpoint, replayed, or dual-run
against both clouds during cutover.

Discovery here follows the same two-source pattern as ``crossrefs.py``:
structured fields read straight off collected pipeline metadata, plus a
regex scan of exported notebook/job source for what metadata alone can't
show -- ``readStream``/``writeStream`` calls, watermarks, checkpoint
locations, and the Kafka/Event Hubs/Pub-Sub endpoints they point at.

Every discovered asset gets a ``migration_strategy`` -- but this module never
assigns one. A blank strategy is a decision a human owns, not a default the
toolkit picks; see ``gaps in the migration report`` for where an unset one
surfaces.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .crossrefs import MAX_FILE_BYTES, SKIP_DIRS, SOURCE_EXTENSIONS, notebook_source
from .workspace import WorkspaceInventory

#: The only values a human reviewer may set. ``None`` means "not yet decided" --
#: see ``coverage_gaps`` -- and is never assigned automatically.
MIGRATION_STRATEGIES = frozenset(
    {"rebuild_and_replay", "dual_write_dual_read", "replicate_topic", "retire"}
)

KIND_STRUCTURED_STREAMING = "structured_streaming"
KIND_DLT_PIPELINE = "dlt_pipeline"

_READ_STREAM_FORMAT = re.compile(r"readStream\s*(?:\.format\s*\(\s*['\"]([^'\"]+)['\"])?")
_CHECKPOINT = re.compile(r"""checkpointLocation['"]?\s*[,=)]\s*['"]([^'"]+)['"]""")
_TRIGGER = re.compile(r"""\.trigger\s*\(\s*([^)]*)\)""")
_WATERMARK = re.compile(r"""\.withWatermark\s*\(\s*['"]([^'"]+)['"]\s*,\s*['"]([^'"]+)['"]""")
_OUTPUT_MODE = re.compile(r"""\.outputMode\s*\(\s*['"]([^'"]+)['"]""")
_QUERY_NAME = re.compile(r"""\.queryName\s*\(\s*['"]([^'"]+)['"]""")

#: External event sources referenced in code -- the broker a rebuilt query
#: has to be re-pointed at, or the topic a replication job has to mirror.
_KAFKA_BOOTSTRAP = re.compile(
    r"""kafka\.bootstrap\.servers['"]?\s*[,=)]\s*['"]([^'"]+)['"]"""
)
_EVENT_HUB_NAMESPACE = re.compile(r"[a-z0-9-]+\.servicebus\.windows\.net")
_PUBSUB_TOPIC = re.compile(r"projects/[^/'\"\s]+/topics/[^/'\"\s]+")


@dataclass(frozen=True)
class StreamingAsset:
    """One streaming or event-driven workload, migration strategy still unset."""

    asset_id: str
    kind: str  # structured_streaming | dlt_pipeline
    name: str
    source_type: str = ""
    checkpoint_location: str = ""
    trigger: str = ""
    watermark: str = ""
    output_mode: str = ""
    external_sources: List[str] = field(default_factory=list)
    expectations: List[str] = field(default_factory=list)
    channel: str = ""
    continuous: bool = False
    storage_location: str = ""
    location: str = ""  # "path:line" for a source-scanned asset, "" for API metadata
    migration_strategy: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "StreamingAsset":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known})


@dataclass
class StreamingReport:
    assets: List[StreamingAsset] = field(default_factory=list)

    def add(self, asset: StreamingAsset) -> None:
        self.assets.append(asset)

    @property
    def unassigned(self) -> List[StreamingAsset]:
        """Assets with no reviewer-set strategy -- what ``dbxmig gaps`` must flag."""
        return [a for a in self.assets if a.migration_strategy is None]

    def to_dicts(self) -> List[Dict[str, Any]]:
        return [a.to_dict() for a in self.assets]


def discover_dlt_pipelines(inventory: WorkspaceInventory) -> List[StreamingAsset]:
    """DLT/Lakeflow pipeline configs already captured by ``workspace.py``.

    Channel and expectations live inside the pipeline's ``spec`` payload,
    which is only present when the workspace collection ran with
    ``--raw`` (see ``workspace.py``'s ``flatten_pipeline``).
    """
    assets: List[StreamingAsset] = []
    for row in inventory.rows("pipelines"):
        raw = row.get("raw") or {}
        spec = raw.get("spec") or {}
        expectations = [
            str(expectation.get("name", ""))
            for library in spec.get("libraries") or []
            for expectation in library.get("expectations") or []
        ]
        assets.append(
            StreamingAsset(
                asset_id=str(row.get("pipeline_id", "")),
                kind=KIND_DLT_PIPELINE,
                name=str(row.get("name", "")),
                channel=str(spec.get("channel", "")),
                continuous=bool(row.get("continuous", False)),
                storage_location=str(row.get("storage", "")),
                expectations=expectations,
            )
        )
    return assets


def _to_asset(path: str, fields: Dict[str, Any]) -> StreamingAsset:
    return StreamingAsset(
        asset_id=path,
        kind=KIND_STRUCTURED_STREAMING,
        name=os.path.basename(path),
        source_type=fields.get("source_type", ""),
        checkpoint_location=fields.get("checkpoint_location", ""),
        trigger=fields.get("trigger", ""),
        watermark=fields.get("watermark", ""),
        output_mode=fields.get("output_mode", ""),
        external_sources=sorted(fields.get("external_sources", set())),
        location=path,
    )


def _scan_text(text: str) -> Optional[Dict[str, Any]]:
    """Every streaming signal found in one file's text, or ``None`` if it has none."""
    read_stream = _READ_STREAM_FORMAT.search(text)
    if read_stream is None:
        return None
    external_sources: set = set()
    external_sources.update(_KAFKA_BOOTSTRAP.findall(text))
    external_sources.update(_EVENT_HUB_NAMESPACE.findall(text))
    external_sources.update(_PUBSUB_TOPIC.findall(text))

    checkpoint = _CHECKPOINT.search(text)
    trigger = _TRIGGER.search(text)
    watermark = _WATERMARK.search(text)
    output_mode = _OUTPUT_MODE.search(text)

    return {
        "source_type": read_stream.group(1) or "",
        "checkpoint_location": checkpoint.group(1) if checkpoint else "",
        "trigger": trigger.group(1).strip() if trigger else "",
        "watermark": "{0}: {1}".format(*watermark.groups()) if watermark else "",
        "output_mode": output_mode.group(1) if output_mode else "",
        "external_sources": external_sources,
    }


def scan_source_tree(root: str, extensions: "tuple" = SOURCE_EXTENSIONS) -> List[StreamingAsset]:
    """Find Structured Streaming queries in exported notebooks / repo source.

    Mirrors ``crossrefs.scan_source_tree``'s file walk -- same extensions,
    same size cap, same notebook-cell unwrapping -- so both scans see the
    same files the same way.
    """
    assets: List[StreamingAsset] = []
    lowered = tuple(e.lower() for e in extensions)
    for directory, subdirs, filenames in os.walk(root):
        subdirs[:] = [d for d in subdirs if d not in SKIP_DIRS and not d.startswith(".")]
        for filename in sorted(filenames):
            if not filename.lower().endswith(lowered):
                continue
            path = os.path.join(directory, filename)
            try:
                if os.path.getsize(path) > MAX_FILE_BYTES:
                    continue
                with open(path, "r", encoding="utf-8", errors="replace") as handle:
                    text = handle.read()
            except OSError:
                continue
            fields = _scan_text(notebook_source(text, filename))
            if fields is not None:
                assets.append(_to_asset(os.path.relpath(path, root), fields))
    return assets


def discover(inventory: WorkspaceInventory, source_root: Optional[str] = None) -> StreamingReport:
    """Full streaming discovery: DLT pipeline configs plus a source-tree scan."""
    report = StreamingReport()
    for asset in discover_dlt_pipelines(inventory):
        report.add(asset)
    if source_root:
        for asset in scan_source_tree(source_root):
            report.add(asset)
    return report
