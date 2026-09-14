import pytest
from datarace.benchmarks.suite import get_all_benchmarks
from datarace.scheduler.dpor import DPOScheduler
from datarace.replay.sandbox import ReplaySandbox
from datarace.reducer.delta_debugger import DeltaDebugger


def test_delta_debugger_minimization():
    benchmarks = get_all_benchmarks()
    case = benchmarks["01_banking_lost_update"]
    txs = case.transactions_fn()

    scheduler = DPOScheduler(txs)
    schedules = scheduler.generate_schedules()
    sandbox = ReplaySandbox(case.setup_db, txs, case.invariants)

    # Find failing schedule
    failing_sched = None
    for s in schedules:
        has_anomaly, inv_fails, _ = sandbox.replay_schedule(s)
        if has_anomaly and inv_fails:
            failing_sched = s
            break

    assert failing_sched is not None

    reducer = DeltaDebugger(sandbox)
    min_sched = reducer.minimize_schedule(failing_sched)

    assert min_sched is not None
    assert len(min_sched.steps) <= len(failing_sched.steps)

    # Verify that min_sched still triggers invariant failure
    fails, inv_fails, _ = sandbox.replay_schedule(min_sched)
    assert fails
    assert len(inv_fails) > 0
