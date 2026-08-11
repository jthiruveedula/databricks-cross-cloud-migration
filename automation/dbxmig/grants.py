"""Grant translation and replay.

Grants are the part of a metastore migration with no bulk copy operation and no
forgiving failure mode: a missed grant is invisible until a user or a job hits a
permission error in the target, usually days after cutover. This module makes
the grant set an explicit, diffable artifact.

Two rules drive the design:

* **Principals are account-scoped.** A source group name means nothing in the
  target account. Every grantee must resolve through an explicit mapping, and an
  unmapped principal is a hard failure, never a silent skip.
* **Grants apply top-down.** Catalog, then schema, then table/view/volume. A
  table grant issued before its schema grant can fail with a confusing
  permission error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .ddl import quote_ident, quote_name
from .models import Grant

#: Legacy Hive metastore privileges and their Unity Catalog equivalents. A
#: source estate that predates UC will export the left-hand names; issuing them
#: verbatim against a UC metastore fails.
LEGACY_PRIVILEGE_MAP = {
    "USAGE": "USE SCHEMA",
    "READ_METADATA": "BROWSE",
    "CREATE": "CREATE TABLE",
    "CREATE_NAMED_FUNCTION": "CREATE FUNCTION",
    "SELECT": "SELECT",
    "MODIFY": "MODIFY",
    "ALL PRIVILEGES": "ALL PRIVILEGES",
}

#: Privileges that exist on the source but must not be replayed: they are
#: granted by the target's own bootstrap, or they are meaningless off-cloud.
NON_REPLAYABLE_PRIVILEGES = frozenset(
    {
        "CREATE_STORAGE_CREDENTIAL",
        "CREATE_EXTERNAL_LOCATION",
        "CREATE_CONNECTION",
        "MANAGE_ALLOWLIST",
    }
)

#: The securable keyword each object type uses in a GRANT statement.
SECURABLE_KEYWORD = {
    "CATALOG": "CATALOG",
    "SCHEMA": "SCHEMA",
    "DATABASE": "SCHEMA",
    "TABLE": "TABLE",
    "VIEW": "VIEW",
    "MATERIALIZED_VIEW": "TABLE",
    "STREAMING_TABLE": "TABLE",
    "VOLUME": "VOLUME",
    "FUNCTION": "FUNCTION",
    "REGISTERED_MODEL": "MODEL",
    "MODEL": "MODEL",
    "EXTERNAL_LOCATION": "EXTERNAL LOCATION",
    "STORAGE_CREDENTIAL": "STORAGE CREDENTIAL",
    "CONNECTION": "CONNECTION",
}


class UnmappedPrincipalError(KeyError):
    """Raised when a source principal has no target mapping.

    Deliberately fatal. Skipping the grant would produce a target that looks
    migrated and quietly denies access to whoever held it.
    """


@dataclass
class PrincipalMap:
    """Source principal -> target principal, with the gaps kept visible."""

    mapping: Dict[str, str] = field(default_factory=dict)
    #: Principals intentionally dropped (leavers, decommissioned service
    #: principals). Recorded so "not migrated" is a decision, not an oversight.
    retired: Set[str] = field(default_factory=set)

    @classmethod
    def from_dict(cls, raw: Dict[str, object]) -> "PrincipalMap":
        mapping = {str(k): str(v) for k, v in (raw.get("mapping") or {}).items()}
        retired = {str(p) for p in (raw.get("retired") or [])}
        # A flat {source: target} file is also accepted.
        if not mapping and not retired:
            mapping = {str(k): str(v) for k, v in raw.items() if isinstance(v, str)}
        return cls(mapping=mapping, retired=retired)

    def resolve(self, principal: str) -> Optional[str]:
        if principal in self.retired:
            return None
        target = self.mapping.get(principal)
        if target is None:
            raise UnmappedPrincipalError(principal)
        return target

    def unmapped(self, grants: Iterable[Grant]) -> List[str]:
        """Principals in the grant set with neither a mapping nor a retirement."""
        missing = {
            g.principal
            for g in grants
            if g.principal and g.principal not in self.mapping and g.principal not in self.retired
        }
        return sorted(missing)


def normalise_privilege(privilege: str) -> Optional[str]:
    """Map a source privilege onto its target name, or ``None`` if not replayable."""
    upper = (privilege or "").strip().upper().replace("  ", " ")
    if not upper or upper in NON_REPLAYABLE_PRIVILEGES:
        return None
    return LEGACY_PRIVILEGE_MAP.get(upper, upper)


def _principal_sql(principal: str) -> str:
    """Quote a grantee. Account groups and users both take backticks in UC."""
    return quote_ident(principal)


def grant_statement(grant: Grant, target_full_name: str, target_principal: str) -> Optional[str]:
    privilege = normalise_privilege(grant.privilege)
    if privilege is None:
        return None
    keyword = SECURABLE_KEYWORD.get(grant.object_type.upper())
    if keyword is None:
        return None
    if keyword in ("EXTERNAL LOCATION", "STORAGE CREDENTIAL", "CONNECTION", "CATALOG"):
        securable = "{0} {1}".format(keyword, quote_ident(target_full_name))
    else:
        securable = "{0} {1}".format(keyword, quote_name(target_full_name))
    return "GRANT {0} ON {1} TO {2};".format(privilege, securable, _principal_sql(target_principal))


@dataclass
class GrantTranslation:
    statements: List[str] = field(default_factory=list)
    skipped: List[Tuple[Grant, str]] = field(default_factory=list)
    unmapped_principals: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.unmapped_principals


def translate_grants(
    grants: Sequence[Grant],
    principal_map: PrincipalMap,
    catalog_map: Optional[Dict[str, str]] = None,
    strict: bool = True,
) -> GrantTranslation:
    """Turn a source grant export into ordered, target-ready GRANT statements.

    With ``strict=True`` (the default and the recommended setting for a real
    run) an unmapped principal aborts translation. With ``strict=False`` the
    unmapped set is collected and returned so the mapping file can be completed
    in one pass instead of one error at a time.
    """
    catalog_map = catalog_map or {}
    result = GrantTranslation()
    missing = principal_map.unmapped(grants)
    if missing:
        result.unmapped_principals = missing
        if strict:
            raise UnmappedPrincipalError(
                "no target mapping for {0} principal(s): {1}".format(
                    len(missing), ", ".join(missing)
                )
            )

    def retarget(full_name: str) -> str:
        parts = full_name.split(".")
        if parts:
            parts[0] = catalog_map.get(parts[0], parts[0])
        return ".".join(parts)

    # Top-down: catalog (0 dots), schema (1), table/view/volume (2). Within a
    # depth, sort by name then principal so two runs emit byte-identical output.
    ordered = sorted(grants, key=lambda g: (g.depth, g.full_name, g.principal, g.privilege))
    for grant in ordered:
        if grant.principal in principal_map.retired:
            result.skipped.append((grant, "principal retired"))
            continue
        target_principal = principal_map.mapping.get(grant.principal)
        if target_principal is None:
            result.skipped.append((grant, "principal unmapped"))
            continue
        statement = grant_statement(grant, retarget(grant.full_name), target_principal)
        if statement is None:
            result.skipped.append((grant, "privilege not replayable: {0}".format(grant.privilege)))
            continue
        result.statements.append(statement)
    return result


@dataclass
class GrantDiff:
    missing_in_target: List[Grant] = field(default_factory=list)
    extra_in_target: List[Grant] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.missing_in_target and not self.extra_in_target


def diff_grants(
    expected: Sequence[Grant],
    actual: Sequence[Grant],
) -> GrantDiff:
    """Compare an expected (translated) grant set against what the target reports.

    Run this at cutover and again on a schedule through hypercare -- grants
    drift, and the drift is only ever discovered by a user losing access.
    """

    def key(grant: Grant) -> Tuple[str, str, str, str]:
        return (
            grant.object_type.upper(),
            grant.full_name,
            grant.principal,
            (normalise_privilege(grant.privilege) or grant.privilege).upper(),
        )

    expected_index = {key(g): g for g in expected}
    actual_index = {key(g): g for g in actual}
    missing = [expected_index[k] for k in sorted(set(expected_index) - set(actual_index))]
    extra = [actual_index[k] for k in sorted(set(actual_index) - set(expected_index))]
    return GrantDiff(missing_in_target=missing, extra_in_target=extra)


def expected_grants_after_translation(
    grants: Sequence[Grant],
    principal_map: PrincipalMap,
    catalog_map: Optional[Dict[str, str]] = None,
) -> List[Grant]:
    """The grant set the target *should* report once replay succeeds."""
    catalog_map = catalog_map or {}
    expected: List[Grant] = []
    for grant in grants:
        target_principal = principal_map.mapping.get(grant.principal)
        if target_principal is None:
            continue
        privilege = normalise_privilege(grant.privilege)
        if privilege is None:
            continue
        parts = grant.full_name.split(".")
        if parts:
            parts[0] = catalog_map.get(parts[0], parts[0])
        expected.append(
            Grant(
                object_type=grant.object_type.upper(),
                full_name=".".join(parts),
                principal=target_principal,
                privilege=privilege,
            )
        )
    return expected
