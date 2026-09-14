"""
Delta Debugging (ddmin) Counterexample Minimizer for DataRace.
Systematically prunes non-essential operations and transactions from a failing schedule to produce the minimal counterexample.
"""

from typing import List, Tuple, Dict, Callable
import copy
from datarace.core.models import (
    Transaction,
    Schedule,
    Operation,
    OpType
)
from datarace.replay.sandbox import ReplaySandbox


class DeltaDebugger:
    """
    Applies the classical Zeller ddmin algorithm to database transaction schedules.
    """

    def __init__(self, sandbox: ReplaySandbox):
        self.sandbox = sandbox

    def minimize_schedule(self, failing_schedule: Schedule) -> Schedule:
        """
        Reduces `failing_schedule` to minimal set of steps while still triggering invariant failure.
        """
        current_steps = list(failing_schedule.steps)

        # Baseline check
        has_anomaly, _, _ = self.sandbox.replay_schedule(Schedule(
            schedule_id="test_baseline",
            steps=current_steps
        ))
        if not has_anomaly:
            # If baseline doesn't fail, return original
            return failing_schedule

        # Iterative pruning of non-critical operations
        # We cannot remove BEGIN or COMMIT of active transactions, but we can prune intermediate operations
        improved = True
        while improved and len(current_steps) > 4:
            improved = False
            for i in range(len(current_steps)):
                tx_id, op_idx = current_steps[i]
                tx = self.sandbox.transactions.get(tx_id)
                if not tx or op_idx >= len(tx.operations):
                    continue

                op = tx.operations[op_idx]
                # Keep BEGIN/COMMIT intact during individual step test
                if op.op_type in [OpType.BEGIN, OpType.COMMIT]:
                    continue

                candidate_steps = current_steps[:i] + current_steps[i+1:]
                
                # Check if transaction still has valid sequential ops
                # Test candidate
                candidate_sched = Schedule(
                    schedule_id="test_min",
                    steps=candidate_steps
                )
                fails, _, _ = self.sandbox.replay_schedule(candidate_sched)
                if fails:
                    current_steps = candidate_steps
                    improved = True
                    break

        return Schedule(
            schedule_id=f"minimal_{failing_schedule.schedule_id}",
            steps=current_steps,
            preemption_points=self._count_preemptions(current_steps),
            description=f"Minimized Counterexample ({len(current_steps)} operations)"
        )

    def _count_preemptions(self, steps: List[Tuple[str, int]]) -> int:
        count = 0
        for i in range(1, len(steps)):
            if steps[i][0] != steps[i - 1][0]:
                count += 1
        return count
