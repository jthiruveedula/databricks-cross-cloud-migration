"""Migration configuration: one file that is the contract for the whole run.

Everything environment-specific lives here -- source and target workspaces,
catalog renames, storage path rules, where managed data lands, which principals
map to which, whether LLM assist is switched on. Nothing environment-specific is
passed on the command line, so the same command produces the same result on
anyone's machine and the config file is the thing that gets reviewed and
version-controlled.

Validation is strict and up front. A path rule missing its target, or a catalog
rename pointing at a catalog that is not in scope, is a config error caught
before the first statement runs -- not a partial migration discovered later.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .rewrite import PathRule, Rewriter, rules_from_config


class ConfigError(ValueError):
    """Raised for any structurally invalid configuration."""


@dataclass
class WorkspaceConfig:
    host: str = ""
    warehouse_id: str = ""
    profile: Optional[str] = None
    token_env: str = ""
    cloud: str = ""
    catalogs: List[str] = field(default_factory=list)

    @property
    def token(self) -> Optional[str]:
        """Read the token from the environment, never from the config file."""
        return os.environ.get(self.token_env) if self.token_env else None

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "WorkspaceConfig":
        return cls(
            host=str(raw.get("host", "")),
            warehouse_id=str(raw.get("warehouse_id", "")),
            profile=raw.get("profile"),
            token_env=str(raw.get("token_env", "")),
            cloud=str(raw.get("cloud", "")).lower(),
            catalogs=[str(c) for c in (raw.get("catalogs") or [])],
        )


@dataclass
class LlmConfig:
    #: Off by default. A migration only uses a model when someone decides it
    #: should, and then only for objects the rule engine could not finish.
    enabled: bool = False
    endpoint: str = ""
    max_tokens: int = 2048

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "LlmConfig":
        return cls(
            enabled=bool(raw.get("enabled", False)),
            endpoint=str(raw.get("endpoint", "")),
            max_tokens=int(raw.get("max_tokens", 2048)),
        )


@dataclass
class MigrationConfig:
    source: WorkspaceConfig = field(default_factory=WorkspaceConfig)
    target: WorkspaceConfig = field(default_factory=WorkspaceConfig)
    catalog_map: Dict[str, str] = field(default_factory=dict)
    path_rules: List[PathRule] = field(default_factory=list)
    #: target catalog/schema name -> MANAGED LOCATION URI
    managed_locations: Dict[str, str] = field(default_factory=dict)
    #: source table full name -> explicit target LOCATION, for external tables
    table_locations: Dict[str, str] = field(default_factory=dict)
    principal_map_file: str = ""
    llm: LlmConfig = field(default_factory=LlmConfig)
    state_file: str = ".dbxmig/journal.jsonl"
    row_count_tolerance: int = 0
    lineage_days: int = 90

    def rewriter(self) -> Rewriter:
        return Rewriter(path_rules=list(self.path_rules), catalog_map=dict(self.catalog_map))

    def source_prefixes(self) -> List[str]:
        return [rule.source_prefix for rule in self.path_rules]

    def target_location_for(
        self, table_full_name: str, storage_location: Optional[str]
    ) -> Optional[str]:
        """Explicit override first, then the path rules, then nothing.

        Returning ``None`` is meaningful: the planner turns it into a blocked
        step for external tables rather than inventing a location.
        """
        override = self.table_locations.get(table_full_name)
        if override:
            return override
        if not storage_location:
            return None
        result = self.rewriter().rewrite_uri(storage_location)
        return result.value if result.mapped else None

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "MigrationConfig":
        if not isinstance(raw, dict):
            raise ConfigError("configuration root must be a mapping")
        config = cls(
            source=WorkspaceConfig.from_dict(raw.get("source") or {}),
            target=WorkspaceConfig.from_dict(raw.get("target") or {}),
            catalog_map={str(k): str(v) for k, v in (raw.get("catalog_map") or {}).items()},
            path_rules=rules_from_config(raw.get("path_rules") or []),
            managed_locations={
                str(k): str(v) for k, v in (raw.get("managed_locations") or {}).items()
            },
            table_locations={str(k): str(v) for k, v in (raw.get("table_locations") or {}).items()},
            principal_map_file=str(raw.get("principal_map_file", "")),
            llm=LlmConfig.from_dict(raw.get("llm") or {}),
            state_file=str(raw.get("state_file", ".dbxmig/journal.jsonl")),
            row_count_tolerance=int(raw.get("row_count_tolerance", 0)),
            lineage_days=int(raw.get("lineage_days", 90)),
        )
        config.validate()
        return config

    def validate(self) -> None:
        problems = self.problems()
        if problems:
            raise ConfigError("invalid configuration:\n  - " + "\n  - ".join(problems))

    def problems(self) -> List[str]:
        problems: List[str] = []
        if self.llm.enabled and not self.llm.endpoint:
            problems.append("llm.enabled is true but llm.endpoint is empty")
        scope = set(self.source.catalogs)
        for source_catalog in self.catalog_map:
            if scope and source_catalog not in scope:
                problems.append(
                    "catalog_map renames {0!r}, which is not in source.catalogs".format(
                        source_catalog
                    )
                )
        seen_targets: Dict[str, str] = {}
        for source_catalog, target_catalog in self.catalog_map.items():
            if target_catalog in seen_targets:
                problems.append(
                    "catalog_map sends both {0!r} and {1!r} to {2!r}".format(
                        seen_targets[target_catalog], source_catalog, target_catalog
                    )
                )
            seen_targets[target_catalog] = source_catalog
        for rule in self.path_rules:
            if not rule.target_prefix:
                problems.append(
                    "path rule for {0!r} has an empty target".format(rule.source_prefix)
                )
            if rule.source_prefix == rule.target_prefix:
                problems.append(
                    "path rule for {0!r} is a no-op (source equals target)".format(
                        rule.source_prefix
                    )
                )
        if self.row_count_tolerance < 0:
            problems.append("row_count_tolerance cannot be negative")
        return problems


def load_config(path: str) -> MigrationConfig:
    """Load YAML or JSON. YAML needs PyYAML; JSON always works."""
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    return MigrationConfig.from_dict(parse_config_text(text, path))


def parse_config_text(text: str, path: str = "<string>") -> Dict[str, Any]:
    if path.endswith(".json"):
        return json.loads(text)
    try:
        import yaml  # type: ignore import-not-found
    except ImportError:  # pragma: no cover - PyYAML is a declared dependency
        try:
            return json.loads(text)
        except ValueError as exc:
            raise ConfigError(
                "PyYAML is not installed and {0} is not valid JSON".format(path)
            ) from exc
    loaded = yaml.safe_load(text)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ConfigError(
            "configuration root must be a mapping, got {0}".format(type(loaded).__name__)
        )
    return loaded


def load_principal_map(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
