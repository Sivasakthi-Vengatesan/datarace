"""
Exports full DataRace engine evaluation data to JSON for the Retro 90s Web Workbench.
"""

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent
for p in [str(root_dir), str(root_dir.parent)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import json
from datarace.benchmarks.suite import get_all_benchmarks
from datarace.analyzer.conflict_graph import ConflictGraph
from datarace.scheduler.dpor import DPOScheduler
from datarace.replay.sandbox import ReplaySandbox
from datarace.reducer.delta_debugger import DeltaDebugger


def export_all():
    benchmarks = get_all_benchmarks()
    exported = []

    for b_id, bench in benchmarks.items():
        txs = bench.transactions_fn()
        graph = ConflictGraph(txs)
        cycles = graph.find_cycles()

        classified_cycles = []
        for c in cycles:
            atype, atitle, adesc = graph.classify_cycle_anomaly(c)
            classified_cycles.append({
                "anomaly_type": atype.value,
                "title": atitle,
                "description": adesc,
                "edges": [e.to_dict() for e in c]
            })

        scheduler = DPOScheduler(txs)
        schedules = scheduler.generate_schedules()

        sandbox = ReplaySandbox(bench.setup_db, txs, bench.invariants)

        failing_sched = None
        failed_invs = []
        all_schedule_results = []

        for sched in schedules:
            has_anomaly, inv_fails, meta = sandbox.replay_schedule(sched)
            all_schedule_results.append({
                "schedule_id": sched.schedule_id,
                "description": sched.description,
                "preemption_points": sched.preemption_points,
                "steps": sched.steps,
                "has_anomaly": has_anomaly,
                "failed_invariants": inv_fails,
                "steps_executed": meta["steps_executed"]
            })
            if has_anomaly and inv_fails and not failing_sched:
                failing_sched = sched
                failed_invs = inv_fails

        min_sched_dict = None
        if failing_sched:
            reducer = DeltaDebugger(sandbox)
            min_sched = reducer.minimize_schedule(failing_sched)
            min_sched_dict = min_sched.to_dict()

        # Build timeline operations
        tx_dict = {tx.tx_id: tx.to_dict() for tx in txs}

        exported.append({
            "case_id": bench.case_id,
            "title": bench.title,
            "category": bench.category,
            "description": bench.description,
            "setup_sql": bench.setup_sql,
            "suggested_fix": bench.suggested_fix,
            "transactions": tx_dict,
            "conflict_edges": [e.to_dict() for e in graph.edges],
            "cycles": classified_cycles,
            "schedules": all_schedule_results,
            "failing_schedule": failing_sched.to_dict() if failing_sched else None,
            "minimal_schedule": min_sched_dict,
            "failed_invariants": failed_invs
        })

    out_dir = root_dir / "ui" / "src" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "benchmarksData.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(exported, f, indent=2)

    print(f"Successfully exported {len(exported)} benchmarks to {out_file}")


if __name__ == "__main__":
    export_all()
