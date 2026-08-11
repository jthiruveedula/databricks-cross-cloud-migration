"""Target DDL emission.

Pure string generation -- nothing here connects to a workspace. That is
deliberate: the generated SQL is a reviewable artifact. A migration you can read
as a diff before anyone runs it is a migration a security reviewer can sign off
on, and a failed run can be re-driven from the same file.

Every statement is written to be idempotent (``IF NOT EXISTS`` / ``OR REPLACE``)
so a half-finished run can be re-executed from the top without manual cleanup.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .models import Catalog, Column, Function, Schema, Table, Volume


def quote_ident(name: str) -> str:
    """Backtick-quote one identifier part, escaping embedded backticks."""
    return "`" + name.replace("`", "``") + "`"


def quote_name(full_name: str) -> str:
    """Backtick-quote a dotted name part by part: ``a.b.c`` -> ``` `a`.`b`.`c` ```."""
    return ".".join(quote_ident(part) for part in full_name.split(".") if part != "")


def quote_literal(value: str) -> str:
    """Single-quote a string literal, escaping quotes and backslashes."""
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return "'" + escaped + "'"


def _properties_clause(properties: Dict[str, str]) -> str:
    if not properties:
        return ""
    pairs = ", ".join(
        "{0} = {1}".format(quote_literal(k), quote_literal(v))
        for k, v in sorted(properties.items())
    )
    return " TBLPROPERTIES ({0})".format(pairs)


def create_catalog(
    catalog: Catalog, target_name: str, managed_location: Optional[str] = None
) -> str:
    parts = ["CREATE CATALOG IF NOT EXISTS {0}".format(quote_ident(target_name))]
    if managed_location:
        parts.append("MANAGED LOCATION {0}".format(quote_literal(managed_location)))
    if catalog.comment:
        parts.append("COMMENT {0}".format(quote_literal(catalog.comment)))
    return " ".join(parts) + ";"


def create_schema(schema: Schema, target_name: str, managed_location: Optional[str] = None) -> str:
    parts = ["CREATE SCHEMA IF NOT EXISTS {0}".format(quote_name(target_name))]
    if managed_location:
        parts.append("MANAGED LOCATION {0}".format(quote_literal(managed_location)))
    if schema.comment:
        parts.append("COMMENT {0}".format(quote_literal(schema.comment)))
    statements = [" ".join(parts) + ";"]
    if schema.properties:
        statements.append(
            "ALTER SCHEMA {0} SET DBPROPERTIES ({1});".format(
                quote_name(target_name),
                ", ".join(
                    "{0} = {1}".format(quote_literal(k), quote_literal(v))
                    for k, v in sorted(schema.properties.items())
                ),
            )
        )
    return "\n".join(statements)


def create_external_location(
    name: str, url: str, credential_name: str, read_only: bool = False
) -> str:
    statement = (
        "CREATE EXTERNAL LOCATION IF NOT EXISTS {0} URL {1} "
        "WITH (STORAGE CREDENTIAL {2})".format(
            quote_ident(name), quote_literal(url), quote_ident(credential_name)
        )
    )
    if read_only:
        statement += " READ_ONLY"
    return statement + ";"


def create_volume(volume: Volume, target_name: str, target_location: Optional[str] = None) -> str:
    if volume.volume_type == "EXTERNAL":
        if not target_location:
            raise ValueError("external volume {0} needs a target location".format(volume.full_name))
        statement = "CREATE EXTERNAL VOLUME IF NOT EXISTS {0} LOCATION {1}".format(
            quote_name(target_name), quote_literal(target_location)
        )
    else:
        statement = "CREATE VOLUME IF NOT EXISTS {0}".format(quote_name(target_name))
    if volume.comment:
        statement += " COMMENT {0}".format(quote_literal(volume.comment))
    return statement + ";"


def deep_clone(
    source_full_name: str,
    target_full_name: str,
    target_location: Optional[str] = None,
    replace: bool = False,
) -> str:
    """``DEEP CLONE`` copies data and the current Delta log -- never grants.

    The target's ``DESCRIBE HISTORY`` starts at this CLONE operation; source
    history does not come with it. Reconciliation checks provenance, not history
    equality -- see ``reconcile.check_clone_provenance``.
    """
    head = "CREATE OR REPLACE TABLE" if replace else "CREATE TABLE IF NOT EXISTS"
    statement = "{0} {1} DEEP CLONE {2}".format(
        head, quote_name(target_full_name), quote_name(source_full_name)
    )
    if target_location:
        statement += " LOCATION {0}".format(quote_literal(target_location))
    return statement + ";"


def clone_at_version(source_full_name: str, target_full_name: str, version: int) -> str:
    """Pin a clone to a source version -- the pre-cutover snapshot pattern."""
    return "CREATE OR REPLACE TABLE {0} DEEP CLONE {1} VERSION AS OF {2};".format(
        quote_name(target_full_name), quote_name(source_full_name), int(version)
    )


def ctas(
    source_full_name: str,
    target_full_name: str,
    column_list: Optional[Iterable[str]] = None,
    target_location: Optional[str] = None,
    partition_columns: Optional[Iterable[str]] = None,
) -> str:
    """Non-Delta fallback. Loses history entirely -- a one-way door per table."""
    columns = ", ".join(quote_ident(c) for c in column_list) if column_list else "*"
    statement = "CREATE TABLE IF NOT EXISTS {0}".format(quote_name(target_full_name))
    if partition_columns:
        statement += " PARTITIONED BY ({0})".format(
            ", ".join(quote_ident(c) for c in partition_columns)
        )
    if target_location:
        statement += " LOCATION {0}".format(quote_literal(target_location))
    statement += " AS SELECT {0} FROM {1}".format(columns, quote_name(source_full_name))
    return statement + ";"


def create_view(target_full_name: str, view_definition: str, comment: Optional[str] = None) -> str:
    body = view_definition.strip().rstrip(";")
    statement = "CREATE OR REPLACE VIEW {0}".format(quote_name(target_full_name))
    if comment:
        statement += " COMMENT {0}".format(quote_literal(comment))
    return statement + " AS\n" + body + ";"


def create_function(function: Function, target_full_name: str, body: Optional[str] = None) -> str:
    """Emit a function definition.

    Unity Catalog's ``routine_definition`` is the body only, but an inventory
    captured by hand or by an older export often holds a whole ``CREATE
    FUNCTION`` statement. Both are accepted; the second is passed through with
    only its name rewritten, so the output is never a doubled statement.
    """
    definition = ((body if body is not None else function.routine_definition) or "").strip()
    definition = definition.rstrip(";")
    if definition.upper().startswith("CREATE "):
        return definition + ";"
    return "CREATE OR REPLACE FUNCTION {0}\n{1};".format(quote_name(target_full_name), definition)


def comment_on_column(table_full_name: str, column: Column) -> Optional[str]:
    if not column.comment:
        return None
    return "COMMENT ON COLUMN {0}.{1} IS {2};".format(
        quote_name(table_full_name), quote_ident(column.name), quote_literal(column.comment)
    )


def set_table_tags(table_full_name: str, tags: Dict[str, str]) -> Optional[str]:
    if not tags:
        return None
    pairs = ", ".join(
        "{0} = {1}".format(quote_literal(k), quote_literal(v)) for k, v in sorted(tags.items())
    )
    return "ALTER TABLE {0} SET TAGS ({1});".format(quote_name(table_full_name), pairs)


def set_table_properties(table_full_name: str, properties: Dict[str, str]) -> Optional[str]:
    """Re-apply table properties, minus the ones Databricks owns.

    Delta protocol and provenance keys are set by the engine when the target
    table is created; replaying them from the source either fails outright or
    pins the target to an older protocol than its runtime supports.
    """
    replayable = {
        key: value
        for key, value in properties.items()
        if not key.startswith("delta.minReaderVersion")
        and not key.startswith("delta.minWriterVersion")
        and not key.startswith("delta.feature.")
        and not key.startswith("delta.columnMapping.")
        and not key.startswith("spark.")
        and not key.lower().startswith("option.")
    }
    if not replayable:
        return None
    pairs = ", ".join(
        "{0} = {1}".format(quote_literal(k), quote_literal(v))
        for k, v in sorted(replayable.items())
    )
    return "ALTER TABLE {0} SET TBLPROPERTIES ({1});".format(quote_name(table_full_name), pairs)


def add_constraint(table_full_name: str, name: str, kind: str, definition: str) -> Optional[str]:
    """Emit a constraint. NOT NULL is a column alteration, not a constraint clause."""
    kind = kind.upper()
    if kind == "NOT_NULL":
        return "ALTER TABLE {0} ALTER COLUMN {1} SET NOT NULL;".format(
            quote_name(table_full_name), quote_ident(definition)
        )
    if kind == "CHECK":
        return "ALTER TABLE {0} ADD CONSTRAINT {1} CHECK ({2});".format(
            quote_name(table_full_name), quote_ident(name), definition
        )
    if kind in ("PRIMARY_KEY", "FOREIGN_KEY"):
        clause = "PRIMARY KEY" if kind == "PRIMARY_KEY" else "FOREIGN KEY"
        return "ALTER TABLE {0} ADD CONSTRAINT {1} {2} {3};".format(
            quote_name(table_full_name), quote_ident(name), clause, definition
        )
    return None


def set_owner(object_type: str, full_name: str, owner: str) -> str:
    """Ownership is not a grant and is not replayed by ``GRANT`` statements."""
    keyword = "CATALOG" if object_type == "CATALOG" else object_type.replace("_", " ")
    return "ALTER {0} {1} SET OWNER TO {2};".format(
        keyword, quote_name(full_name), quote_ident(owner)
    )


def table_ddl_bundle(
    table: Table,
    target_full_name: str,
    strategy: str,
    target_location: Optional[str] = None,
) -> List[str]:
    """All statements needed to stand up one table, in execution order."""
    statements: List[str] = []
    if strategy == "DEEP_CLONE":
        statements.append(deep_clone(table.full_name, target_full_name, target_location))
    elif strategy == "CTAS":
        statements.append(
            ctas(
                table.full_name,
                target_full_name,
                target_location=target_location,
                partition_columns=table.partition_columns,
            )
        )
    if table.comment:
        statements.append(
            "COMMENT ON TABLE {0} IS {1};".format(
                quote_name(target_full_name), quote_literal(table.comment)
            )
        )
    for column in table.columns:
        statement = comment_on_column(target_full_name, column)
        if statement:
            statements.append(statement)
    properties = set_table_properties(target_full_name, table.properties)
    if properties:
        statements.append(properties)
    tags = set_table_tags(target_full_name, table.tags)
    if tags:
        statements.append(tags)
    for constraint in table.constraints:
        statement = add_constraint(
            target_full_name, constraint.name, constraint.kind, constraint.definition
        )
        if statement:
            statements.append(statement)
    return statements
