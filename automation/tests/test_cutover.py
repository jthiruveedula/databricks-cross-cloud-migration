from __future__ import annotations

from types import SimpleNamespace

from dbxmig.cutover import active_job_runs, check_drain


class _StubJobsApi:
    def __init__(self, runs):
        self._runs = runs

    def list_runs(self, active_only=True, expand_tasks=False):  # noqa: FBT002 - mirrors SDK signature
        assert active_only is True
        return list(self._runs)


class _StubClient:
    def __init__(self, runs):
        self.jobs = _StubJobsApi(runs)


def _run(run_id, job_id, run_name, state):
    return SimpleNamespace(
        run_id=run_id,
        job_id=job_id,
        run_name=run_name,
        status=SimpleNamespace(state=SimpleNamespace(value=state)),
    )


def test_no_active_runs_means_drained():
    client = _StubClient([])
    status = check_drain(client)
    assert status.drained
    assert status.summary() == "drained: zero active runs"


def test_active_runs_block_drain():
    client = _StubClient([_run(1, 10, "nightly_batch", "RUNNING")])
    status = check_drain(client)
    assert not status.drained
    assert "nightly_batch" in status.summary()
    assert "1 active run(s)" in status.summary()


def test_active_job_runs_reads_lifecycle_state_off_the_status_object():
    client = _StubClient([_run(2, 20, "ingest", "QUEUED")])
    runs = active_job_runs(client)
    assert len(runs) == 1
    assert runs[0].state == "QUEUED"
    assert runs[0].job_id == 20


def test_unnamed_run_falls_back_to_job_id_in_summary():
    client = _StubClient([_run(3, 30, "", "PENDING")])
    status = check_drain(client)
    assert "job 30" in status.summary()


def test_multiple_active_runs_are_deduplicated_by_name_in_summary():
    client = _StubClient(
        [_run(1, 10, "nightly_batch", "RUNNING"), _run(2, 10, "nightly_batch", "RUNNING")]
    )
    status = check_drain(client)
    assert status.summary().count("nightly_batch") == 1
    assert "2 active run(s)" in status.summary()
