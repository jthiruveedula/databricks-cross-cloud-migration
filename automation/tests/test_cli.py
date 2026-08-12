"""End-to-end CLI tests against the offline fixture.

These are the tests that prove the toolkit is runnable rather than illustrative:
every command in the documented sequence executes, in order, with no workspace
and no credentials.
"""

from __future__ import annotations

import json
import os

from dbxmig.cli import EXIT_FINDINGS, EXIT_OK, EXIT_USAGE, main

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURE = os.path.join(HERE, "fixtures", "source_metastore.json")


def write_config(tmp_path, **overrides) -> str:
    payload = {
        "source": {"cloud": "azure", "catalogs": ["prod"]},
        "target": {"cloud": "gcp"},
        "catalog_map": {"prod": "prod_gcp"},
        "path_rules": [
            {
                "from": "abfss://raw@prodstorage.dfs.core.windows.net/",
                "to": "gs://acme-prod-raw/",
            }
        ],
        "managed_locations": {"prod_gcp": "gs://acme-prod-managed/catalogs/prod"},
        "principal_map_file": os.path.join(ROOT, "examples", "principal_map.example.json"),
    }
    payload.update(overrides)
    path = str(tmp_path / "migration.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return path


def test_validate_accepts_a_good_config(tmp_path, capsys):
    assert main(["-c", write_config(tmp_path), "validate"]) == EXIT_OK
    assert "valid" in capsys.readouterr().out


def test_validate_rejects_a_bad_config(tmp_path, capsys):
    path = str(tmp_path / "bad.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"llm": {"enabled": True}}, handle)
    assert main(["-c", path, "validate"]) == EXIT_USAGE
    assert "endpoint" in capsys.readouterr().err


def test_inventory_from_fixture_round_trips(tmp_path):
    out = str(tmp_path / "inventory.json")
    argv = ["-c", write_config(tmp_path), "inventory", "--fixture", FIXTURE, "-o", out]
    assert main(argv) == EXIT_OK
    with open(out, encoding="utf-8") as handle:
        data = json.load(handle)
    assert len(data["tables"]) == 8
    assert data["cloud"] == "azure"


def test_plan_json_is_dependency_ordered(tmp_path):
    out = str(tmp_path / "plan.json")
    code = main(["-c", write_config(tmp_path), "plan", "-i", FIXTURE, "--json", "-o", out])
    assert code == EXIT_OK
    with open(out, encoding="utf-8") as handle:
        plan = json.load(handle)
    ids = [step["id"] for step in plan["steps"]]
    assert ids.index("catalog:prod") < ids.index("schema:prod.sales")
    assert plan["problems"] == []


def test_gaps_exits_nonzero_when_something_needs_a_human(tmp_path, capsys):
    code = main(["-c", write_config(tmp_path), "gaps", "-i", FIXTURE])
    assert code == EXIT_FINDINGS
    out = capsys.readouterr().out
    assert "mv_daily_sales" in out
    assert "other_metastore.finance.adjustments" in out
    # The archive location has no path rule in this config.
    assert "abfss://archive@legacystorage.dfs.core.windows.net" in out


def test_ddl_is_generated_in_order_and_flags_blocked_objects(tmp_path):
    out = str(tmp_path / "target.sql")
    code = main(["-c", write_config(tmp_path), "ddl", "-i", FIXTURE, "-o", out])
    assert code == EXIT_FINDINGS  # blocked objects exist in the fixture, by design
    sql = open(out, encoding="utf-8").read()
    assert sql.index("CREATE CATALOG IF NOT EXISTS `prod_gcp`") < sql.index(
        "CREATE SCHEMA IF NOT EXISTS `prod_gcp`.`sales`"
    )
    assert sql.index("`prod_gcp`.`sales`.`orders` DEEP CLONE") < sql.index(
        "CREATE OR REPLACE VIEW `prod_gcp`.`sales`.`v_orders_enriched`"
    )
    assert "-- BLOCKED" in sql
    assert "gs://acme-prod-managed/catalogs/prod" in sql


def test_generated_ddl_never_contains_an_unmapped_source_path(tmp_path):
    out = str(tmp_path / "target.sql")
    main(["-c", write_config(tmp_path), "ddl", "-i", FIXTURE, "-o", out])
    for line in open(out, encoding="utf-8"):
        if line.startswith("--"):
            continue
        assert "legacystorage.dfs.core.windows.net" not in line


def test_grants_are_translated_and_retired_principals_are_noted(tmp_path):
    out = str(tmp_path / "grants.sql")
    assert main(["-c", write_config(tmp_path), "grants", "-i", FIXTURE, "-o", out]) == EXIT_OK
    sql = open(out, encoding="utf-8").read()
    assert "GRANT USE CATALOG ON CATALOG `prod_gcp` TO `data-readers`;" in sql
    assert "GRANT USE SCHEMA ON SCHEMA `prod_gcp`.`sales`" in sql  # USAGE translated
    assert "TO `sales-engineering`" in sql  # principal renamed
    assert "SKIPPED SELECT on prod.finance.ledger_csv" in sql  # retired principal
    assert "CREATE_EXTERNAL_LOCATION" not in sql.split("-- SKIPPED")[0]


def test_apply_dry_run_prints_statements_and_writes_no_journal_entries(tmp_path, capsys):
    state = str(tmp_path / "journal.jsonl")
    code = main(
        ["-c", write_config(tmp_path), "apply", "-i", FIXTURE, "--state", state]
    )
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "CREATE CATALOG IF NOT EXISTS `prod_gcp`" in out
    # Blocked steps are journalled even in a dry run; executed ones are not.
    entries = [json.loads(line) for line in open(state, encoding="utf-8")]
    assert entries and all(e["status"] == "blocked" for e in entries)


def migrated_target(tmp_path) -> str:
    """The fixture as it should look after a correct migration."""
    with open(FIXTURE, encoding="utf-8") as handle:
        text = handle.read()
    text = text.replace(
        "abfss://raw@prodstorage.dfs.core.windows.net/", "gs://acme-prod-raw/"
    )
    path = str(tmp_path / "target.json")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def test_reconcile_passes_against_a_correctly_migrated_target(tmp_path):
    out = str(tmp_path / "recon.md")
    code = main(
        [
            "-c",
            write_config(tmp_path),
            "reconcile",
            "-i",
            FIXTURE,
            "-t",
            migrated_target(tmp_path),
            "-o",
            out,
        ]
    )
    assert code == EXIT_OK
    assert "PASS" in open(out, encoding="utf-8").read()


def test_reconcile_fails_a_target_still_pointing_at_source_storage(tmp_path):
    out = str(tmp_path / "recon.md")
    code = main(
        ["-c", write_config(tmp_path), "reconcile", "-i", FIXTURE, "-t", FIXTURE, "-o", out]
    )
    assert code == EXIT_FINDINGS
    content = open(out, encoding="utf-8").read()
    assert "residual_source_path" in content
    assert "prod.sales.customers" in content


def test_reconcile_fails_when_the_target_is_short_a_table(tmp_path):
    with open(FIXTURE, encoding="utf-8") as handle:
        data = json.load(handle)
    data["tables"] = [t for t in data["tables"] if t["name"] != "orders"]
    target = str(tmp_path / "target.json")
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    out = str(tmp_path / "recon.md")
    code = main(["-c", write_config(tmp_path), "reconcile", "-i", FIXTURE, "-t", target, "-o", out])
    assert code == EXIT_FINDINGS
    assert "FAIL" in open(out, encoding="utf-8").read()


def test_report_bundles_everything_into_one_markdown_file(tmp_path):
    out = str(tmp_path / "report.md")
    assert main(["-c", write_config(tmp_path), "report", "-i", FIXTURE, "-o", out]) == EXIT_OK
    content = open(out, encoding="utf-8").read()
    for heading in ("## Source inventory", "## Plan", "## Gaps requiring a decision"):
        assert heading in content
    assert "SHARE" in content  # metastore-level objects surfaced as manual work


def test_missing_inventory_file_is_a_usage_error(tmp_path, capsys):
    code = main(["-c", write_config(tmp_path), "plan", "-i", str(tmp_path / "nope.json")])
    assert code == EXIT_USAGE
    assert "missing file" in capsys.readouterr().err


def test_function_body_is_emitted_and_not_double_prefixed(tmp_path):
    out = str(tmp_path / "target.sql")
    main(["-c", write_config(tmp_path), "ddl", "-i", FIXTURE, "-o", out])
    sql = open(out, encoding="utf-8").read()
    assert "CREATE OR REPLACE FUNCTION `prod_gcp`.`sales`.`mask_email`" in sql
    assert sql.count("CREATE OR REPLACE FUNCTION") == 1
    assert "CREATE FUNCTION prod" not in sql


def test_view_reading_outside_the_scope_is_not_emitted(tmp_path):
    out = str(tmp_path / "target.sql")
    main(["-c", write_config(tmp_path), "ddl", "-i", FIXTURE, "-o", out])
    sql = open(out, encoding="utf-8").read()
    assert "CREATE OR REPLACE VIEW `prod_gcp`.`finance`.`v_external_feed`" not in sql
    assert "-- BLOCKED prod.finance.v_external_feed" in sql


def test_ownership_is_replayed_through_the_principal_map(tmp_path):
    out = str(tmp_path / "grants.sql")
    main(["-c", write_config(tmp_path), "grants", "-i", FIXTURE, "-o", out])
    sql = open(out, encoding="utf-8").read()
    assert "ALTER SCHEMA `prod_gcp`.`sales` SET OWNER TO `sales-engineering`;" in sql
    assert "ALTER CATALOG `prod_gcp` SET OWNER TO `data-platform-admins`;" in sql
    # Pipeline outputs do not exist yet at cutover, so no owner statement for them.
    assert "mv_daily_sales` SET OWNER" not in sql


def test_row_filter_and_column_masks_are_surfaced_as_work(tmp_path, capsys):
    main(["-c", write_config(tmp_path), "gaps", "-i", FIXTURE])
    out = capsys.readouterr().out
    assert "ROW_COLUMN_POLICY" in out
    assert "not copied by CLONE" in out


WORKSPACE_FIXTURE = os.path.join(HERE, "fixtures", "workspace.json")


def test_workspace_collect_from_fixture_writes_manifest_and_summary(tmp_path, capsys):
    out = str(tmp_path / "workspace.json")
    code = main(
        [
            "-c", write_config(tmp_path), "workspace",
            "--fixture", WORKSPACE_FIXTURE, "-o", out,
        ]
    )
    assert code == EXIT_OK
    data = json.load(open(out, encoding="utf-8"))
    assert len(data["assets"]["jobs"]) == 3
    err = capsys.readouterr().err
    assert "Usually owned by" in err  # the summary names a role per asset class
    assert "object_acls" in err


def test_workspace_csv_export_gives_one_file_per_asset_class(tmp_path):
    csv_dir = str(tmp_path / "csv")
    main(
        [
            "-c", write_config(tmp_path), "workspace",
            "--fixture", WORKSPACE_FIXTURE, "-o", str(tmp_path / "w.json"),
            "--csv-dir", csv_dir,
        ]
    )
    files = sorted(os.listdir(csv_dir))
    assert "jobs.csv" in files and "object_acls.csv" in files
    header = open(os.path.join(csv_dir, "jobs.csv"), encoding="utf-8").readline()
    assert "cluster_policy_ids" in header


def test_crossrefs_exits_nonzero_on_blockers_and_names_them(tmp_path, capsys):
    code = main(["-c", write_config(tmp_path), "crossrefs", "-w", WORKSPACE_FIXTURE])
    assert code == EXIT_FINDINGS
    out = capsys.readouterr().out
    assert "POL-RETIRED-2023" in out
    assert "dbfs:/mnt/legacy" in out
    assert "instance-profile/legacy-etl-role" in out
    assert "must move together" in out


def test_crossrefs_csv_is_written_when_asked(tmp_path):
    csv_path = str(tmp_path / "crossrefs.csv")
    main(
        [
            "-c", write_config(tmp_path), "crossrefs",
            "-w", WORKSPACE_FIXTURE, "--csv", csv_path,
            "-o", str(tmp_path / "r.md"),
        ]
    )
    lines = open(csv_path, encoding="utf-8").read().splitlines()
    assert lines[0].startswith("severity,asset_class")
    assert len(lines) > 5


def test_crossrefs_source_scan_adds_notebook_findings_with_lines(tmp_path, capsys):
    src = tmp_path / "src"
    (src / "etl").mkdir(parents=True)
    (src / "etl" / "load.py").write_text(
        'p = "abfss://archive@legacystorage.dfs.core.windows.net/x"\n', encoding="utf-8"
    )
    code = main(
        [
            "-c", write_config(tmp_path), "crossrefs",
            "-w", WORKSPACE_FIXTURE, "-s", str(src),
        ]
    )
    assert code == EXIT_FINDINGS
    out = capsys.readouterr().out
    assert "source_file" in out
    assert "line 1" in out


def test_bundle_command_writes_a_deployable_tree(tmp_path, capsys):
    out = str(tmp_path / "bundle")
    code = main(
        ["-c", write_config(tmp_path), "bundle", "-w", WORKSPACE_FIXTURE, "-o", out]
    )
    # Non-zero because the fixture deliberately contains a job collected
    # without --raw, which must be reported rather than silently dropped.
    assert code == EXIT_FINDINGS
    assert os.path.exists(os.path.join(out, "databricks.yml"))
    assert os.path.exists(os.path.join(out, "resources", "jobs.yml"))
    assert os.path.exists(os.path.join(out, "REVIEW.md"))
    err = capsys.readouterr().err
    assert "need review" in err
    jobs = open(os.path.join(out, "resources", "jobs.yml"), encoding="utf-8").read()
    assert "${var." in jobs
    assert "prodstorage.dfs.core.windows.net" not in jobs
