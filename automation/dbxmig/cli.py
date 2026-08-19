"""Command-line entry point.

The commands map onto the phases of a metastore migration and are meant to be
run in order:

    dbxmig inventory   # capture the source metastore
    dbxmig plan        # order it into executable steps
    dbxmig gaps        # what will not migrate on its own -- read this one
    dbxmig ddl         # emit the target SQL for review
    dbxmig grants      # emit the translated GRANT statements
    dbxmig apply       # execute, resumably (--execute to leave dry-run)
    dbxmig cutover-drain  # cutover night: poll source until zero active runs
    dbxmig reconcile   # prove the target matches the source (add --live for data checksums)

``apply`` is dry-run by default and prints the statements it would issue.
Executing for real takes an explicit ``--execute``, because a metastore
migration is not something to start by accident.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from typing import List, Optional, Sequence

from . import __version__
from .acls import build_acl_plan, entries_from_inventory, replay_script
from .acls import diff as acl_diff
from .acls import summary as acl_summary
from .acls import to_rows as acl_rows
from .bundle import generate_bundle
from .cloud.aws import AwsAssetAdapter
from .cloud.azure import AzureAssetAdapter
from .cloud.gcp import GcpAssetAdapter
from .cloud.merge import merge_with_workspace_inventory
from .collisions import detect as detect_collisions
from .collisions import render as render_collisions
from .config import ConfigError, MigrationConfig, load_config, load_principal_map
from .crossrefs import coverage_gaps, from_dicts, merge, scan, scan_source_tree, to_dicts, to_rows
from .cutover import check_drain
from .ddl import (
    add_constraint,
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
from .grants import (
    PrincipalMap,
    diff_grants,
    expected_grants_after_translation,
    translate_grants,
)
from .llm import Assistant, NullLlmClient
from .models import Inventory
from .ownership import load_ownership
from .ownership import unowned as unowned_labels
from .reconcile import reconcile_inventories, reconcile_live
from .report import (
    crossref_summary,
    full_report,
    gap_report,
    plan_summary,
    reconciliation_summary,
    verify_summary,
    wave_plan_summary,
    workspace_summary,
)
from .state import STATUS_BLOCKED, STATUS_DONE, STATUS_FAILED, Journal
from .streaming import StreamingAsset, StreamingReport
from .streaming import discover as discover_streaming
from .waveplan import DEFAULT_THRESHOLDS, build_wave_plan
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


def _step_id_for_statement(statement: str) -> str:
    """Content-addressed journal step id for one rendered DDL statement.

    A positional index (``"sql:{index}"``) shifts every time the plan's
    statement count changes upstream -- an added/removed table, a config
    change that alters how many statements a table's DDL bundle emits -- and
    the journal has no way to tell that the id it recorded "done" now means
    a completely different statement. Hashing the statement text instead
    means the id only ever matches the exact SQL that was journalled: if the
    statement changes for any reason, resume treats it as new work rather
    than silently skipping it.
    """
    return "sql:" + hashlib.sha1(statement.encode("utf-8")).hexdigest()[:12]


def _load_streaming(path: str) -> StreamingReport:
    with open(path, "r", encoding="utf-8") as handle:
        return StreamingReport(assets=[StreamingAsset.from_dict(a) for a in json.load(handle)])


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
    inventory = gateway.fetch_inventory(config.source.catalogs or None, config.lineage_days)
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
                "{0:<6} {1:<16} {2:<40} {3}".format(step.tier, marker, step.source_name, step.id)
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
    streaming_report = _load_streaming(args.streaming) if args.streaming else None
    content = gap_report(plan, config.rewriter(), inventory, translation, streaming_report)

    # The target metastore is shared by every workspace in its region, so the
    # names this plan intends to create may already belong to someone else.
    # Optional because a greenfield region has nothing to compare against, but
    # skipping it is a choice the report records rather than a silent default.
    collisions = None
    if args.target_inventory:
        collisions = detect_collisions(
            inventory,
            _load_inventory(args.target_inventory),
            config.rewriter(),
            config.catalog_map,
        )
        content = content.rstrip("\n") + "\n\n" + render_collisions(collisions)
    else:
        content = content.rstrip("\n") + (
            "\n\n## Target collisions\n\n"
            "Not checked -- no `--target-inventory` was supplied. Every `CREATE` this "
            "toolkit emits is `IF NOT EXISTS`, so a name already taken in the target "
            "metastore produces no error: a colliding catalog is silently migrated "
            "*into*, and a colliding table is silently not migrated at all. Run "
            "`dbxmig inventory` against the target and pass it here before generating "
            "DDL.\n"
        )

    _write(args.out, content)
    has_gaps = bool(
        plan.blocked_steps
        or plan.dangling_references
        or plan.cycles
        or translation.unmapped_principals
        or (collisions is not None and collisions.fatal)
        or (streaming_report is not None and streaming_report.unassigned)
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
            # Table-local constraints ride along in their table's bundle, which
            # keeps them adjacent to the CREATE they depend on. A FOREIGN KEY
            # cannot: it names a parent table that the bundle cannot assume
            # exists yet, and UC requires that parent's PRIMARY KEY to already
            # be defined. Tier 65 runs after every table, the earliest safe point.
            if str(step.detail.get("kind", "")).upper() != "FOREIGN_KEY":
                continue
            table_name, _, constraint_name = step.source_name.rpartition(".")
            table = tables.get(table_name)
            if table is None:
                continue
            constraint = next((c for c in table.constraints if c.name == constraint_name), None)
            if constraint is None:
                continue
            statements.append(
                add_constraint(
                    rewriter.rewrite_full_name(table.full_name),
                    constraint.name,
                    constraint.kind,
                    constraint.definition,
                    rewriter.rewrite_full_name,
                )
            )
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
            gateway.client,
            include_acls=not args.no_acls,
            include_query_text=not args.no_query_text,
            include_raw=args.raw,
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
    target_cloud = config.target.cloud or None
    report = scan(inventory, config.rewriter(), target_cloud=target_cloud)
    if args.source:
        # Asset metadata cannot see a path hardcoded on line 88 of a notebook.
        # Scanning the exported source closes that half, with a line number.
        scopes = {str(r.get("scope", "")) for r in inventory.rows("secret_scopes")}
        report = merge(
            report,
            scan_source_tree(args.source, config.rewriter(), scopes, target_cloud=target_cloud),
        )
    if args.csv:
        with open(args.csv, "w", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerows(to_rows(report))
        print("wrote {0}".format(args.csv), file=sys.stderr)
    if args.json:
        _write(args.json, json.dumps(to_dicts(report), indent=2, sort_keys=True))
        print("wrote {0}".format(args.json), file=sys.stderr)
    _write(args.out, crossref_summary(inventory, report))
    return EXIT_FINDINGS if report.blockers else EXIT_OK


_CLOUD_ADAPTERS = {
    "azure": AzureAssetAdapter,
    "aws": AwsAssetAdapter,
    "gcp": GcpAssetAdapter,
}


def cmd_cloud_inventory(config: MigrationConfig, args: argparse.Namespace) -> int:
    """Discover cloud-native resources (Key Vaults, S3 buckets, VPCs, ...) outside Unity Catalog."""
    with open(args.scope, "r", encoding="utf-8") as handle:
        scope = json.load(handle)
    adapter = _CLOUD_ADAPTERS[args.provider]()
    assets = adapter.discover(scope)
    if args.merge_with_crossrefs:
        with open(args.merge_with_crossrefs, "r", encoding="utf-8") as handle:
            crossref_report = from_dicts(json.load(handle))
        graph = merge_with_workspace_inventory(assets, crossref_report.findings)
        _write(args.out, json.dumps(graph.to_dict(), indent=2, sort_keys=True))
        print(
            "discovered {0} {1} asset(s); merged graph has {2} node(s), {3} edge(s)".format(
                len(assets), args.provider, len(graph.nodes), len(graph.edges)
            ),
            file=sys.stderr,
        )
        return EXIT_OK
    _write(args.out, json.dumps([a.to_dict() for a in assets], indent=2, sort_keys=True))
    print("discovered {0} {1} asset(s)".format(len(assets), args.provider), file=sys.stderr)
    return EXIT_OK


def cmd_wave_plan(config: MigrationConfig, args: argparse.Namespace) -> int:
    """Cluster assets that share a reference and assign them to waves.

    [Wave planning](/execution/wave-planning) calls the shared-references
    table "the wave-planning signal"; this is the step that was always left
    manual -- turning it into actual clusters, scoring them, and assigning
    waves. Clustering and dependency-count scoring are deterministic; the
    other four scoring factors are a judgment call this toolkit cannot
    observe, so they come from ``--scores`` or default to 1 (earliest wave)
    rather than being invented.
    """
    with open(args.crossrefs, "r", encoding="utf-8") as handle:
        report = from_dicts(json.load(handle))
    manual_scores: dict = {}
    if args.scores:
        with open(args.scores, "r", encoding="utf-8") as handle:
            manual_scores = json.load(handle)
    ownership = load_ownership(args.ownership_file) if args.ownership_file else {}
    all_labels = report.all_asset_labels()
    shared = report.shared_references(minimum=args.minimum_holders)
    plan = build_wave_plan(
        shared,
        manual_scores=manual_scores,
        all_assets=all_labels,
        thresholds=DEFAULT_THRESHOLDS,
        ownership=ownership,
    )
    unowned_assets = unowned_labels(all_labels, ownership) if ownership else []
    _write(args.out, wave_plan_summary(plan, unowned_assets))
    return EXIT_FINDINGS if unowned_assets else EXIT_OK


def cmd_streaming(config: MigrationConfig, args: argparse.Namespace) -> int:
    """Discover streaming/DLT assets and flag the ones with no migration strategy."""
    inventory = _load_workspace(args.workspace)
    report = discover_streaming(inventory, source_root=args.source)
    _write(args.out, json.dumps(report.to_dicts(), indent=2, sort_keys=True))
    print(
        "discovered {0} streaming asset(s), {1} unassigned".format(
            len(report.assets), len(report.unassigned)
        ),
        file=sys.stderr,
    )
    for asset in report.unassigned:
        print(
            "needs a migration_strategy: {0} ({1})".format(asset.name, asset.kind),
            file=sys.stderr,
        )
    return EXIT_FINDINGS if report.unassigned else EXIT_OK


def cmd_bundle(config: MigrationConfig, args: argparse.Namespace) -> int:
    """Emit Declarative Automation Bundle YAML from the workspace inventory."""
    inventory = _load_workspace(args.workspace)
    streaming_report = _load_streaming(args.streaming) if args.streaming else None
    result = generate_bundle(
        inventory,
        bundle_name=args.name,
        target_name=args.target_name,
        target_host=config.target.host,
        rewriter=config.rewriter(),
        pause_schedules=not args.no_pause,
        streaming_report=streaming_report,
    )
    out_dir = args.out or "bundle"
    for relative, content in sorted(result.files.items()):
        path = os.path.join(out_dir, relative)
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
    counts = ", ".join("{0}={1}".format(k, v) for k, v in sorted(result.resource_counts.items()))
    print(
        "wrote {0} file(s) to {1} ({2}); {3} variable(s); {4} item(s) need review".format(
            len(result.files), out_dir, counts, len(result.variables), len(result.review)
        ),
        file=sys.stderr,
    )
    for _, reason in result.review:
        print("review: " + reason, file=sys.stderr)
    return EXIT_FINDINGS if result.needs_review() else EXIT_OK


def cmd_acls(config: MigrationConfig, args: argparse.Namespace) -> int:
    """Replay workspace object ACLs -- the permission system UC grants do not cover."""
    inventory = _load_workspace(args.workspace)
    plan = build_acl_plan(inventory, _principal_map(config), strict=args.strict)
    if args.script:
        _write(args.script, replay_script(plan))
        print("wrote replay script to {0}".format(args.script), file=sys.stderr)
    if args.csv:
        with open(args.csv, "w", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerows(acl_rows(plan))
        print("wrote {0}".format(args.csv), file=sys.stderr)
    _write(args.out, acl_summary(plan))
    return EXIT_OK if plan.ok else EXIT_FINDINGS


def cmd_verify(config: MigrationConfig, args: argparse.Namespace) -> int:
    """Prove the target holds what the migration intended.

    Every other command describes what will happen. This one reads the target
    after the fact. It closes the loop the runbook keeps asking for -- "diff
    target grants against the source export" -- which until now had no command
    behind it.
    """
    principal_map = _principal_map(config)
    grant_diff = None
    acl_missing = None
    acl_extra = None

    if args.inventory and args.target_inventory:
        source = _load_inventory(args.inventory)
        target = _load_inventory(args.target_inventory)
        expected = expected_grants_after_translation(
            source.grants, principal_map, config.catalog_map
        )
        grant_diff = diff_grants(expected, target.grants)

    if args.workspace and args.target_workspace:
        source_ws = _load_workspace(args.workspace)
        target_ws = _load_workspace(args.target_workspace)
        # Expected ACLs are the source set translated and filtered the same way
        # `dbxmig acls` would replay them -- comparing raw source entries would
        # flag IS_OWNER and retired principals as missing every time.
        plan = build_acl_plan(source_ws, principal_map, strict=False)
        result = acl_diff(plan.entries, entries_from_inventory(target_ws))
        acl_missing = result["missing_in_target"]
        acl_extra = result["extra_in_target"]

    if grant_diff is None and acl_missing is None:
        raise ConfigError(
            "nothing to verify: pass -i/-t for grants, -w/--target-workspace for ACLs, or both"
        )

    _write(args.out, verify_summary(grant_diff, acl_missing, acl_extra))
    drift = 0
    if grant_diff is not None:
        drift += len(grant_diff.missing_in_target) + len(grant_diff.extra_in_target)
    drift += len(acl_missing or []) + len(acl_extra or [])
    return EXIT_FINDINGS if drift else EXIT_OK


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
    for statement in statements:
        step_id = _step_id_for_statement(statement)
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
    if args.live:
        # Only checksum tables that already cleared metadata reconciliation --
        # a missing table or schema drift should block before we ever touch a
        # warehouse for that table.
        already_blocked = {f.obj for f in report.blockers}
        target_index = target.table_index()
        wanted = set(args.tables) if args.tables else None
        live_tables = [
            t
            for t in source.tables
            if t.full_name in target_index
            and t.full_name not in already_blocked
            and (wanted is None or t.full_name in wanted)
        ]
        source_gateway = _gateway(config, args, side="source")
        target_gateway = _gateway(config, args, side="target")
        live_report = reconcile_live(
            source_gateway, target_gateway, live_tables, config.row_count_tolerance
        )
        report.checked += live_report.checked
        report.findings.extend(live_report.findings)
    _write(args.out, reconciliation_summary(report))
    return report.exit_code()


def cmd_cutover_drain(config: MigrationConfig, args: argparse.Namespace) -> int:
    """Poll the drain gate [cutover](/execution/cutover) step 3 describes, until it clears.

    Read-only: this answers "is it safe to proceed to final sync", it does
    not pause anything itself. A timeout is a no-go, not a "close enough" --
    it exits non-zero either way so it composes cleanly into a go/no-go
    script.
    """
    if getattr(args, "fixture", None):
        raise ConfigError(
            "cutover-drain needs a live workspace -- fixtures do not model job runs"
        )
    gateway = _gateway(config, args, side=args.side)
    if not isinstance(gateway, DatabricksGateway):
        raise ConfigError("cutover-drain needs a live workspace ({0}.host)".format(args.side))
    client = gateway.client

    deadline = time.monotonic() + args.timeout
    while True:
        status = check_drain(client)
        print(status.summary(), file=sys.stderr)
        if status.drained:
            return EXIT_OK
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            print(
                "DRAIN TIMEOUT after {0}s -- treat as no-go, not close enough".format(
                    args.timeout
                ),
                file=sys.stderr,
            )
            return EXIT_FINDINGS
        time.sleep(max(0, min(args.poll_interval, remaining)))


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
    streaming_report = _load_streaming(args.streaming) if args.streaming else None
    content = full_report(
        inventory, plan, config.rewriter(), translation, reconciliation, streaming_report
    )
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
    p.add_argument(
        "--raw",
        action="store_true",
        help="keep full job/pipeline definitions -- required for `dbxmig bundle`",
    )
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
    p.add_argument(
        "--json", help="also write the full report as JSON, for `dbxmig wave-plan --crossrefs`"
    )
    p.set_defaults(func=cmd_crossrefs)

    p = sub.add_parser(
        "cloud-inventory",
        help="discover cloud-native resources (Key Vaults, S3 buckets, VPCs, ...) outside UC",
    )
    p.add_argument(
        "--provider", required=True, choices=sorted(_CLOUD_ADAPTERS), help="cloud to query"
    )
    p.add_argument(
        "--scope",
        required=True,
        help="JSON file naming what to query -- e.g. {\"subscriptions\": [...]} for azure, "
        "{\"project\": \"...\"} for gcp, {\"resource_types\": [...]} for aws",
    )
    p.add_argument(
        "--merge-with-crossrefs",
        help="`dbxmig crossrefs --json` output -- write the merged AssetGraph instead of "
        "the plain asset list",
    )
    p.add_argument("-o", "--out", help="write the discovered assets here instead of stdout")
    p.set_defaults(func=cmd_cloud_inventory)

    p = sub.add_parser(
        "wave-plan",
        help="cluster assets sharing a reference and assign them to waves",
    )
    p.add_argument(
        "--crossrefs", required=True, help="`dbxmig crossrefs --json` output"
    )
    p.add_argument(
        "--scores",
        help=(
            "JSON: {cluster_id: {criticality, risk_tolerance, data_size, owner_readiness, "
            "dependency_count}}, each 1-5 -- cluster_id is the cluster's alphabetically-lowest "
            "asset label. Unscored clusters default to 1 (earliest wave) on every factor."
        ),
    )
    p.add_argument(
        "--minimum-holders",
        type=int,
        default=2,
        help="minimum assets sharing a reference before they're clustered together (default: 2)",
    )
    p.add_argument(
        "--ownership-file",
        help="CSV or YAML: asset_label -> {business_owner, criticality_tier, domain, ...} "
        "(see ownership.py). Unowned assets are flagged, never defaulted quietly.",
    )
    p.add_argument("-o", "--out", help="write the plan here instead of stdout")
    p.set_defaults(func=cmd_wave_plan)

    p = sub.add_parser(
        "streaming", help="discover Structured Streaming / DLT assets and their migration strategy"
    )
    p.add_argument("-w", "--workspace", default="workspace.json", help="workspace inventory JSON")
    p.add_argument(
        "-s", "--source", help="also scan this directory of exported notebooks / repo source"
    )
    p.add_argument("-o", "--out", help="write the discovered assets here instead of stdout")
    p.set_defaults(func=cmd_streaming)

    p = sub.add_parser(
        "bundle", help="generate Declarative Automation Bundle YAML from the workspace inventory"
    )
    p.add_argument("-w", "--workspace", default="workspace.json", help="workspace inventory JSON")
    p.add_argument("-o", "--out", default="bundle", help="directory to write the bundle into")
    p.add_argument("--name", default="migrated-estate", help="bundle name")
    p.add_argument("--target-name", default="target", help="bundle target name")
    p.add_argument(
        "--no-pause",
        action="store_true",
        help="keep original schedules instead of emitting every job PAUSED",
    )
    p.add_argument("--streaming", help="`dbxmig streaming --json` output, to include in REVIEW.md")
    p.set_defaults(func=cmd_bundle)

    p = sub.add_parser(
        "acls", help="replay workspace object ACLs (jobs, clusters, pools, warehouses)"
    )
    p.add_argument("-w", "--workspace", default="workspace.json", help="workspace inventory JSON")
    p.add_argument("-o", "--out", help="write the report here instead of stdout")
    p.add_argument("--script", help="also write a runnable Python replay script here")
    p.add_argument("--csv", help="also write the entries as CSV")
    p.add_argument(
        "--strict",
        action="store_true",
        help="fail instead of skipping when a principal has no mapping",
    )
    p.set_defaults(func=cmd_acls)

    p = sub.add_parser("plan", help="order the inventory into executable steps")
    add_common(p)
    p.add_argument("--json", action="store_true", help="emit the plan as JSON")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("gaps", help="report what will not migrate without a decision")
    add_common(p)
    p.add_argument(
        "--target-inventory",
        help=(
            "inventory of the TARGET metastore, to detect names already taken there. "
            "A metastore is shared per region, so another team's catalog can absorb "
            "this migration without raising an error"
        ),
    )
    p.add_argument(
        "--streaming", help="`dbxmig streaming --json` output, to flag unassigned strategies"
    )
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

    p = sub.add_parser(
        "verify", help="prove the target holds the grants and ACLs the migration intended"
    )
    p.add_argument("-i", "--inventory", help="source metastore inventory JSON")
    p.add_argument("-t", "--target-inventory", help="target metastore inventory JSON")
    p.add_argument("-w", "--workspace", help="source workspace inventory JSON")
    p.add_argument("--target-workspace", help="target workspace inventory JSON")
    p.add_argument("-o", "--out", help="write the report here instead of stdout")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("reconcile", help="compare a target inventory against the source")
    add_common(p)
    p.add_argument("-t", "--target-inventory", required=True, help="target inventory JSON")
    p.add_argument(
        "--live",
        action="store_true",
        help=(
            "also run row-count + aggregate-hash checksum reconciliation against live "
            "source and target warehouses (needs source.host/target.host or --fixture)"
        ),
    )
    p.add_argument(
        "--tables",
        nargs="*",
        help="restrict --live checksum reconciliation to these full table names",
    )
    p.add_argument(
        "--fixture",
        help=(
            "run --live against a fixture gateway instead of live workspaces -- the same "
            "fixture is used for both source and target, so this proves the wiring, not "
            "an actual cross-environment result"
        ),
    )
    p.set_defaults(func=cmd_reconcile)

    p = sub.add_parser(
        "cutover-drain",
        help="poll the Jobs API until zero active runs, or a hard timeout -- read-only",
    )
    p.add_argument(
        "--side",
        choices=["source", "target"],
        default="source",
        help="which workspace to poll (cutover step 3 checks source before final sync)",
    )
    p.add_argument(
        "--timeout", type=int, default=900, help="seconds before giving up (default: 900 = 15m)"
    )
    p.add_argument("--poll-interval", type=int, default=15, help="seconds between polls")
    p.add_argument("--fixture", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_cutover_drain)

    p = sub.add_parser("report", help="one markdown report covering inventory, plan, and gaps")
    add_common(p)
    p.add_argument("-t", "--target-inventory", help="include reconciliation against this target")
    p.add_argument(
        "--streaming", help="`dbxmig streaming --json` output, to flag unassigned strategies"
    )
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
