"""Streaming/DLT discovery: structured fields from pipelines, regex scan from source."""

from __future__ import annotations

from dbxmig.streaming import (
    MIGRATION_STRATEGIES,
    StreamingAsset,
    StreamingReport,
    discover,
    discover_dlt_pipelines,
    scan_source_tree,
)
from dbxmig.workspace import WorkspaceInventory

QUERY_SOURCE = """
df = (
    spark.readStream.format("kafka")
    .option("kafka.bootstrap.servers", "broker1.example.com:9092")
    .load()
)
(
    df.withWatermark("event_time", "10 minutes")
    .writeStream.outputMode("append")
    .queryName("orders_stream")
    .option("checkpointLocation", "/mnt/checkpoints/orders")
    .trigger(processingTime="1 minute")
    .start()
)
"""


def test_migration_strategies_are_closed_and_default_none():
    asset = StreamingAsset(asset_id="a", kind="dlt_pipeline", name="x")
    assert asset.migration_strategy is None
    assert {"rebuild_and_replay", "dual_write_dual_read", "replicate_topic", "retire"} == (
        MIGRATION_STRATEGIES
    )


def test_streaming_asset_round_trips():
    asset = StreamingAsset(
        asset_id="p1", kind="dlt_pipeline", name="orders_dlt", channel="PREVIEW", continuous=True
    )
    assert StreamingAsset.from_dict(asset.to_dict()) == asset


def test_discover_dlt_pipelines_reads_channel_and_expectations_from_raw_spec():
    inventory = WorkspaceInventory(
        assets={
            "pipelines": [
                {
                    "pipeline_id": "p1",
                    "name": "orders_dlt",
                    "continuous": True,
                    "storage": "/mnt/dlt/orders",
                    "raw": {
                        "spec": {
                            "channel": "PREVIEW",
                            "libraries": [
                                {"expectations": [{"name": "valid_order_id"}]},
                            ],
                        }
                    },
                }
            ]
        }
    )
    assets = discover_dlt_pipelines(inventory)
    assert len(assets) == 1
    asset = assets[0]
    assert asset.channel == "PREVIEW"
    assert asset.continuous is True
    assert asset.storage_location == "/mnt/dlt/orders"
    assert asset.expectations == ["valid_order_id"]
    assert asset.migration_strategy is None


def test_scan_source_tree_finds_structured_streaming_signals(tmp_path):
    notebook = tmp_path / "orders_stream.py"
    notebook.write_text(QUERY_SOURCE, encoding="utf-8")
    assets = scan_source_tree(str(tmp_path))
    assert len(assets) == 1
    asset = assets[0]
    assert asset.source_type == "kafka"
    assert asset.checkpoint_location == "/mnt/checkpoints/orders"
    assert asset.watermark == "event_time: 10 minutes"
    assert asset.output_mode == "append"
    assert asset.external_sources == ["broker1.example.com:9092"]


def test_scan_source_tree_ignores_files_with_no_streaming_calls(tmp_path):
    (tmp_path / "batch.py").write_text("df = spark.read.table('x')\n", encoding="utf-8")
    assert scan_source_tree(str(tmp_path)) == []


def test_discover_combines_pipelines_and_source_scan(tmp_path):
    (tmp_path / "orders_stream.py").write_text(QUERY_SOURCE, encoding="utf-8")
    inventory = WorkspaceInventory(
        assets={"pipelines": [{"pipeline_id": "p1", "name": "orders_dlt"}]}
    )
    report = discover(inventory, source_root=str(tmp_path))
    assert {a.kind for a in report.assets} == {"dlt_pipeline", "structured_streaming"}
    assert len(report.unassigned) == 2


def test_report_unassigned_excludes_reviewer_set_strategies():
    report = StreamingReport(
        assets=[
            StreamingAsset(
                asset_id="a", kind="dlt_pipeline", name="x", migration_strategy="retire"
            ),
            StreamingAsset(asset_id="b", kind="dlt_pipeline", name="y"),
        ]
    )
    assert [a.asset_id for a in report.unassigned] == ["b"]
