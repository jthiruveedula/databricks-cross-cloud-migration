"""Command-line entry point.

The commands map onto the phases of a metastore migration and are meant to be
run in order:

    dbxmig inventory   # capture the source metastore
    dbxmig plan        # order it into executable steps
    dbxmig gaps        # what will not migrate on its own -- read this one
    dbxmig ddl         # emit the target SQL for review
    dbxmig grants      # emit the translated GRANT statements
    dbxmig apply       # execute, resumably (--execute to leave dry-run)
    dbxmig reconcile   # prove the target matches the source

``apply`` is dry-run by default and prints the statements it would issue.
Executing for real takes an explicit ``--execute``, because a metastore
migration is not something to start by accident.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import List, Optional, Sequence

from . import __version__
from .config import ConfigError, MigrationConfig, load_config, load_principal_map
from .crossrefs import coverage_gaps, merge, scan, scan_source_tree, to_rows
from .ddl import (
    create_catalog,
    create_external_location,
    create_function,
    create_schema,
    create_view,
    create_volume,
    set_owner,
    table_ddl_bundle,
)
from .depgraph import (
    CREATE_VIEW,
    CTAS,
    DEEP_CLONE,
    TIER_CATALOG,
    TIER_CONSTRAINT,
    TIER_EXTERNAL_LOCATION,
    TIER_FUNCTION,
    TIER_SCHEMA,
    TIER_TABLE,
    TIER_VIEW,
    TIER_VOLUME,
    Plan,
    build_plan,
    validate_plan,
)
from .gateway import DatabricksGateway, FixtureGateway, Gateway
from .grants import PrincipalMap, translate_grants
from .llm import Assistant, NullLlmClient
from .models import Inventory
from .reconcile import reconcile_inventories
from .report import (
    crossref_summary,
    full_report,
    gap_report,
    plan_summary,
    reconciliation_summary,
    workspace_summary,
)
from .state import STATUS_BLOCKED, STATUS_DONE, STATUS_FAILED, Journal
from .workspace import (
    ASSET_CLASSES,
    WorkspaceInventory,
    collect_workspace_inventory,
    csv_rows,
)

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2


def _load_inventory(path: str) -> Inventory:
    with open(path, "r", encoding="utf-8") as handle:
        return Inventory.from_dict(json.load(handle))


def _write(path: Optional[str], content: str) -> None:
    if not path:
        sys.stdout.write(content if content.endswith("\n") else content + "\n")
        return
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content if content.endswith("\n") else content + "\n")


def _gateway(config: MigrationConfig, args: argparse.Namespace, side: str = "source") -> Gateway:
    if getattr(args, "fixture", None):
        return FixtureGateway(inventory_path=args.fixture)
    workspace = config.source if side == "source" else config.target
    if not workspace.host:
        raise ConfigError("{0}.host is required to reach a live workspace".format(side))
    return DatabricksGateway(
        host=workspace.host,
        warehouse_id=workspace.warehouse_id,
        token=workspace.token,
        profile=workspace.profile,
        dry_run=not getattr(args, "execute", False),
    )


def _plan_from(config: MigrationConfig, inventory: Inventory) -> Plan:
    locations = {
        table.full_name: location
        for table in inventory.tables
        for location in [config.target_location_for(table.full_name, table.storage_location)]
        if location
    }
    return build_plan(inventory, catalog_map=config.catalog_map, target_location_for=locations)


def _principal_map(config: MigrationConfig) -> PrincipalMap:
    if not config.principal_map_file:
        return PrincipalMap()
    return PrincipalMap.from_dict(load_principal_map(config.principal_map_file))


# ---- commands -----------------------------------------------------------


def cmd_inventory(config: MigrationConfig, args: argparse.Namespace) -> int:
    gateway = _gateway(config, args)
    inventory = gateway.fetch_inventory(config.source.catalogs or None)
    inventory.cloud = inventory.cloud or config.source.cloud
    _write(args.out, json.dumps(inventory.to_dict(), indent=2, sort_keys=True))
    if args.out:
        print("wrote inventory for {0} table(s) to {1}".format(len(inventory.tables), args.out))
    return EXIT_OK


def cmd_plan(config: MigrationConfig, args: argparse.Namespace) -> int:
    inventory = _load_inventory(args.inventory)
    plan = _plan_from(config, inventory)
    problems = validate_plan(plan)
    if args.json:
        payload = {
            "steps": [
                {
                    "id": s.id,
                    "tier": s.tier,
                    "action": s.action,
                    "object_type": s.object_type,
                    "source_name": s.source_name,
                    "target_name": s.target_name,
                    "strategy": s.strategy,
                    "depends_on": s.depends_on,
                    "blocked_reason": s.blocked_reason,
                    "detail": s.detail,
                }
                for s in plan.steps
            ],
            "dangling_references": plan.dangling_references,
            "cycles": plan.cycles,
            "problems": problems,
        }
        _write(args.out, json.dumps(payload, indent=2, sort_keys=True))
    else:
        lines = [plan_summary(plan), ""]
        for step in plan.steps:
            marker = "BLOCKED" if step.blocked else step.strategy
            lines.append(
                "{0:<6} {1:<16} {2:<40} {3}".format(
                    step.tier, marker, step.source_name, step.id
                )
            )
        _write(args.out, "\n".join(lines))
    if problems:
        for problem in problems:
            print("plan problem: " + problem, file=sys.stderr)
        return EXIT_FINDINGS
    return EXIT_OK


def cmd_gaps(config: MigrationConfig, args: argparse.Namespace) -> int:
    inventory = _load_inventory(args.inventory)
    plan = _plan_from(config, inventory)
    principal_map = _principal_map(config)
    translation = translate_grants(
        inventory.grants, principal_map, config.catalog_map, strict=False
    )
    content = gap_report(plan, config.rewriter(), inventory, translation)
    _write(args.out, content)
    has_gaps = bool(
        plan.blocked_steps
        or plan.dangling_references
        or plan.cycles
        or translation.unmapped_principals
    )
    return EXIT_FINDINGS if has_gaps else EXIT_OK


def _ddl_statements(config: MigrationConfig, inventory: Inventory, plan: Plan) -> List[str]:
    """Render the plan into SQL, in plan order."""
    rewriter = config.rewriter()
    catalogs = {c.name: c for c in inventory.catalogs}
    schemas = {s.full_name: s for s in inventory.schemas}
    volumes = {v.full_name: v for v in inventory.volumes}
    functions = {f.full_name: f for f in inventory.functions}
    tables = inventory.table_index()
    locations = {loc.name: loc for loc in inventory.external_locations}
    assistant = Assistant(rewriter=rewriter, client=NullLlmClient())
    allowed = sorted({rewriter.rewrite_full_name(name) for name in tables})

    statements: List[str] = []
    for step in plan.steps:
        if step.blocked:
            statements.append("-- BLOCKED {0}: {1}".format(step.source_name, step.blocked_reason))
            continue
        if step.tier == TIER_EXTERNAL_LOCATION:
            location = locations.get(step.source_name)
            if location is None:
                continue
            rewritten = rewriter.rewrite_uri(location.url)
            if not rewritten.mapped:
                statements.append(
                    "-- BLOCKED external location {0}: no path rule for {1}".format(
                        location.name, location.url
                    )
                )
                continue
            statements.append(
                create_external_location(
                    location.name, rewritten.value, location.credential_name, location.read_only
                )
            )
        elif step.tier == TIER_CATALOG:
            catalog = catalogs.get(step.source_name)
            if catalog is not None:
                statements.append(
                    create_catalog(
                        catalog,
                        step.target_name,
                        config.managed_locations.get(step.target_name),
                    )
                )
        elif step.tier == TIER_SCHEMA:
            schema = schemas.get(step.source_name)
            if schema is not None:
                statements.append(
                    create_schema(
                        schema,
                        step.target_name,
                        config.managed_locations.get(step.target_name),
                    )
                )
        elif step.tier == TIER_VOLUME:
            volume = volumes.get(step.source_name)
            if volume is not None:
                target_location = None
                if volume.volume_type == "EXTERNAL" and volume.storage_location:
                    rewritten = rewriter.rewrite_uri(volume.storage_location)
                    target_location = rewritten.value if rewritten.mapped else None
                    if target_location is None:
                        statements.append(
                            "-- BLOCKED volume {0}: no path rule for {1}".format(
                                volume.full_name, volume.storage_location
                            )
                        )
                        continue
                statements.append(create_volume(volume, step.target_name, target_location))
        elif step.tier == TIER_TABLE and step.strategy in (DEEP_CLONE, CTAS):
            table = tables.get(step.source_name)
            if table is not None:
                statements.extend(
                    table_ddl_bundle(
                        table,
                        step.target_name,
                        step.strategy,
                        step.detail.get("target_location"),
                    )
                )
        elif step.tier == TIER_VIEW and step.strategy == CREATE_VIEW:
            view = tables.get(step.source_name)
            if view is None or not view.view_definition:
                continue
            translation = assistant.translate_view(
                view.full_name, view.view_definition, allowed, {}
            )
            if not translation.accepted:
                statements.append(
                    "-- BLOCKED view {0}: {1}".format(view.full_name, translation.rejection_reason)
                )
                continue
            statements.append(create_view(step.target_name, translation.sql, view.comment))
        elif step.tier == TIER_CONSTRAINT:
            # Constraints are emitted as part of their table's bundle, which
            # keeps them adjacent to the CREATE they depend on.
            continue
        elif step.tier == TIER_FUNCTION:
            function = functions.get(step.source_name)
            if function is None or not function.routine_definition:
                statements.append(
                    "-- BLOCKED function {0}: no exported definition".format(step.source_name)
                )
                continue
            body = rewriter.rewrite_sql(function.routine_definition).value
            residual = rewriter.find_unmapped(body)
            if residual:
                statements.append(
                    "-- BLOCKED function {0}: unmapped paths {1}".format(
                        function.full_name, ", ".join(residual)
                    )
                )
                continue
            statements.append(create_function(function, step.target_name, body))
    return statements


def cmd_ddl(config: MigrationConfig, args: argparse.Namespace) -> int:
    inventory = _load_inventory(args.inventory)
    plan = _plan_from(config, inventory)
    statements = _ddl_statements(config, inventory, plan)
    header = [
        "-- Generated by dbxmig {0}".format(__version__),
        "-- Review before executing. Statements are idempotent and ordered by dependency.",
        "",
    ]
    _write(args.out, "\n".join(header + statements))
    blocked = [s for s in statements if s.startswith("-- BLOCKED")]
    return EXIT_FINDINGS if blocked else EXIT_OK


def cmd_grants(config: MigrationConfig, args: argparse.Namespace) -> int:
    inventory = _load_inventory(args.inventory)
    principal_map = _principal_map(config)
    translation = translate_grants(
        inventory.grants, principal_map, config.catalog_map, strict=args.strict
    )
    lines = [
        "-- Generated by dbxmig {0}".format(__version__),
        "-- Applied top-down: catalog, then schema, then table/view/volume.",
        "",
    ]
    lines.extend(translation.statements)
    owner_lines, unmapped_owners = _owner_statements(config, inventory, principal_map)
    if owner_lines:
        lines.append("")
        lines.append("-- Ownership. Not a grant: an object's owner is not reproduced by any")
        lines.append("-- GRANT statement, and the migrating admin owns everything by default")
        lines.append("-- until this runs.")
        lines.extend(owner_lines)
    for owner in unmapped_owners:
        lines.append("-- SKIPPED owner {0}: no target mapping".format(owner))
    if translation.skipped:
        lines.append("")
        for grant, reason in translation.skipped:
            lines.append(
                "-- SKIPPED {0} on {1} to {2}: {3}".format(
                    grant.privilege, grant.full_name, grant.principal, reason
                )
            )
    _write(args.out, "\n".join(lines))
    return EXIT_FINDINGS if translation.unmapped_principals else EXIT_OK


def _owner_statements(
    config: MigrationConfig, inventory: Inventory, principal_map: PrincipalMap
) -> "tuple[List[str], List[str]]":
    """Emit ``SET OWNER TO`` for every object that records an owner.

    Ownership is separate from privileges and separately lost: whoever runs the
    migration owns every object they create, which quietly concentrates
    ``MANAGE`` on one account until this is corrected.
    """
    statements: List[str] = []
    unmapped: List[str] = []

    def emit(object_type: str, source_name: str, owner: Optional[str]) -> None:
        if not owner:
            return
        if owner in principal_map.retired:
            return
        target_owner = principal_map.mapping.get(owner)
        if target_owner is None:
            if owner not in unmapped:
                unmapped.append(owner)
            return
        parts = source_name.split(".")
        parts[0] = config.catalog_map.get(parts[0], parts[0])
        statements.append(set_owner(object_type, ".".join(parts), target_owner))

    for catalog in inventory.catalogs:
        emit("CATALOG", catalog.name, catalog.owner)
    for schema in inventory.schemas:
        emit("SCHEMA", schema.full_name, schema.owner)
    for table in inventory.tables:
        if table.table_type in ("MATERIALIZED_VIEW", "STREAMING_TABLE"):
            # These do not exist until their pipeline has been recreated and has
            # refreshed, so an owner statement here would fail at cutover.
            continue
        emit("VIEW" if table.is_view else "TABLE", table.full_name, table.owner)
    for volume in inventory.volumes:
        emit("VOLUME", volume.full_name, volume.owner)
    for function in inventory.functions:
        emit("FUNCTION", function.full_name, function.owner)
    return statements, sorted(unmapped)


def _load_workspace(path: str) -> WorkspaceInventory:
    with open(path, "r", encoding="utf-8") as handle:
        return WorkspaceInventory.from_dict(json.load(handle))


def cmd_workspace(config: MigrationConfig, args: argparse.Namespace) -> int:
    """Collect the workspace plane: everything that is not in the metastore."""
    if args.fixture:
        inventory = _load_workspace(args.fixture)
    else:
        gateway = _gateway(config, args)
        if not isinstance(gateway, DatabricksGateway):
            raise ConfigError("workspace collection needs a live workspace or --fixture")
        inventory = collect_workspace_inventory(
            gateway.client, include_acls=not args.no_acls, include_query_text=not args.no_query_text
        )
    _write(args.out, json.dumps(inventory.to_dict(), indent=2, sort_keys=True))

    if args.csv_dir:
        os.makedirs(args.csv_dir, exist_ok=True)
        written = 0
        for asset_class in ASSET_CLASSES:
            rows = csv_rows(inventory, asset_class)
            if not rows:
                continue
            path = os.path.join(args.csv_dir, asset_class + ".csv")
            with open(path, "w", encoding="utf-8", newline="") as handle:
                csv.writer(handle).writerows(rows)
            written += 1
        print("wrote {0} CSV file(s) to {1}".format(written, args.csv_dir), file=sys.stderr)

    print(workspace_summary(inventory), file=sys.stderr)
    gaps = coverage_gaps(inventory)
    for gap in gaps:
        print("coverage: " + gap, file=sys.stderr)
    return EXIT_FINDINGS if inventory.failed_classes() else EXIT_OK


def cmd_crossrefs(config: MigrationConfig, args: argparse.Namespace) -> int:
    """Report what each workspace asset depends on, and what will break."""
    inventory = _load_workspace(args.workspace)
    report = scan(inventory, config.rewriter())
    if args.source:
        # Asset metadata cannot see a path hardcoded on line 88 of a notebook.
        # Scanning the exported source closes that half, with a line number.
        scopes = {str(r.get("scope", "")) for r in inventory.rows("secret_scopes")}
        report = merge(report, scan_source_tree(args.source, config.rewriter(), scopes))
    if args.csv:
        with open(args.csv, "w", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerows(to_rows(report))
        print("wrote {0}".format(args.csv), file=sys.stderr)
    _write(args.out, crossref_summary(inventory, report))
    return EXIT_FINDINGS if report.blockers else EXIT_OK


def cmd_apply(config: MigrationConfig, args: argparse.Namespace) -> int:
    inventory = _load_inventory(args.inventory)
    plan = _plan_from(config, inventory)
    statements = _ddl_statements(config, inventory, plan)
    journal = Journal(path=args.state or config.state_file)
    # A dry run needs no workspace at all -- it must work before target
    # credentials exist, which is when the SQL actually gets reviewed.
    gateway = _gateway(config, args, side="target") if args.execute else None

    executed = 0
    skipped = 0
    failed = 0
    for index, statement in enumerate(statements):
        step_id = "sql:{0:05d}".format(index)
        if statement.startswith("-- BLOCKED"):
            journal.record(step_id, STATUS_BLOCKED, detail=statement)
            continue
        if journal.is_done(step_id):
            skipped += 1
            continue
        if not args.execute or gateway is None:
            print(statement)
            executed += 1
            continue
        try:
            gateway.execute(statement)
        except Exception as exc:  # noqa: BLE001 - the failure must be journalled, then surfaced
            journal.record(step_id, STATUS_FAILED, statement=statement, error=str(exc))
            failed += 1
            print("FAILED {0}: {1}".format(step_id, exc), file=sys.stderr)
            if not args.continue_on_error:
                break
            continue
        journal.record(step_id, STATUS_DONE, statement=statement)
        executed += 1

    mode = "executed" if args.execute else "would execute"
    print(
        "{0} {1} statement(s); {2} already done; {3} failed".format(
            mode, executed, skipped, failed
        ),
        file=sys.stderr,
    )
    return EXIT_FINDINGS if failed else EXIT_OK


def cmd_reconcile(config: MigrationConfig, args: argparse.Namespace) -> int:
    source = _load_inventory(args.inventory)
    target = _load_inventory(args.target_inventory)
    report = reconcile_inventories(source, target, config.source_prefixes())
    _write(args.out, reconciliation_summary(report))
    return report.exit_code()


def cmd_report(config: MigrationConfig, args: argparse.Namespace) -> int:
    inventory = _load_inventory(args.inventory)
    plan = _plan_from(config, inventory)
    principal_map = _principal_map(config)
    translation = translate_grants(
        inventory.grants, principal_map, config.catalog_map, strict=False
    )
    reconciliation = None
    if args.target_inventory:
        target = _load_inventory(args.target_inventory)
        reconciliation = reconcile_inventories(inventory, target, config.source_prefixes())
    content = full_report(inventory, plan, config.rewriter(), translation, reconciliation)
    _write(args.out, content)
    return EXIT_OK


def cmd_validate(config: MigrationConfig, args: argparse.Namespace) -> int:
    problems = config.problems()
    if problems:
        for problem in problems:
            print("config problem: " + problem, file=sys.stderr)
        return EXIT_FINDINGS
    print("configuration is valid")
    return EXIT_OK


# ---- argument parsing ---------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dbxmig",
        description="Unity Catalog metastore migration toolkit for cross-cloud moves.",
    )
    parser.add_argument("--version", action="version", version="dbxmig " + __version__)
    parser.add_argument("-c", "--config", required=True, help="migration config (YAML or JSON)")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(sp: argparse.ArgumentParser, needs_inventory: bool = True) -> None:
        if needs_inventory:
            sp.add_argument(
                "-i", "--inventory", default="inventory.json", help="source inventory JSON"
            )
        sp.add_argument("-o", "--out", help="write output to this file instead of stdout")

    p = sub.add_parser("validate", help="check the config file and exit")
    p.set_defaults(func=cmd_validate)
    p.add_argument("-o", "--out", help=argparse.SUPPRESS)

    p = sub.add_parser("inventory", help="export the source metastore to JSON")
    add_common(p, needs_inventory=False)
    p.add_argument("--fixture", help="read from a JSON fixture instead of a live workspace")
    p.set_defaults(func=cmd_inventory)

    p = sub.add_parser(
        "workspace", help="collect the workspace plane: jobs, clusters, dashboards, ACLs, ..."
    )
    p.add_argument("-o", "--out", help="write the JSON manifest here instead of stdout")
    p.add_argument("--fixture", help="read from a JSON fixture instead of a live workspace")
    p.add_argument("--csv-dir", help="also write one CSV per asset class into this directory")
    p.add_argument("--no-acls", action="store_true", help="skip workspace object ACLs (faster)")
    p.add_argument("--no-query-text", action="store_true", help="omit SQL bodies from the manifest")
    p.set_defaults(func=cmd_workspace)

    p = sub.add_parser(
        "crossrefs", help="what each workspace asset depends on, and what will break"
    )
    p.add_argument("-w", "--workspace", default="workspace.json", help="workspace inventory JSON")
    p.add_argument(
        "-s",
        "--source",
        help="also scan this directory of exported notebooks / repo source, with line numbers",
    )
    p.add_argument("-o", "--out", help="write the report here instead of stdout")
    p.add_argument("--csv", help="also write the findings as CSV")
    p.set_defaults(func=cmd_crossrefs)

    p = sub.add_parser("plan", help="order the inventory into executable steps")
    add_common(p)
    p.add_argument("--json", action="store_true", help="emit the plan as JSON")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("gaps", help="report what will not migrate without a decision")
    add_common(p)
    p.set_defaults(func=cmd_gaps)

    p = sub.add_parser("ddl", help="emit target DDL in dependency order")
    add_common(p)
    p.set_defaults(func=cmd_ddl)

    p = sub.add_parser("grants", help="emit translated GRANT statements")
    add_common(p)
    p.add_argument(
        "--strict",
        action="store_true",
        help="fail instead of skipping when a principal has no mapping",
    )
    p.set_defaults(func=cmd_grants)

    p = sub.add_parser("apply", help="execute the plan (dry-run unless --execute)")
    add_common(p)
    p.add_argument("--execute", action="store_true", help="actually run the statements")
    p.add_argument("--state", help="journal file (defaults to config state_file)")
    p.add_argument("--fixture", help="run against a fixture gateway")
    p.add_argument(
        "--continue-on-error",
        action="store_true",
        help="keep going after a failed statement instead of stopping",
    )
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("reconcile", help="compare a target inventory against the source")
    add_common(p)
    p.add_argument("-t", "--target-inventory", required=True, help="target inventory JSON")
    p.set_defaults(func=cmd_reconcile)

    p = sub.add_parser("report", help="one markdown report covering inventory, plan, and gaps")
    add_common(p)
    p.add_argument("-t", "--target-inventory", help="include reconciliation against this target")
    p.set_defaults(func=cmd_report)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    except OSError as exc:
        print("cannot read config: {0}".format(exc), file=sys.stderr)
        return EXIT_USAGE
    try:
        return int(args.func(config, args))
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    except FileNotFoundError as exc:
        print("missing file: {0}".format(exc), file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
