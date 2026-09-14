"""
DataRace Command Line Interface (CLI).
Provides developer commands for tracing, conflict analysis, DPOR schedule exploration, deterministic replay, and benchmark evaluation.
"""

import sys
from pathlib import Path

# Ensure root directory and parent are in sys.path
root_dir = Path(__file__).resolve().parent.parent
for p in [str(root_dir), str(root_dir.parent)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import argparse
import json
import time
from typing import List, Dict, Any, Optional
from datarace.core.models import (
    Transaction,
    Schedule,
    AnomalyReport,
    AnomalyType
)
from datarace.analyzer.conflict_graph import ConflictGraph
from datarace.scheduler.dpor import DPOScheduler
from datarace.replay.sandbox import ReplaySandbox
from datarace.reducer.delta_debugger import DeltaDebugger
from datarace.benchmarks.suite import get_all_benchmarks


def format_box(title: str, content: List[str]) -> str:
    width = 76
    top = "┌" + "─" * (width - 2) + "┐"
    title_line = f"│ {title.center(width - 4)} │"
    div = "├" + "─" * (width - 2) + "┤"
    bot = "└" + "─" * (width - 2) + "┘"
    lines = [top, title_line, div]
    for c in content:
        for sub in c.split("\n"):
            lines.append(f"│ {sub.ljust(width - 4)[:width - 4]} │")
    lines.append(bot)
    return "\n".join(lines)


def cmd_benchmark(args):
    benchmarks = get_all_benchmarks()
    print("\n" + "=" * 80)
    print(" DATARACE CONCURRENCY ENGINE — BENCHMARK EVALUATION SUITE")
    print("=" * 80)
    print(f"Running {len(benchmarks)} canonical concurrency test cases...\n")

    results = []
    start_total = time.time()

    for idx, (b_id, bench) in enumerate(benchmarks.items(), 1):
        txs = bench.transactions_fn()
        graph = ConflictGraph(txs)
        cycles = graph.find_cycles()
        scheduler = DPOScheduler(txs)
        schedules = scheduler.generate_schedules()

        sandbox = ReplaySandbox(bench.setup_db, txs, bench.invariants)
        
        found_bug = False
        failing_sched = None
        reproduced_invariants = []

        t0 = time.time()
        for sched in schedules:
            has_anomaly, failed_invs, meta = sandbox.replay_schedule(sched)
            if has_anomaly and failed_invs:
                found_bug = True
                failing_sched = sched
                reproduced_invariants = failed_invs
                break
        t_elapsed = (time.time() - t0) * 1000

        # Minimize counterexample
        min_steps = len(failing_sched.steps) if failing_sched else 0
        if found_bug and failing_sched:
            reducer = DeltaDebugger(sandbox)
            min_sched = reducer.minimize_schedule(failing_sched)
            min_steps = len(min_sched.steps)

        status = "[BUG FOUND]" if found_bug else "[NO BUG]"
        print(f"[{idx:02d}/10] {bench.title.ljust(44)} -> {status} in {t_elapsed:.1f}ms (Min steps: {min_steps})")
        results.append({
            "id": b_id,
            "title": bench.title,
            "category": bench.category,
            "found_bug": found_bug,
            "cycles_detected": len(cycles),
            "schedules_explored": len(schedules),
            "min_steps": min_steps,
            "time_ms": t_elapsed
        })

    print("-" * 80)
    total_time = time.time() - start_total
    passed_bugs = sum(1 for r in results if r["found_bug"])
    print(f"SUMMARY: {passed_bugs}/{len(benchmarks)} real-world concurrency bugs deterministically discovered & reproduced in {total_time:.2f}s.")
    print("=" * 80 + "\n")


def cmd_explore(args):
    benchmarks = get_all_benchmarks()
    target_id = args.benchmark_id
    if target_id not in benchmarks:
        print(f"Error: Benchmark '{target_id}' not found. Available: {list(benchmarks.keys())}")
        return

    bench = benchmarks[target_id]
    txs = bench.transactions_fn()

    print(f"\nAnalyzing Benchmark: {bench.title} ({bench.category})")
    print(f"Description: {bench.description}\n")

    # Step 1: Conflict Graph
    graph = ConflictGraph(txs)
    print(f"1. Direct Serialization Graph (DSG):")
    print(f"   - Transactions: {len(txs)}")
    print(f"   - Conflict Edges ({len(graph.edges)}):")
    for e in graph.edges:
        print(f"     * [{e.dep_type.value}] {e.source_tx} -> {e.target_tx} on key '{e.item_key}'")

    cycles = graph.find_cycles()
    print(f"   - Cycles Detected: {len(cycles)}")
    for c in cycles:
        atype, atitle, adesc = graph.classify_cycle_anomaly(c)
        print(f"     ! {atitle}: {adesc}")

    # Step 2: DPOR Scheduler
    scheduler = DPOScheduler(txs)
    schedules = scheduler.generate_schedules()
    print(f"\n2. Conflict-Directed DPOR Schedule Generation:")
    print(f"   - Generated {len(schedules)} prioritized schedules (avoided exponential explosion).")

    # Step 3: Deterministic Replay Sandbox
    sandbox = ReplaySandbox(bench.setup_db, txs, bench.invariants)
    found_bug = False
    failing_sched = None
    failed_invs = []

    for sched in schedules:
        has_anomaly, inv_fails, meta = sandbox.replay_schedule(sched)
        if has_anomaly and inv_fails:
            found_bug = True
            failing_sched = sched
            failed_invs = inv_fails
            break

    if found_bug and failing_sched:
        print(f"\n3. Deterministic Replay Result: REPRODUCED!")
        print(f"   - Dangerous Interleaving: {failing_sched.description}")
        print(f"   - Invariant Violations:")
        for inv in failed_invs:
            print(f"     * {inv}")

        # Step 4: Minimization
        reducer = DeltaDebugger(sandbox)
        min_sched = reducer.minimize_schedule(failing_sched)
        print(f"\n4. Minimal Counterexample (Delta Debugging ddmin):")
        print(f"   - Reduced from {len(failing_sched.steps)} to {len(min_sched.steps)} operations:")
        for tid, op_idx in min_sched.steps:
            tx = sandbox.transactions[tid]
            op = tx.operations[op_idx]
            print(f"     {tid}.{op.op_type.value.ljust(6)} -> {op.sql}")

        print(f"\n5. Suggested Remediation:")
        print(f"   {bench.suggested_fix}\n")
    else:
        print("\n3. Replay Result: No invariant violations triggered.")


def main():
    parser = argparse.ArgumentParser(description="DataRace — Database Concurrency Bug Discovery Engine")
    subparsers = parser.add_subparsers(dest="command")

    # benchmark
    p_bench = subparsers.add_parser("benchmark", help="Run all 10 canonical concurrency benchmarks")

    # explore
    p_exp = subparsers.add_parser("explore", help="Explore conflict graphs and schedules for a specific case")
    p_exp.add_argument("benchmark_id", nargs="?", default="01_banking_lost_update", help="Benchmark ID to analyze")

    args = parser.parse_args()

    if args.command == "benchmark":
        cmd_benchmark(args)
    elif args.command == "explore":
        cmd_explore(args)
    else:
        # Default run benchmark
        cmd_benchmark(args)


if __name__ == "__main__":
    main()
