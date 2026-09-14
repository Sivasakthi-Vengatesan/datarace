import pytest
from datarace.benchmarks.suite import get_all_benchmarks
from datarace.analyzer.conflict_graph import ConflictGraph
from datarace.scheduler.dpor import DPOScheduler
from datarace.replay.sandbox import ReplaySandbox


def test_dpor_schedule_generation():
    benchmarks = get_all_benchmarks()
    case = benchmarks["01_banking_lost_update"]
    txs = case.transactions_fn()

    scheduler = DPOScheduler(txs)
    schedules = scheduler.generate_schedules()

    assert len(schedules) >= 2  # Serial + conflict-directed interleavings
    # Check that at least one schedule has preemption points
    has_interleaved = any(s.preemption_points > 0 for s in schedules)
    assert has_interleaved


def test_all_10_benchmarks_reproduce():
    benchmarks = get_all_benchmarks()
    assert len(benchmarks) == 10

    for b_id, bench in benchmarks.items():
        txs = bench.transactions_fn()
        scheduler = DPOScheduler(txs)
        schedules = scheduler.generate_schedules()
        sandbox = ReplaySandbox(bench.setup_db, txs, bench.invariants)

        found_anomaly = False
        for sched in schedules:
            has_anomaly, inv_fails, _ = sandbox.replay_schedule(sched)
            if has_anomaly and inv_fails:
                found_anomaly = True
                break

        assert found_anomaly, f"Failed to reproduce anomaly in benchmark {b_id}: {bench.title}"
