"""Gated LLM assist for the long tail the rule engine cannot rewrite.

This implements the runbook's hybrid pattern literally, and the ordering of the
three functions below *is* the pattern:

1. ``needs_assist`` -- the deterministic rewriter runs first, always. The model
   is only consulted for what is left over. If ``rewrite.py`` handled the
   object, no call is made and no tokens are spent.
2. ``redact`` -- string literals and known-sensitive identifiers are stripped
   before anything leaves the process, so a stored procedure full of customer
   values is not what gets sent for translation.
3. ``validate_translation`` -- the model's output is checked mechanically before
   it is allowed anywhere near the target: single statement, correct object
   name, no source URIs left, no references outside the allow-list. Output that
   fails the gate is discarded and the object is escalated to a human. The model
   is never trusted on the strength of the output looking plausible.

Model id and prompt version are recorded with every result so a migration can be
re-run and audited: "which model wrote this view, from which prompt" is a
question a regulated migration will be asked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .rewrite import Rewriter

#: Bumped whenever the prompt text changes. Recorded alongside every output so
#: a translation can be traced to the exact instructions that produced it.
PROMPT_VERSION = "2026-08-11.1"

SYSTEM_PROMPT = """You translate Databricks SQL object definitions between cloud \
storage backends during a Unity Catalog metastore migration.

