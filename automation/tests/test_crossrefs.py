from __future__ import annotations

import json
import os

import pytest

from dbxmig.crossrefs import (
    SEV_ATTENTION,
    SEV_BLOCKER,
    coverage_gaps,
    merge,
    scan,
    scan_source_tree,
    to_rows,
    wave_hints,
)
from dbxmig.rewrite import PathRule, Rewriter
from dbxmig.workspace import CollectionResult, WorkspaceInventory

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "workspace.json")


@pytest.fixture()
def workspace() -> WorkspaceInventory:
    with open(FIXTURE, encoding="utf-8") as handle:
        return WorkspaceInventory.from_dict(json.load(handle))


@pytest.fixture()
def rewriter() -> Rewriter:
    return Rewriter(
        path_rules=[
            PathRule("abfss://raw@prodstorage.dfs.core.windows.net/", "gs://nwr-raw/"),
        ],
        catalog_map={"prod": "prod_gcp"},
    )


def findings_of(report, kind):
    return [f for f in report.findings if f.kind == kind]


def test_mapped_path_is_informational_unmapped_path_blocks(workspace, rewriter):
    report = scan(workspace, rewriter)
    uris = {f.reference: f.severity for f in findings_of(report, "storage_uri")}
    assert uris["abfss://raw@prodstorage.dfs.core.windows.net/pipelines/orders"] != SEV_BLOCKER
    assert uris["abfss://archive@legacystorage.dfs.core.windows.net/finance/ledger"] == SEV_BLOCKER


def test_dbfs_mount_always_blocks_and_is_not_double_reported(workspace, rewriter):
    report = scan(workspace, rewriter)
    mounts = findings_of(report, "dbfs_mount")
    assert mounts and all(f.severity == SEV_BLOCKER for f in mounts)
    # The same mount must not also appear as a storage_uri finding.
    mount_refs = {f.reference for f in mounts}
    uri_refs = {f.reference for f in findings_of(report, "storage_uri")}
    assert not (mount_refs & uri_refs)


def test_secret_reference_in_spark_conf_is_extracted(workspace, rewriter):
    report = scan(workspace, rewriter)
    secrets = findings_of(report, "secret")
    assert [f.reference for f in secrets] == ["prod-etl/adls_account_key"]
    # The scope exists in the inventory, so it needs attention rather than blocking.
    assert secrets[0].severity == SEV_ATTENTION


def test_secret_scope_missing_from_the_inventory_blocks():
    inventory = WorkspaceInventory(
        assets={
            "jobs": [
                {
                    "job_id": "1",
                    "name": "j",
                    "notes": 'dbutils.secrets.get(scope="ghost", key="tok")',
                }
            ]
        }
    )
    report = scan(inventory, Rewriter())
    secret = findings_of(report, "secret")[0]
    assert secret.severity == SEV_BLOCKER
    assert "not present in the inventory" in secret.breaks


def test_both_secret_spellings_are_recognised():
    inventory = WorkspaceInventory(
        assets={
            "clusters": [{"cluster_id": "c", "name": "c", "conf": "{{secrets/s1/k1}}"}],
            "jobs": [{"job_id": "j", "name": "j", "code": "dbutils.secrets.get('s2', 'k2')"}],
        },
        results=[],
    )
    report = scan(inventory, Rewriter(), known_scopes=["s1", "s2"])
    assert {f.reference for f in findings_of(report, "secret")} == {"s1/k1", "s2/k2"}


def test_aws_instance_profile_blocks_on_a_cross_cloud_move(workspace, rewriter):
    report = scan(workspace, rewriter)
    identity = findings_of(report, "cloud_identity")
    assert identity and identity[0].severity == SEV_BLOCKER
    assert "legacy-etl-role" in identity[0].reference


def test_aws_instance_profile_is_only_an_attention_note_on_an_aws_to_aws_move(workspace, rewriter):
    """Same-cloud: the identity mechanism carries over, the specific role may not."""
    report = scan(workspace, rewriter, target_cloud="aws")
    identity = findings_of(report, "cloud_identity")
    assert identity and identity[0].severity == SEV_ATTENTION
    assert "legacy-etl-role" in identity[0].reference


def test_azure_managed_identity_blocks_on_a_move_to_a_different_cloud():
    inventory = WorkspaceInventory(
        assets={
            "clusters": [
                {
                    "cluster_id": "c",
                    "name": "c",
                    "code": (
                        "/subscriptions/11111111-1111-1111-1111-111111111111/"
                        "resourcegroups/prod-rg/providers/Microsoft.ManagedIdentity/"
                        "userAssignedIdentities/etl-identity"
                    ),
                }
            ]
        },
        results=[],
    )
    report = scan(inventory, target_cloud="gcp")
    identity = findings_of(report, "cloud_identity")
    assert identity and identity[0].severity == SEV_BLOCKER
    assert "etl-identity" in identity[0].reference


