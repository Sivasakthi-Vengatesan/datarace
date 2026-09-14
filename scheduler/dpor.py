"""
Conflict-Directed Dynamic Partial-Order Reduction (DPOR) & Bounded Schedule Generator.
Explores transaction interleavings targeted at reversing conflicting operations without combinatorial explosion.
"""

from typing import List, Dict, Tuple, Set, Optional
import itertools
import uuid
from datarace.core.models import (
    Transaction,
    Operation,
    OpType,
    Schedule
)
from datarace.analyzer.conflict_graph import ConflictGraph


class DPOScheduler:
    """
    Explores candidate schedules using Conflict-Directed Dynamic Partial Order Reduction.
    Prioritizes preemption points at read/write conflict boundaries.
    """

    def __init__(self, transactions: List[Transaction], max_preemptions: int = 2):
        self.transactions: Dict[str, Transaction] = {tx.tx_id: tx for tx in transactions}
        self.max_preemptions = max_preemptions
        self.conflict_graph = ConflictGraph(transactions)

    def generate_schedules(self) -> List[Schedule]:
        """
        Generates prioritized set of schedules:
        1. Serial baselines (T1 then T2, T2 then T1).
        2. Conflict-directed interleavings reversing critical R/W operation pairs.
        3. Bounded preemption permutations.
        """
        schedules: List[Schedule] = []
        seen_signatures: Set[str] = set()

        # 1. Serial schedules
        tx_ids = list(self.transactions.keys())
        for perm in itertools.permutations(tx_ids):
            steps = []
            for tid in perm:
                tx = self.transactions[tid]
                for op_idx in range(len(tx.operations)):
                    steps.append((tid, op_idx))
            sig = self._schedule_signature(steps)
            if sig not in seen_signatures:
                seen_signatures.add(sig)
                schedules.append(Schedule(
                    schedule_id=f"sched_serial_{len(schedules)+1}",
                    steps=steps,
                    preemption_points=0,
                    description=f"Serial execution: {' -> '.join(perm)}"
                ))

        # 2. Conflict-directed interleavings
        # For each pair of transactions that have a conflict edge:
        for edge in self.conflict_graph.edges:
            t1 = self.transactions.get(edge.source_tx)
            t2 = self.transactions.get(edge.target_tx)
            if not t1 or not t2 or t1.tx_id == t2.tx_id:
                continue

            # Find op indices
            op1_idx = next((i for i, op in enumerate(t1.operations) if op.op_id == edge.source_op_id), -1)
            op2_idx = next((i for i, op in enumerate(t2.operations) if op.op_id == edge.target_op_id), -1)

            if op1_idx != -1 and op2_idx != -1:
                # Interleaving 1: T1 up to op1 -> T2 up to op2 -> T1 finish -> T2 finish
                sched1 = self._build_interleaved_schedule(t1, t2, op1_idx, op2_idx)
                sig1 = self._schedule_signature(sched1.steps)
                if sig1 not in seen_signatures:
                    seen_signatures.add(sig1)
                    schedules.append(sched1)

                # Interleaving 2: T2 up to op2 -> T1 up to op1 -> T2 finish -> T1 finish
                sched2 = self._build_interleaved_schedule(t2, t1, op2_idx, op1_idx)
                sig2 = self._schedule_signature(sched2.steps)
                if sig2 not in seen_signatures:
                    seen_signatures.add(sig2)
                    schedules.append(sched2)

                # Classical Read-Modify-Write Interleaving:
                # T1.read -> T2.read -> T1.write -> T2.write
                sched_rmw = self._build_rmw_interleaved_schedule(t1, t2)
                if sched_rmw:
                    sig_rmw = self._schedule_signature(sched_rmw.steps)
                    if sig_rmw not in seen_signatures:
                        seen_signatures.add(sig_rmw)
                        schedules.append(sched_rmw)

        return schedules

    def _build_interleaved_schedule(
        self,
        t1: Transaction,
        t2: Transaction,
        t1_split: int,
        t2_split: int
    ) -> Schedule:
        steps: List[Tuple[str, int]] = []

        # T1 up to split
        for i in range(0, t1_split + 1):
            steps.append((t1.tx_id, i))

        # T2 up to split
        for j in range(0, t2_split + 1):
            steps.append((t2.tx_id, j))

        # T1 remaining
        for i in range(t1_split + 1, len(t1.operations)):
            steps.append((t1.tx_id, i))

        # T2 remaining
        for j in range(t2_split + 1, len(t2.operations)):
            steps.append((t2.tx_id, j))

        # Other transactions appended
        for tid, tx in self.transactions.items():
            if tid not in [t1.tx_id, t2.tx_id]:
                for k in range(len(tx.operations)):
                    steps.append((tid, k))

        preemptions = self._count_preemptions(steps)
        return Schedule(
            schedule_id=f"sched_dpor_{uuid.uuid4().hex[:5]}",
            steps=steps,
            preemption_points=preemptions,
            description=f"Conflict-directed interleaving: {t1.tx_id} (op 0..{t1_split}) -> {t2.tx_id} (op 0..{t2_split}) -> {t1.tx_id} rest -> {t2.tx_id} rest"
        )

    def _build_rmw_interleaved_schedule(self, t1: Transaction, t2: Transaction) -> Optional[Schedule]:
        """Builds fine-grained interleaved Read-Read-Write-Write schedule."""
        t1_reads = [i for i, op in enumerate(t1.operations) if op.op_type in [OpType.READ, OpType.LOCK]]
        t1_writes = [i for i, op in enumerate(t1.operations) if op.op_type == OpType.WRITE]
        t2_reads = [i for i, op in enumerate(t2.operations) if op.op_type in [OpType.READ, OpType.LOCK]]
        t2_writes = [i for i, op in enumerate(t2.operations) if op.op_type == OpType.WRITE]

        if not (t1_reads and t1_writes and t2_reads and t2_writes):
            return None

        steps: List[Tuple[str, int]] = []
        # T1 begin + reads
        t1_first_write = t1_writes[0]
        for i in range(0, t1_first_write):
            steps.append((t1.tx_id, i))

        # T2 begin + reads
        t2_first_write = t2_writes[0]
        for j in range(0, t2_first_write):
            steps.append((t2.tx_id, j))

        # T1 writes + commit
        for i in range(t1_first_write, len(t1.operations)):
            steps.append((t1.tx_id, i))

        # T2 writes + commit
        for j in range(t2_first_write, len(t2.operations)):
            steps.append((t2.tx_id, j))

        preemptions = self._count_preemptions(steps)
        return Schedule(
            schedule_id=f"sched_rmw_{uuid.uuid4().hex[:5]}",
            steps=steps,
            preemption_points=preemptions,
            description=f"Read-Modify-Write Race Interleaving: {t1.tx_id} READ -> {t2.tx_id} READ -> {t1.tx_id} WRITE -> {t2.tx_id} WRITE"
        )

    def _count_preemptions(self, steps: List[Tuple[str, int]]) -> int:
        preemptions = 0
        for i in range(1, len(steps)):
            if steps[i][0] != steps[i - 1][0]:
                preemptions += 1
        return preemptions

    def _schedule_signature(self, steps: List[Tuple[str, int]]) -> str:
        return ",".join(f"{tid}:{idx}" for tid, idx in steps)