Rules you must follow exactly:
- Return ONE SQL statement and nothing else. No prose, no markdown fence, no explanation.
- Preserve the query semantics exactly. Do not add, remove, or reorder columns.
- Do not invent columns, tables, or functions. Only reference names given to you.
- Rewrite storage URIs and catalog names using the supplied mapping only.
- If a required mapping is missing, return the single token: NEEDS_HUMAN_REVIEW
"""

_REDACTION = "'<redacted>'"
_STRING_LITERAL = re.compile(r"'(?:[^']|'')*'")
_STATEMENT_SPLIT = re.compile(r";\s*\S")


@dataclass(frozen=True)
class Translation:
    """One model output plus everything needed to audit or reject it."""

    object_name: str
    sql: str
    model: str
    prompt_version: str
    accepted: bool
    rejection_reason: Optional[str] = None
    redacted_literals: int = 0


@dataclass(frozen=True)
class AssistDecision:
    needed: bool
    reason: str = ""
    unmapped: Sequence[str] = ()


def needs_assist(rewriter: Rewriter, sql: Optional[str]) -> AssistDecision:
    """Decide whether the deterministic pass left anything for a model to do.

    The answer is "no" for the overwhelming majority of objects, and that is the
    point: LLM cost and LLM risk scale with the size of the residue, not the
    size of the estate.
    """
    if not sql:
        return AssistDecision(False, "no definition to rewrite")
    unmapped = rewriter.find_unmapped(sql)
    if unmapped:
        return AssistDecision(True, "unmapped storage URIs in definition", tuple(unmapped))
    return AssistDecision(False, "deterministic rewrite is complete")


def redact(sql: str, keep_patterns: Optional[Sequence[str]] = None) -> "tuple[str, int]":
    """Replace string literals with a placeholder before sending code off-process.

    ``keep_patterns`` are regexes for literals that must survive because the
    translation depends on them -- storage URIs, most often. Everything else
    becomes ``'<redacted>'``.
    """
    keep = [re.compile(p, re.IGNORECASE) for p in (keep_patterns or [])]
    count = 0

    def replace(match: "re.Match[str]") -> str:
        nonlocal count
        literal = match.group(0)
        for pattern in keep:
            if pattern.search(literal):
                return literal
        count += 1
        return _REDACTION

    return _STRING_LITERAL.sub(replace, sql), count


def build_prompt(
    object_name: str,
    sql: str,
    allowed_names: Sequence[str],
    path_mapping: Dict[str, str],
) -> str:
    lines = [
        "Object being migrated: {0}".format(object_name),
        "",
        "Storage path mapping (source -> target):",
    ]
    for source, target in sorted(path_mapping.items()):
        lines.append("  {0} -> {1}".format(source, target))
    if not path_mapping:
        lines.append("  (none supplied)")
    lines.extend(
        [
            "",
            "Object names you may reference (no others exist in the target):",
        ]
    )
    for name in sorted(allowed_names):
        lines.append("  " + name)
    lines.extend(["", "Source definition:", sql.strip()])
    return "\n".join(lines)


def validate_translation(
    candidate: str,
    object_name: str,
    rewriter: Rewriter,
    allowed_names: Sequence[str],
) -> Optional[str]:
    """Mechanical gate. Returns a rejection reason, or ``None`` when acceptable.

    This runs on every model output without exception. It cannot prove semantic
    equivalence -- only reconciliation against real data does that -- but it
    eliminates the failure modes that get past a human skim: an extra statement
    appended, a hallucinated table name, a source URI left in place.
    """
    if not candidate or not candidate.strip():
        return "empty response"
    text = candidate.strip()
    if "NEEDS_HUMAN_REVIEW" in text:
        return "model declined: missing mapping"
    if text.startswith("```"):
        return "response is fenced markdown, not bare SQL"
    body = text.rstrip(";").strip()
    if _STATEMENT_SPLIT.search(body):
        return "response contains more than one statement"
    upper = body.upper()
    if not (upper.startswith("CREATE OR REPLACE VIEW") or upper.startswith("CREATE VIEW")):
        return "response is not a CREATE VIEW statement"
    if object_name.split(".")[-1].lower() not in body.lower():
        return "response does not define {0}".format(object_name)
    residual = rewriter.find_unmapped(body)
    if residual:
        return "response still contains unmapped source URIs: {0}".format(", ".join(residual))
    unknown = _unknown_references(body, allowed_names)
    if unknown:
        return "response references objects not in the allow-list: {0}".format(", ".join(unknown))
    return None


def _unknown_references(sql: str, allowed_names: Sequence[str]) -> List[str]:
    """Three-part names in the SQL that are not in the allow-list.

    Deliberately conservative: only fully-qualified ``a.b.c`` references are
    checked, because those are the ones a model hallucinates. Bare column names
    are not resolvable without a parser and are caught by reconciliation.
    """
    allowed = {name.lower() for name in allowed_names}
    pattern = re.compile(r"\b([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)\b")
    unknown: List[str] = []
    for match in pattern.finditer(sql):
        name = match.group(0).lower()
        if name not in allowed and name not in unknown:
            unknown.append(match.group(0))
    return unknown


class LlmClient:
    """Minimal interface an assist backend must satisfy."""

    model: str = "none"

    def complete(self, system: str, user: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError


class NullLlmClient(LlmClient):
    """Default backend: refuses to translate anything.

    A migration that has not explicitly configured a model endpoint gets zero
    LLM involvement rather than a silent default, and every object that would
    have needed assistance is escalated to a human instead.
    """

    model = "null"

    def complete(self, system: str, user: str) -> str:
        return "NEEDS_HUMAN_REVIEW"


class DatabricksServingClient(LlmClient):
    """Calls a Databricks Model Serving endpoint in the customer's own workspace.

    Keeping inference inside the workspace is what makes this usable for a
    regulated migration: code and schema never leave the account boundary, and
    the call is logged in system tables like any other workspace activity.
    """

    def __init__(self, workspace_client: Any, endpoint: str, max_tokens: int = 2048) -> None:
        self._client = workspace_client
        self.endpoint = endpoint
        self.model = "databricks-serving:" + endpoint
        self.max_tokens = max_tokens

    def complete(self, system: str, user: str) -> str:
        response = self._client.serving_endpoints.query(
            name=self.endpoint,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=self.max_tokens,
            temperature=0.0,
        )
        choices = getattr(response, "choices", None) or []
        if not choices:
            return ""
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None) if message is not None else None
        return content or ""


@dataclass
class Assistant:
    """Ties the three stages together and records every call for audit."""

    rewriter: Rewriter
    client: LlmClient = field(default_factory=NullLlmClient)
    keep_literal_patterns: Sequence[str] = ("://", "^'/Volumes/")
    calls: List[Dict[str, Any]] = field(default_factory=list)

    def translate_view(
        self,
        object_name: str,
        sql: str,
        allowed_names: Sequence[str],
        path_mapping: Optional[Dict[str, str]] = None,
    ) -> Translation:
        decision = needs_assist(self.rewriter, sql)
        if not decision.needed:
            rewritten = self.rewriter.rewrite_sql(sql).value
            return Translation(
                object_name=object_name,
                sql=rewritten,
                model="deterministic",
                prompt_version=PROMPT_VERSION,
                accepted=True,
            )

        redacted, redaction_count = redact(sql, self.keep_literal_patterns)
        prompt = build_prompt(object_name, redacted, allowed_names, path_mapping or {})
        raw = self.client.complete(SYSTEM_PROMPT, prompt)
        reason = validate_translation(raw, object_name, self.rewriter, allowed_names)
        self.calls.append(
            {
                "object": object_name,
                "model": self.client.model,
                "prompt_version": PROMPT_VERSION,
                "redacted_literals": redaction_count,
                "accepted": reason is None,
                "rejection_reason": reason or "",
            }
        )
        return Translation(
            object_name=object_name,
            sql=raw.strip() if reason is None else "",
            model=self.client.model,
            prompt_version=PROMPT_VERSION,
            accepted=reason is None,
            rejection_reason=reason,
            redacted_literals=redaction_count,
        )