def test_gcp_service_account_is_an_attention_note_on_a_gcp_to_gcp_move():
    inventory = WorkspaceInventory(
        assets={
            "clusters": [
                {
                    "cluster_id": "c",
                    "name": "c",
                    "code": "etl-runner@my-project.iam.gserviceaccount.com",
                }
            ]
        },
        results=[],
    )
    report = scan(inventory, target_cloud="gcp")
    identity = findings_of(report, "cloud_identity")
    assert identity and identity[0].severity == SEV_ATTENTION
    assert "etl-runner@my-project.iam.gserviceaccount.com" in identity[0].reference


def test_hardcoded_workspace_url_blocks():
    inventory = WorkspaceInventory(
        assets={
            "jobs": [
                {
                    "job_id": "1",
                    "name": "j",
                    "code": "requests.get('https://adb-1234567890123456.7.azuredatabricks.net/api')",
                }
            ]
        }
    )
    report = scan(inventory, Rewriter())
    url = findings_of(report, "hardcoded_workspace_url")
    assert url and url[0].severity == SEV_BLOCKER


def test_reference_to_a_missing_policy_blocks_but_a_present_one_does_not(workspace, rewriter):
    report = scan(workspace, rewriter)
    policies = {f.reference: f.severity for f in findings_of(report, "cluster_policy")}
    assert policies["POL-RETIRED-2023"] == SEV_BLOCKER
    assert policies["POL-STANDARD-ETL"] == SEV_ATTENTION


def test_an_asset_is_not_a_dependency_of_itself(workspace, rewriter):
    report = scan(workspace, rewriter)
    assert not [f for f in report.findings if f.asset_class == "cluster_policies"]
    assert not [
        f for f in findings_of(report, "sql_warehouse") if f.asset_class == "sql_warehouses"
    ]


def test_shared_references_identify_what_must_move_together(workspace, rewriter):
    report = scan(workspace, rewriter)
    shared = report.shared_references()
    warehouse = shared["sql_warehouse=WH-FINANCE-01"]
    assert len(warehouse) == 3
    assert "dashboards:Regional revenue" in warehouse
    assert "jobs:finance-ledger-export" in warehouse
    hints = wave_hints(report)
    assert any("WH-FINANCE-01" in h for h in hints)


def test_a_single_holder_is_not_a_shared_reference(workspace, rewriter):
    report = scan(workspace, rewriter)
    assert "cloud_identity=arn:aws:iam::123456789012:instance-profile/legacy-etl-role" not in (
        report.shared_references()
    )


def test_findings_are_deduplicated(workspace, rewriter):
    report = scan(workspace, rewriter)
    keys = [f.key() for f in report.findings]
    assert len(keys) == len(set(keys))


def test_acls_and_principals_are_not_scanned_for_references(workspace, rewriter):
    report = scan(workspace, rewriter)
    scanned = {f.asset_class for f in report.findings}
    assert not scanned & {"object_acls", "groups", "service_principals"}


def test_coverage_gaps_separate_a_failure_from_an_empty_estate():
    inventory = WorkspaceInventory(
        results=[
            CollectionResult("jobs", 0, ok=False, reason="403"),
            CollectionResult("alerts", 0, ok=True, reason="none"),
            CollectionResult("clusters", 5, ok=True),
        ]
    )
    gaps = coverage_gaps(inventory)
    assert any("FAILED" in g and "jobs" in g for g in gaps)
    assert any("zero rows" in g and "alerts" in g for g in gaps)
    assert not any("clusters" in g for g in gaps)


def test_csv_rows_are_sorted_blockers_first(workspace, rewriter):
    rows = to_rows(scan(workspace, rewriter))
    assert rows[0][0] == "severity"
    severities = [r[0] for r in rows[1:]]
    assert severities[0] == SEV_BLOCKER
    assert severities == sorted(severities, key=lambda s: {"blocker": 0, "attention": 1}.get(s, 2))


def test_scan_works_with_no_rewriter_at_all(workspace):
    report = scan(workspace)
    assert report.findings
    # With no path rules, every storage URI is unmapped and therefore a blocker.
    assert all(f.severity == SEV_BLOCKER for f in findings_of(report, "storage_uri"))


# ---- source-file scanning ------------------------------------------------


