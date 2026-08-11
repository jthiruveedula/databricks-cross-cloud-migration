from __future__ import annotations

import pytest

from dbxmig.grants import (
    PrincipalMap,
    UnmappedPrincipalError,
    diff_grants,
    expected_grants_after_translation,
    grant_statement,
    normalise_privilege,
    translate_grants,
)
from dbxmig.models import Grant, Inventory

MAP = PrincipalMap(
    mapping={
        "data-readers": "data-readers",
        "sales-eng": "sales-engineering",
        "pii-readers": "pii-readers",
        "platform-admins": "data-platform-admins",
        "finance-eng": "finance-engineering",
    },
    retired={"departed-contractor"},
)


def test_legacy_hive_privilege_is_translated():
    assert normalise_privilege("USAGE") == "USE SCHEMA"
    assert normalise_privilege("READ_METADATA") == "BROWSE"
    assert normalise_privilege("select") == "SELECT"


def test_metastore_bootstrap_privileges_are_not_replayed():
    assert normalise_privilege("CREATE_EXTERNAL_LOCATION") is None


def test_unmapped_principal_is_fatal_in_strict_mode(inventory: Inventory):
    empty = PrincipalMap(mapping={})
    with pytest.raises(UnmappedPrincipalError):
        translate_grants(inventory.grants, empty, strict=True)


def test_non_strict_mode_collects_every_unmapped_principal_at_once(inventory: Inventory):
    result = translate_grants(inventory.grants, PrincipalMap(mapping={}), strict=False)
    assert "data-readers" in result.unmapped_principals
    assert "sales-eng" in result.unmapped_principals
    # A retired principal is a decision, not a gap.
    assert result.statements == []


def test_retired_principal_is_skipped_with_a_reason(inventory: Inventory):
    result = translate_grants(inventory.grants, MAP, {"prod": "prod_gcp"}, strict=True)
    reasons = {grant.principal: reason for grant, reason in result.skipped}
    assert reasons["departed-contractor"] == "principal retired"


def test_statements_are_ordered_catalog_then_schema_then_table(inventory: Inventory):
    result = translate_grants(inventory.grants, MAP, {"prod": "prod_gcp"}, strict=True)
    depths = []
    for statement in result.statements:
        # depth = dots inside the backticked securable name
        securable = statement.split(" ON ", 1)[1].split(" TO ", 1)[0]
        depths.append(securable.count("`.`"))
    assert depths == sorted(depths)


def test_catalog_rename_is_applied_to_the_securable(inventory: Inventory):
    result = translate_grants(inventory.grants, MAP, {"prod": "prod_gcp"}, strict=True)
    joined = "\n".join(result.statements)
    assert "`prod_gcp`" in joined
    assert "ON CATALOG `prod`" not in joined


def test_grant_statement_quotes_identifiers():
    grant = Grant("TABLE", "cat.sch.weird`name", "grp", "SELECT")
    statement = grant_statement(grant, grant.full_name, "target-grp")
    assert statement == "GRANT SELECT ON TABLE `cat`.`sch`.`weird``name` TO `target-grp`;"


def test_catalog_securable_is_not_dotted():
    grant = Grant("CATALOG", "prod", "grp", "USE CATALOG")
    assert grant_statement(grant, "prod_gcp", "grp") == (
        "GRANT USE CATALOG ON CATALOG `prod_gcp` TO `grp`;"
    )


def test_diff_reports_missing_and_extra_grants():
    expected = [Grant("TABLE", "c.s.t", "grp", "SELECT")]
    actual = [Grant("TABLE", "c.s.t", "other", "SELECT")]
    diff = diff_grants(expected, actual)
    assert not diff.clean
    assert diff.missing_in_target[0].principal == "grp"
    assert diff.extra_in_target[0].principal == "other"


def test_diff_is_clean_when_translation_matches_reality(inventory: Inventory):
    expected = expected_grants_after_translation(inventory.grants, MAP, {"prod": "prod_gcp"})
    assert diff_grants(expected, expected).clean


def test_diff_normalises_legacy_privileges_before_comparing():
    expected = [Grant("SCHEMA", "c.s", "grp", "USE SCHEMA")]
    actual = [Grant("SCHEMA", "c.s", "grp", "USAGE")]
    assert diff_grants(expected, actual).clean
