"""
Deterministic Replay Sandbox for DataRace.
Executes transactions under controlled schedules and verifies post-execution invariants.
"""

import sqlite3
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple, Any
from datarace.core.models import (
    Transaction,
    Schedule,
    AnomalyReport,
    AnomalyType,
    OpType,
    ConflictEdge
)
from datarace.replay.barrier_controller import BarrierController
from datarace.invariants.engine import InvariantEngine


class ReplaySandbox:
    """
    Executes transactions inside isolated database connections according to a candidate Schedule.
    """

    def __init__(
        self,
        setup_fn: Callable[[sqlite3.Connection], None],
        transactions: List[Transaction],
        invariants: InvariantEngine
    ):
        self.setup_fn = setup_fn
        self.transactions = {tx.tx_id: tx for tx in transactions}
        self.invariants = invariants

    def replay_schedule(self, schedule: Schedule, db_path: str = ":memory:") -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Replays the schedule across concurrent threads.
        Returns:
            (has_anomaly: bool, failed_invariants: List[str], execution_metadata: Dict)
        """
        controller = BarrierController(schedule, timeout_sec=0.5)
        
        is_shared_uri = False
        if db_path == ":memory:":
            db_uri = f"file:memdb_{time.time_ns()}?mode=memory&cache=shared"
            is_shared_uri = True
        else:
            db_uri = db_path

        init_conn = sqlite3.connect(db_uri, uri=is_shared_uri, check_same_thread=False, autocommit=True)
        try:
            self.setup_fn(init_conn)
        finally:
            pass

        thread_errors = []
        threads = []

        # Precompute the assigned schedule step indices for each transaction
        tx_steps: Dict[str, List[Tuple[int, int]]] = {tid: [] for tid in self.transactions}
        for global_step_idx, (tid, op_idx) in enumerate(schedule.steps):
            if tid in tx_steps:
                tx_steps[tid].append((global_step_idx, op_idx))

        def worker(tx_id: str, tx: Transaction, steps_to_run: List[Tuple[int, int]]):
            try:
                conn = sqlite3.connect(db_uri, uri=is_shared_uri, check_same_thread=False, isolation_level=None)
                cursor = conn.cursor()

                for global_step_idx, op_idx in steps_to_run:
                    if op_idx >= len(tx.operations):
                        continue

                    op = tx.operations[op_idx]

                    # Block until scheduler permits this exact global step
                    permitted = controller.wait_for_step(global_step_idx)
                    if not permitted:
                        conn.close()
                        return

                    # Execute operation
                    try:
                        if op.op_type == OpType.BEGIN:
                            cursor.execute("BEGIN;")
                        elif op.op_type == OpType.COMMIT:
                            cursor.execute("COMMIT;")
                        elif op.op_type == OpType.ABORT:
                            cursor.execute("ROLLBACK;")
                        elif op.sql:
                            cursor.execute(op.sql, op.params or {})
                    except Exception as sql_err:
                        pass  # Record lock/conflict errors if any

                    # Notify scheduler that step is complete
                    controller.mark_step_done(tx_id, op_idx)

                conn.close()
            except Exception as e:
                thread_errors.append((tx_id, str(e)))
                controller.abort()

        # Launch worker thread for each transaction that has steps in the schedule
        for tx_id, tx in self.transactions.items():
            steps = tx_steps.get(tx_id, [])
            if steps:
                t = threading.Thread(target=worker, args=(tx_id, tx, steps))
                threads.append(t)
                t.start()

        for t in threads:
            t.join(timeout=2.0)

        # Check invariants post-replay
        eval_conn = sqlite3.connect(db_uri, uri=is_shared_uri, check_same_thread=False)
        failed_invariants = []
        inv_results = self.invariants.check_all(db_connection=eval_conn)
        for name, passed, exp, act in inv_results:
            if not passed:
                failed_invariants.append(f"{name} (Expected: {exp}, Got: {act})")

        eval_conn.close()
        init_conn.close()

        has_anomaly = len(failed_invariants) > 0 or len(thread_errors) > 0
        metadata = {
            "schedule_id": schedule.schedule_id,
            "steps_executed": len(controller.execution_log),
            "completed": controller.completed,
            "aborted": controller.aborted,
            "errors": thread_errors,
            "invariant_results": inv_results
        }
        return has_anomaly, failed_invariants, metadata