def write(tmp_path, relative, text):
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_source_scan_reports_a_line_number(tmp_path, rewriter):
    write(
        tmp_path,
        "etl/load.py",
        "\n".join(
            [
                "import os",
                "",
                'ARCHIVE = "abfss://archive@legacy.dfs.core.windows.net/x"',
            ]
        ),
    )
    report = scan_source_tree(str(tmp_path), rewriter)
    finding = findings_of(report, "storage_uri")[0]
    assert finding.asset_class == "source_file"
    assert finding.asset_id == os.path.join("etl", "load.py")
    assert finding.location == "line 3"
    assert finding.severity == SEV_BLOCKER


def test_source_scan_honours_the_path_rules(tmp_path, rewriter):
    write(tmp_path, "a.py", 'p = "abfss://raw@prodstorage.dfs.core.windows.net/x"')
    finding = findings_of(scan_source_tree(str(tmp_path), rewriter), "storage_uri")[0]
    assert finding.severity != SEV_BLOCKER


def test_source_scan_finds_both_secret_spellings_with_lines(tmp_path, rewriter):
    write(
        tmp_path,
        "b.py",
        '\n'.join(
            [
                'a = dbutils.secrets.get(scope="known", key="k1")',
                'conf = "{{secrets/known/k2}}"',
            ]
        ),
    )
    report = scan_source_tree(str(tmp_path), rewriter, known_scopes=["known"])
    found = {f.reference: f.location for f in findings_of(report, "secret")}
    assert found == {"known/k1": "line 1", "known/k2": "line 2"}


def test_ipynb_source_cells_are_extracted_not_raw_json(tmp_path, rewriter):
    notebook = {
        "cells": [
            {"cell_type": "code", "source": ["import os\n", "\n"]},
            {"cell_type": "code", "source": ['p = "dbfs:/mnt/legacy/x"\n']},
        ],
        "metadata": {"note": "dbfs:/mnt/should-not-be-scanned"},
    }
    write(tmp_path, "nb.ipynb", json.dumps(notebook))
    report = scan_source_tree(str(tmp_path), rewriter)
    refs = {f.reference for f in findings_of(report, "dbfs_mount")}
    assert refs == {"dbfs:/mnt/legacy/x"}  # metadata was not scanned
    assert findings_of(report, "dbfs_mount")[0].location == "line 3"


def test_malformed_ipynb_falls_back_to_raw_text(tmp_path, rewriter):
    write(tmp_path, "broken.ipynb", '{"cells": [ truncated')
    # Must not raise; the file simply yields whatever the raw text matches.
    assert scan_source_tree(str(tmp_path), rewriter) is not None


def test_vendored_and_hidden_directories_are_skipped(tmp_path, rewriter):
    write(tmp_path, ".git/config", 'url = "dbfs:/mnt/x"')
    write(tmp_path, "node_modules/p/i.js", 'const p = "dbfs:/mnt/y"')
    write(tmp_path, "real.py", 'p = "dbfs:/mnt/z"')
    refs = {f.reference for f in scan_source_tree(str(tmp_path), rewriter).findings}
    assert refs == {"dbfs:/mnt/z"}


def test_binary_and_unlisted_extensions_are_ignored(tmp_path, rewriter):
    write(tmp_path, "data.parquet", "dbfs:/mnt/ignored")
    write(tmp_path, "notes.md", "dbfs:/mnt/also-ignored")
    assert scan_source_tree(str(tmp_path), rewriter).findings == []


def test_merge_links_a_notebook_to_the_asset_sharing_its_dependency(
    tmp_path, workspace, rewriter
):
    write(tmp_path, "etl.py", 'k = dbutils.secrets.get(scope="prod-etl", key="adls_account_key")')
    combined = merge(
        scan(workspace, rewriter),
        scan_source_tree(str(tmp_path), rewriter, known_scopes=["prod-etl"]),
    )
    shared = combined.shared_references()["secret=prod-etl/adls_account_key"]
    assert "clusters:shared-analytics" in shared
    assert any(h.startswith("source_file:") for h in shared)


def test_merge_deduplicates_across_reports(workspace, rewriter):
    once = scan(workspace, rewriter)
    assert len(merge(once, once).findings) == len(once.findings)


def test_location_is_empty_for_metadata_findings(workspace, rewriter):
    assert all(f.location == "" for f in scan(workspace, rewriter).findings)


def test_csv_includes_the_location_column(tmp_path, rewriter):
    write(tmp_path, "a.py", 'p = "dbfs:/mnt/x"')
    rows = to_rows(scan_source_tree(str(tmp_path), rewriter))
    assert rows[0] == [
        "severity",
        "asset_class",
        "asset_name",
        "asset_id",
        "location",
        "kind",
        "reference",
        "breaks",
    ]
    assert rows[1][4] == "line 1"
