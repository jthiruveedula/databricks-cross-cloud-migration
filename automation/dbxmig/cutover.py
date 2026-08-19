"""Cutover-night drain gate.

``execution/cutover.mdx`` step 3 states the rule in prose: after pausing
source jobs, poll the Jobs API's ``active_only=true`` filter and do not
proceed to the final sync until it returns zero across every job -- or the
drain hits a hard timeout, in which case treat it as a no-go, not a "close
enough". Proceeding to final sync while a job is still running is the exact
split-brain precondition [rollback](/execution/rollback) exists to guard
against: the sync captures a state the workspace is still mutating
underneath it.

This module is that check, made runnable instead of prose. It is read-only
by design -- it answers "is it safe to proceed", it does not pause jobs or
touch data itself. Pausing schedules (cutover step 2) is a separate, mutating
action and is not automated here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

# Jobs API lifecycle states that mean "still active" -- mirrors the set
# ``active_only=true`` itself filters to, kept explicit here so the drain
# check doesn't silently change behavior if the SDK's filter semantics ever
# shift under us.
ACTIVE_LIFECYCLE_STATES = frozenset(
    {"PENDING", "RUNNING", "TERMINATING", "QUEUED", "BLOCKED", "WAITING_FOR_RETRY"}
)

#: Every life cycle state the Jobs API enum defines. A run in one of these
#: minus ``ACTIVE_LIFECYCLE_STATES`` is definitely finished, even though
#: ``active_only=True`` should never have returned it in the first place --
#: that mismatch is exactly the semantics shift the check above guards
#: against. A state in neither set (``UNKNOWN``, or a future addition to the
#: enum this toolkit hasn't seen yet) is treated as active: fail safe means
#: blocking the drain gate on an unrecognized state, not clearing it.
_TERMINAL_LIFECYCLE_STATES = (
    frozenset({"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}) - ACTIVE_LIFECYCLE_STATES
)


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    return getattr(obj, name, default)


@dataclass(frozen=True)
class ActiveRun:
    run_id: int
    job_id: Optional[int]
    run_name: str
    state: str


@dataclass
class DrainStatus:
    active_runs: List[ActiveRun] = field(default_factory=list)

    @property
    def drained(self) -> bool:
        return not self.active_runs

    def summary(self) -> str:
        if self.drained:
            return "drained: zero active runs"
        names = sorted({r.run_name or "job {0}".format(r.job_id) for r in self.active_runs})
        return "{0} active run(s) blocking drain: {1}".format(
            len(self.active_runs), ", ".join(names)
        )


def active_job_runs(client: Any) -> List[ActiveRun]:
    """List every run still in an active lifecycle state.

    ``client`` is a ``databricks.sdk.WorkspaceClient`` (or a stub of the same
    shape, for tests) -- pass a live ``DatabricksGateway``'s ``.client``.
    Uses ``jobs.list_runs(active_only=True)`` directly, matching the exact
    filter [cutover](/execution/cutover) documents, rather than listing every
    run and filtering client-side.
    """
    runs: List[ActiveRun] = []
    for run in client.jobs.list_runs(active_only=True, expand_tasks=False):
        status = _attr(run, "status") or _attr(run, "state")
        life_cycle = _attr(status, "state") or _attr(status, "life_cycle_state") or status
        state = str(_attr(life_cycle, "value", life_cycle) or "UNKNOWN").upper()
        # Re-check against the known terminal states instead of trusting
        # active_only=True alone. A state this toolkit doesn't recognize at
        # all is kept (fail safe: block the drain gate), not dropped.
        if state in _TERMINAL_LIFECYCLE_STATES:
            continue
        runs.append(
            ActiveRun(
                run_id=int(_attr(run, "run_id", 0) or 0),
                job_id=_attr(run, "job_id"),
                run_name=str(_attr(run, "run_name", "") or ""),
                state=state,
            )
        )
    return runs


def check_drain(client: Any) -> DrainStatus:
    """One poll of the drain gate. Callers own the retry/timeout loop.

    Kept as a single poll rather than a built-in retry loop so it can be
    tested without a clock, and so the CLI's timeout/no-go behavior lives in
    one place (``dbxmig cutover-drain``) instead of being duplicated by every
    caller that wants to check drain state.
    """
    return DrainStatus(active_runs=active_job_runs(client))
