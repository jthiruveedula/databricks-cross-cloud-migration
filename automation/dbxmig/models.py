"""Typed representation of a Unity Catalog metastore inventory.

Everything the toolkit does downstream -- planning, DDL emission, grant replay,
reconciliation -- reads these objects, never a raw API response. That keeps the
Databricks SDK at the edge of the system (``gateway.py``) and lets every other
module be tested offline against a JSON fixture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

# Table types that Unity Catalog reports and this toolkit reasons about.
MANAGED = "MANAGED"
EXTERNAL = "EXTERNAL"
VIEW = "VIEW"
MATERIALIZED_VIEW = "MATERIALIZED_VIEW"
STREAMING_TABLE = "STREAMING_TABLE"
FOREIGN = "FOREIGN"

#: Table types that ``CREATE TABLE ... CLONE`` refuses as source or target.
#: Materialized views and streaming tables are pipeline outputs -- the pipeline
#: is the migratable object, not the table.
#: https://docs.databricks.com/aws/en/sql/language-manual/delta-clone
NON_CLONABLE_TABLE_TYPES = frozenset({MATERIALIZED_VIEW, STREAMING_TABLE, FOREIGN})

#: Delta is the only format ``CLONE`` accepts. Everything else has to be read
#: and rewritten (CTAS), which is why format is a planning input and not a
#: cosmetic attribute.
CLONABLE_FORMATS = frozenset({"DELTA", "UNITY_CATALOG"})


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


@dataclass(frozen=True)
class Column:
    name: str
    type_text: str
    nullable: bool = True
    comment: Optional[str] = None
    position: int = 0
    tags: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Column":
        return cls(
            name=raw["name"],
            type_text=raw.get("type_text") or raw.get("type") or "STRING",
            nullable=bool(raw.get("nullable", True)),
            comment=raw.get("comment"),
            position=int(raw.get("position", 0)),
            tags=dict(raw.get("tags") or {}),
        )


@dataclass(frozen=True)
class Constraint:
    name: str
    kind: str  # PRIMARY_KEY | FOREIGN_KEY | CHECK | NOT_NULL
    definition: str

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Constraint":
        return cls(
            name=raw["name"],
            kind=raw.get("kind", "CHECK").upper(),
            definition=raw.get("definition", ""),
        )


@dataclass(frozen=True)
class StorageCredential:
    name: str
    cloud: str = ""
    comment: Optional[str] = None
    read_only: bool = False

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "StorageCredential":
        return cls(
            name=raw["name"],
            cloud=raw.get("cloud", ""),
            comment=raw.get("comment"),
            read_only=bool(raw.get("read_only", False)),
        )


@dataclass(frozen=True)
class ExternalLocation:
    name: str
    url: str
    credential_name: str
    read_only: bool = False
    comment: Optional[str] = None

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ExternalLocation":
        return cls(
            name=raw["name"],
            url=raw["url"],
            credential_name=raw.get("credential_name", ""),
            read_only=bool(raw.get("read_only", False)),
            comment=raw.get("comment"),
        )


@dataclass(frozen=True)
class Catalog:
    name: str
    comment: Optional[str] = None
    owner: Optional[str] = None
    storage_root: Optional[str] = None
    isolation_mode: Optional[str] = None  # OPEN | ISOLATED
    properties: Dict[str, str] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    workspace_bindings: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Catalog":
        return cls(
            name=raw["name"],
            comment=raw.get("comment"),
            owner=raw.get("owner"),
            storage_root=raw.get("storage_root"),
            isolation_mode=raw.get("isolation_mode"),
            properties=dict(raw.get("properties") or {}),
            tags=dict(raw.get("tags") or {}),
            workspace_bindings=[str(w) for w in _as_list(raw.get("workspace_bindings"))],
        )


@dataclass(frozen=True)
class Schema:
    catalog: str
    name: str
    comment: Optional[str] = None
    owner: Optional[str] = None
    storage_root: Optional[str] = None
    properties: Dict[str, str] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        return "{0}.{1}".format(self.catalog, self.name)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Schema":
        return cls(
            catalog=raw["catalog"],
            name=raw["name"],
            comment=raw.get("comment"),
            owner=raw.get("owner"),
            storage_root=raw.get("storage_root"),
            properties=dict(raw.get("properties") or {}),
            tags=dict(raw.get("tags") or {}),
        )


@dataclass(frozen=True)
class Table:
    catalog: str
    schema: str
    name: str
    table_type: str = MANAGED
    data_source_format: str = "DELTA"
    storage_location: Optional[str] = None
    columns: List[Column] = field(default_factory=list)
    partition_columns: List[str] = field(default_factory=list)
    cluster_columns: List[str] = field(default_factory=list)
    constraints: List[Constraint] = field(default_factory=list)
    properties: Dict[str, str] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    comment: Optional[str] = None
    owner: Optional[str] = None
    view_definition: Optional[str] = None
    #: Fully-qualified names this object reads from. Populated for views,
    #: materialized views, and streaming tables -- it is what makes the
    #: dependency graph a graph rather than a flat list.
    depends_on: List[str] = field(default_factory=list)
    row_filter: Optional[str] = None
    column_masks: Dict[str, str] = field(default_factory=dict)
    size_bytes: int = 0

    @property
    def full_name(self) -> str:
        return "{0}.{1}.{2}".format(self.catalog, self.schema, self.name)

    @property
    def schema_full_name(self) -> str:
        return "{0}.{1}".format(self.catalog, self.schema)

    @property
    def is_view(self) -> bool:
        return self.table_type == VIEW

    @property
    def is_clonable(self) -> bool:
        """True when ``CREATE TABLE ... DEEP CLONE`` is a legal strategy.

        Views are excluded because they carry no data; materialized views,
        streaming tables, and foreign tables because CLONE rejects them
        outright; non-Delta formats because CLONE is Delta-only.
        """
        if self.table_type in NON_CLONABLE_TABLE_TYPES or self.is_view:
            return False
        return (self.data_source_format or "").upper() in CLONABLE_FORMATS

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Table":
        return cls(
            catalog=raw["catalog"],
            schema=raw["schema"],
            name=raw["name"],
            table_type=(raw.get("table_type") or MANAGED).upper(),
            data_source_format=(raw.get("data_source_format") or "DELTA").upper(),
            storage_location=raw.get("storage_location"),
            columns=[Column.from_dict(c) for c in _as_list(raw.get("columns"))],
            partition_columns=[str(c) for c in _as_list(raw.get("partition_columns"))],
            cluster_columns=[str(c) for c in _as_list(raw.get("cluster_columns"))],
            constraints=[Constraint.from_dict(c) for c in _as_list(raw.get("constraints"))],
            properties=dict(raw.get("properties") or {}),
            tags=dict(raw.get("tags") or {}),
            comment=raw.get("comment"),
            owner=raw.get("owner"),
            view_definition=raw.get("view_definition"),
            depends_on=[str(d) for d in _as_list(raw.get("depends_on"))],
            row_filter=raw.get("row_filter"),
            column_masks=dict(raw.get("column_masks") or {}),
            size_bytes=int(raw.get("size_bytes", 0)),
        )


@dataclass(frozen=True)
class Volume:
    catalog: str
    schema: str
    name: str
    volume_type: str = "MANAGED"  # MANAGED | EXTERNAL
    storage_location: Optional[str] = None
    comment: Optional[str] = None
    owner: Optional[str] = None

    @property
    def full_name(self) -> str:
        return "{0}.{1}.{2}".format(self.catalog, self.schema, self.name)

    @property
    def schema_full_name(self) -> str:
        return "{0}.{1}".format(self.catalog, self.schema)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Volume":
        return cls(
            catalog=raw["catalog"],
            schema=raw["schema"],
            name=raw["name"],
            volume_type=(raw.get("volume_type") or "MANAGED").upper(),
            storage_location=raw.get("storage_location"),
            comment=raw.get("comment"),
            owner=raw.get("owner"),
        )


@dataclass(frozen=True)
class Function:
    catalog: str
    schema: str
    name: str
    language: str = "SQL"
    routine_definition: Optional[str] = None
    comment: Optional[str] = None
    owner: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return "{0}.{1}.{2}".format(self.catalog, self.schema, self.name)

    @property
    def schema_full_name(self) -> str:
        return "{0}.{1}".format(self.catalog, self.schema)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Function":
        return cls(
            catalog=raw["catalog"],
            schema=raw["schema"],
            name=raw["name"],
            language=(raw.get("language") or "SQL").upper(),
            routine_definition=raw.get("routine_definition"),
            comment=raw.get("comment"),
            owner=raw.get("owner"),
            depends_on=[str(d) for d in _as_list(raw.get("depends_on"))],
        )


@dataclass(frozen=True)
class RegisteredModel:
    catalog: str
    schema: str
    name: str
    owner: Optional[str] = None
    comment: Optional[str] = None
    version_count: int = 0

    @property
    def full_name(self) -> str:
        return "{0}.{1}.{2}".format(self.catalog, self.schema, self.name)

    @property
    def schema_full_name(self) -> str:
        return "{0}.{1}".format(self.catalog, self.schema)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "RegisteredModel":
        return cls(
            catalog=raw["catalog"],
            schema=raw["schema"],
            name=raw["name"],
            owner=raw.get("owner"),
            comment=raw.get("comment"),
            version_count=int(raw.get("version_count", 0)),
        )


@dataclass(frozen=True)
class Grant:
    """One privilege held by one principal on one securable."""

    object_type: str  # CATALOG | SCHEMA | TABLE | VIEW | VOLUME | FUNCTION | MODEL
    full_name: str
    principal: str
    privilege: str

    @property
    def depth(self) -> int:
        """Dot-count, used to apply grants top-down: catalog then schema then table."""
        return self.full_name.count(".")

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Grant":
        return cls(
            object_type=(raw.get("object_type") or "TABLE").upper(),
            full_name=raw["full_name"],
            principal=raw.get("principal") or raw.get("grantee", ""),
            privilege=(raw.get("privilege") or raw.get("privilege_type", "")).upper(),
        )


@dataclass
class Inventory:
    """Everything discovered in one source metastore, at one point in time."""

    metastore_id: str = ""
    metastore_name: str = ""
    cloud: str = ""
    region: str = ""
    captured_at: str = ""
    storage_credentials: List[StorageCredential] = field(default_factory=list)
    external_locations: List[ExternalLocation] = field(default_factory=list)
    catalogs: List[Catalog] = field(default_factory=list)
    schemas: List[Schema] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    volumes: List[Volume] = field(default_factory=list)
    functions: List[Function] = field(default_factory=list)
    models: List[RegisteredModel] = field(default_factory=list)
    grants: List[Grant] = field(default_factory=list)
    #: Metastore-level objects the toolkit records but cannot recreate
    #: automatically -- connections, shares, recipients. Surfaced in the gap
    #: report so they are migrated by hand rather than forgotten.
    connections: List[Dict[str, Any]] = field(default_factory=list)
    shares: List[Dict[str, Any]] = field(default_factory=list)
    recipients: List[Dict[str, Any]] = field(default_factory=list)

    def table_index(self) -> Dict[str, Table]:
        return {t.full_name: t for t in self.tables}

    def tables_in(self, catalog: str) -> List[Table]:
        return [t for t in self.tables if t.catalog == catalog]

    def counts(self) -> Dict[str, int]:
        """Object counts, the cheapest possible completeness check post-cutover."""
        by_type: Dict[str, int] = {
            "storage_credentials": len(self.storage_credentials),
            "external_locations": len(self.external_locations),
            "catalogs": len(self.catalogs),
            "schemas": len(self.schemas),
            "volumes": len(self.volumes),
            "functions": len(self.functions),
            "models": len(self.models),
            "grants": len(self.grants),
            "connections": len(self.connections),
            "shares": len(self.shares),
        }
        for table in self.tables:
            key = "tables_" + table.table_type.lower()
            by_type[key] = by_type.get(key, 0) + 1
        return by_type

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict

        return {
            "metastore_id": self.metastore_id,
            "metastore_name": self.metastore_name,
            "cloud": self.cloud,
            "region": self.region,
            "captured_at": self.captured_at,
            "storage_credentials": [asdict(o) for o in self.storage_credentials],
            "external_locations": [asdict(o) for o in self.external_locations],
            "catalogs": [asdict(o) for o in self.catalogs],
            "schemas": [asdict(o) for o in self.schemas],
            "tables": [asdict(o) for o in self.tables],
            "volumes": [asdict(o) for o in self.volumes],
            "functions": [asdict(o) for o in self.functions],
            "models": [asdict(o) for o in self.models],
            "grants": [asdict(o) for o in self.grants],
            "connections": list(self.connections),
            "shares": list(self.shares),
            "recipients": list(self.recipients),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Inventory":
        def build(key: str, factory: Any) -> List[Any]:
            return [factory(item) for item in _as_list(raw.get(key))]

        return cls(
            metastore_id=raw.get("metastore_id", ""),
            metastore_name=raw.get("metastore_name", ""),
            cloud=raw.get("cloud", ""),
            region=raw.get("region", ""),
            captured_at=raw.get("captured_at", ""),
            storage_credentials=build("storage_credentials", StorageCredential.from_dict),
            external_locations=build("external_locations", ExternalLocation.from_dict),
            catalogs=build("catalogs", Catalog.from_dict),
            schemas=build("schemas", Schema.from_dict),
            tables=build("tables", Table.from_dict),
            volumes=build("volumes", Volume.from_dict),
            functions=build("functions", Function.from_dict),
            models=build("models", RegisteredModel.from_dict),
            grants=build("grants", Grant.from_dict),
            connections=[dict(c) for c in _as_list(raw.get("connections"))],
            shares=[dict(s) for s in _as_list(raw.get("shares"))],
            recipients=[dict(r) for r in _as_list(raw.get("recipients"))],
        )


def sorted_by_name(items: Iterable[Any], key: str = "full_name") -> Sequence[Any]:
    """Deterministic ordering -- two runs of the toolkit must emit identical plans."""
    return sorted(items, key=lambda o: getattr(o, key, "") or "")
