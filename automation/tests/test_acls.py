from __future__ import annotations

import json
import os

import pytest

from dbxmig.acls import (
    AclEntry,
    build_acl_plan,
    diff,
    entries_from_inventory,
    replay_script,
    summary,
    to_rows,
)
from dbxmig.grants import PrincipalMap, UnmappedPrincipalError
from dbxmig.workspace import WorkspaceInventory

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "workspace.json")

MAP = PrincipalMap(
    mapping={
        "sales-eng": "sales-engineering",
        "data-readers": "data-readers",
        "sam@northwind.example": "sam@northwind.example",
    },
    retired={"departed-contractor"},
)


@pytest.fixture()
def workspace() -> WorkspaceInventory:
    with open(FIXTURE, encoding="utf-8") as handle:
        return WorkspaceInventory.from_dict(json.load(handle))


def reasons(plan):
    return " | ".join(r for _, r in plan.skipped)


def test_principals_are_translated_to_target_names(workspace):
    plan = build_acl_plan(workspace, MAP, strict=False)
    by_object = {(e.object_type, e.object_name): e.principal for e in plan.entries}
    assert by_object[("jobs", "sales-daily-load")] == "sales-engineering"


def test_ownership_is_not_replayed_as_an_acl_entry(workspace):
    plan = build_acl_plan(workspace, MAP, strict=False)
    assert not [e for e in plan.entries if e.permission_level == "IS_OWNER"]
    assert "set by ownership" in reasons(plan)


def test_retired_principal_is_skipped_with_a_reason(workspace):
    plan = build_acl_plan(workspace, MAP, strict=False)
    assert "principal retired: departed-contractor" in reasons(plan)
    assert not [e for e in plan.entries if "contractor" in e.principal]


def test_a_name_shared_by_two_objects_is_ambiguous_not_guessed(workspace):
    plan = build_acl_plan(workspace, MAP, strict=False)
    assert ("sql/warehouses", "shared-bi") in plan.ambiguous
    # And nothing for that name reaches the executable plan.
    assert not [e for e in plan.entries if e.object_name == "shared-bi"]
    assert not plan.ok


def test_unmapped_principal_is_fatal_in_strict_mode(workspace):
    with pytest.raises(UnmappedPrincipalError):
        build_acl_plan(workspace, PrincipalMap(mapping={}), strict=True)


def test_non_strict_collects_every_unmapped_principal(workspace):
    plan = build_acl_plan(workspace, PrincipalMap(mapping={}), strict=False)
    assert "sales-eng" in plan.unmapped_principals
    assert plan.entries == []
    assert not plan.ok


def test_grants_to_an_individual_are_surfaced_as_decisions():
    inventory = WorkspaceInventory(
        assets={
            "object_acls": [
                {
                    "object_type": "jobs",
                    "object_id": "1",
                    "object_name": "nightly",
                    "principal": "priya@example.com",
                    "permission_level": "CAN_MANAGE",
                },
                {
                    "object_type": "jobs",
                    "object_id": "1",
                    "object_name": "nightly",
                    "principal": "eng",
                    "permission_level": "CAN_VIEW",
                },
            ]
        }
    )
    plan = build_acl_plan(
        inventory,
        PrincipalMap(mapping={"priya@example.com": "priya@example.com", "eng": "eng"}),
    )
    assert [e.principal for e in plan.individual_grants] == ["priya@example.com"]
    # It still replays -- it is a decision to review, not an error.
    assert len(plan.entries) == 2


def test_unsupported_object_type_is_skipped_not_dropped():
    inventory = WorkspaceInventory(
        assets={
            "object_acls": [
                {
                    "object_type": "registered-models",
                    "object_id": "1",
                    "object_name": "m",
                    "principal": "eng",
                    "permission_level": "CAN_MANAGE",
                }
            ]
        }
    )
    plan = build_acl_plan(inventory, PrincipalMap(mapping={"eng": "eng"}))
    assert plan.entries == []
    assert "unsupported object type" in reasons(plan)


def test_an_object_with_no_name_cannot_be_resolved():
    inventory = WorkspaceInventory(
        assets={
            "object_acls": [
                {
                    "object_type": "jobs",
                    "object_id": "9",
                    "object_name": "",
                    "principal": "eng",
                    "permission_level": "CAN_VIEW",
                }
            ]
        }
    )
    plan = build_acl_plan(inventory, PrincipalMap(mapping={"eng": "eng"}))
    assert "no name to resolve by" in reasons(plan)


def test_replay_script_resolves_by_name_and_never_hardcodes_a_source_id(workspace):
    script = replay_script(build_acl_plan(workspace, MAP, strict=False))
    assert "def resolve(" in script
    assert "w.permissions.update(" in script
    # Source object ids must not leak into the target script.
    assert "8801" not in script
    assert "0811-shared-01" not in script


def test_replay_script_groups_grants_per_object(workspace):
    script = replay_script(build_acl_plan(workspace, MAP, strict=False))
    assert "by_object.setdefault" in script
    # update() is additive; the script says so rather than implying a replace.
    assert "additive" in script


def test_plan_is_deterministic(workspace):
    first = [e.key() for e in build_acl_plan(workspace, MAP, strict=False).entries]
    second = [e.key() for e in build_acl_plan(workspace, MAP, strict=False).entries]
    assert first == second


def test_csv_has_a_header_and_one_row_per_entry(workspace):
    plan = build_acl_plan(workspace, MAP, strict=False)
    rows = to_rows(plan)
    assert rows[0] == ["object_type", "object_name", "principal", "permission_level"]
    assert len(rows) == len(plan.entries) + 1


def test_summary_reports_every_category(workspace):
    text = summary(build_acl_plan(workspace, MAP, strict=False))
    for heading in ("Workspace object ACLs", "individual", "Ambiguous", "Skipped"):
        assert heading in text


def test_diff_finds_missing_and_extra_entries():
    expected = [AclEntry("jobs", "n", "eng", "CAN_MANAGE")]
    actual = [AclEntry("jobs", "n", "other", "CAN_MANAGE")]
    result = diff(expected, actual)
    assert result["missing_in_target"][0].principal == "eng"
    assert result["extra_in_target"][0].principal == "other"


def test_entries_from_inventory_round_trips_for_diffing(workspace):
    entries = entries_from_inventory(workspace)
    # IS_OWNER is excluded -- whoever runs the migration owns every object it
    # creates in the target, so it has no counterpart on the expected side.
    non_owner_rows = [
        r for r in workspace.rows("object_acls") if r.get("permission_level") != "IS_OWNER"
    ]
    assert len(entries) == len(non_owner_rows)
    assert all(e.permission_level != "IS_OWNER" for e in entries)
    assert diff(entries, entries) == {"missing_in_target": [], "extra_in_target": []}
