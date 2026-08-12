from __future__ import annotations

import os

from dbxmig.state import STATUS_DONE, STATUS_FAILED, Journal, resume_filter


def test_completed_steps_survive_a_reopen(tmp_path):
    path = str(tmp_path / "journal.jsonl")
    first = Journal(path=path)
    first.record("sql:00001", STATUS_DONE, statement="CREATE CATALOG a")
    first.record("sql:00002", STATUS_FAILED, statement="CREATE SCHEMA b", error="boom")

    reopened = Journal(path=path)
    assert reopened.completed() == {"sql:00001"}
    assert [e.step_id for e in reopened.failures()] == ["sql:00002"]


def test_a_retry_that_succeeds_supersedes_the_failure(tmp_path):
    path = str(tmp_path / "journal.jsonl")
    journal = Journal(path=path)
    journal.record("sql:00001", STATUS_FAILED, error="transient")
    journal.record("sql:00001", STATUS_DONE)
    assert journal.completed() == {"sql:00001"}
    assert journal.failures() == []


def test_a_later_failure_supersedes_an_earlier_success(tmp_path):
    journal = Journal(path=str(tmp_path / "j.jsonl"))
    journal.record("sql:1", STATUS_DONE)
    journal.record("sql:1", STATUS_FAILED, error="rolled back")
    assert journal.completed() == set()


def test_resume_filter_skips_done_steps(tmp_path):
    journal = Journal(path=str(tmp_path / "j.jsonl"))
    journal.record("a", STATUS_DONE)
    keep = resume_filter(journal)
    assert not keep("a")
    assert keep("b")


def test_no_journal_means_run_everything():
    keep = resume_filter(None)
    assert keep("anything")


def test_truncated_final_line_is_tolerated(tmp_path):
    path = str(tmp_path / "j.jsonl")
    journal = Journal(path=path)
    journal.record("a", STATUS_DONE)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write('{"step_id": "b", "sta')  # killed mid-write
    assert Journal(path=path).completed() == {"a"}


def test_journal_creates_its_directory(tmp_path):
    path = str(tmp_path / "nested" / "dir" / "j.jsonl")
    Journal(path=path).record("a", STATUS_DONE)
    assert os.path.exists(path)


def test_stats_counts_the_last_status_per_step(tmp_path):
    journal = Journal(path=str(tmp_path / "j.jsonl"))
    journal.record("a", STATUS_DONE)
    journal.record("b", STATUS_FAILED)
    journal.record("b", STATUS_DONE)
    assert journal.stats() == {STATUS_DONE: 2}
