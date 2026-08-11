from __future__ import annotations

from dbxmig.llm import (
    PROMPT_VERSION,
    Assistant,
    LlmClient,
    NullLlmClient,
    build_prompt,
    needs_assist,
    redact,
    validate_translation,
)
from dbxmig.rewrite import PathRule, Rewriter

ALLOWED = ["prod_gcp.sales.orders", "prod_gcp.sales.customers", "prod_gcp.sales.v_orders"]


def make_rewriter() -> Rewriter:
    return Rewriter(
        path_rules=[PathRule("abfss://raw@acct.dfs.core.windows.net/", "gs://acme-raw/")],
        catalog_map={"prod": "prod_gcp"},
    )


class StubClient(LlmClient):
    model = "stub"

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.response


def test_no_model_call_when_the_rule_engine_can_finish():
    rewriter = make_rewriter()
    sql = "SELECT * FROM prod.sales.orders WHERE p = 'abfss://raw@acct.dfs.core.windows.net/x'"
    assert not needs_assist(rewriter, sql).needed


def test_model_is_consulted_only_for_the_residue():
    rewriter = make_rewriter()
    sql = "SELECT * FROM delta.`abfss://other@legacy.dfs.core.windows.net/x`"
    decision = needs_assist(rewriter, sql)
    assert decision.needed
    assert decision.unmapped == ("abfss://other@legacy.dfs.core.windows.net/x",)


def test_deterministic_path_never_calls_the_client():
    client = StubClient("should not be used")
    assistant = Assistant(rewriter=make_rewriter(), client=client)
    translation = assistant.translate_view(
        "prod.sales.v_orders", "SELECT * FROM prod.sales.orders", ALLOWED
    )
    assert translation.model == "deterministic"
    assert translation.accepted
    assert "prod_gcp.sales.orders" in translation.sql
    assert client.calls == []


def test_literals_are_redacted_but_storage_uris_survive():
    sql = "SELECT * FROM t WHERE name = 'Jane Doe' AND p = 'abfss://raw@acct.dfs.core.windows.net/x'"
    redacted, count = redact(sql, ("://",))
    assert count == 1
    assert "Jane Doe" not in redacted
    assert "abfss://raw@acct.dfs.core.windows.net/x" in redacted


def test_prompt_lists_only_allowed_names():
    prompt = build_prompt("c.s.v", "SELECT 1", ALLOWED, {"a": "b"})
    assert "prod_gcp.sales.orders" in prompt
    assert "a -> b" in prompt


def test_gate_rejects_multiple_statements():
    rewriter = make_rewriter()
    candidate = "CREATE OR REPLACE VIEW prod_gcp.sales.v_orders AS SELECT 1; DROP TABLE x;"
    reason = validate_translation(candidate, "prod_gcp.sales.v_orders", rewriter, ALLOWED)
    assert reason == "response contains more than one statement"


def test_gate_rejects_hallucinated_object_names():
    rewriter = make_rewriter()
    candidate = (
        "CREATE OR REPLACE VIEW prod_gcp.sales.v_orders AS "
        "SELECT * FROM prod_gcp.sales.orders_archive"
    )
    reason = validate_translation(candidate, "prod_gcp.sales.v_orders", rewriter, ALLOWED)
    assert reason is not None and "allow-list" in reason


def test_gate_rejects_output_that_still_holds_a_source_uri():
    rewriter = make_rewriter()
    candidate = (
        "CREATE OR REPLACE VIEW prod_gcp.sales.v_orders AS "
        "SELECT * FROM delta.`abfss://other@legacy.dfs.core.windows.net/x`"
    )
    reason = validate_translation(candidate, "prod_gcp.sales.v_orders", rewriter, ALLOWED)
    assert reason is not None and "unmapped source URIs" in reason


def test_gate_rejects_non_view_statements_and_markdown():
    rewriter = make_rewriter()
    assert validate_translation("DROP TABLE x", "c.s.v", rewriter, ALLOWED) is not None
    assert "fenced" in validate_translation("```sql\nCREATE VIEW", "c.s.v", rewriter, ALLOWED)


def test_gate_accepts_a_clean_translation():
    rewriter = make_rewriter()
    candidate = (
        "CREATE OR REPLACE VIEW prod_gcp.sales.v_orders AS SELECT * FROM prod_gcp.sales.orders"
    )
    assert validate_translation(candidate, "prod_gcp.sales.v_orders", rewriter, ALLOWED) is None


def test_null_client_escalates_instead_of_guessing():
    assistant = Assistant(rewriter=make_rewriter(), client=NullLlmClient())
    translation = assistant.translate_view(
        "prod_gcp.sales.v_orders",
        "SELECT * FROM delta.`abfss://other@legacy.dfs.core.windows.net/x`",
        ALLOWED,
    )
    assert not translation.accepted
    assert translation.sql == ""
    assert "declined" in (translation.rejection_reason or "")


def test_rejected_output_is_discarded_not_returned():
    client = StubClient("CREATE OR REPLACE VIEW prod_gcp.sales.v_orders AS SELECT * FROM ghost.a.b")
    assistant = Assistant(rewriter=make_rewriter(), client=client)
    translation = assistant.translate_view(
        "prod_gcp.sales.v_orders",
        "SELECT * FROM delta.`abfss://other@legacy.dfs.core.windows.net/x`",
        ALLOWED,
    )
    assert not translation.accepted
    assert translation.sql == ""


def test_every_call_is_recorded_for_audit():
    client = StubClient(
        "CREATE OR REPLACE VIEW prod_gcp.sales.v_orders AS SELECT * FROM prod_gcp.sales.orders"
    )
    assistant = Assistant(rewriter=make_rewriter(), client=client)
    translation = assistant.translate_view(
        "prod_gcp.sales.v_orders",
        "SELECT * FROM delta.`abfss://other@legacy.dfs.core.windows.net/x` -- 'literal'",
        ALLOWED,
    )
    assert translation.accepted
    assert translation.prompt_version == PROMPT_VERSION
    assert assistant.calls[0]["model"] == "stub"
    assert assistant.calls[0]["accepted"] is True
