"""
Direct Serialization Graph (DSG) & Adya Dependency Analyzer for DataRace.
Constructs conflict graphs (WW, WR, RW edges), detects cycles, and classifies isolation anomalies.
"""

from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
from datarace.core.models import (
    Transaction,
    Operation,
    OpType,
    DependencyType,
    ConflictEdge,
    AnomalyType,
    Schedule
)


class ConflictGraph:
    """
    Constructs and analyzes the Direct Serialization Graph (DSG) across transactions.
    Identifies Adya anomalies: G0 (Lost Update), G1 (Inconsistent Read), G2 (Write Skew).
    """

    def __init__(self, transactions: List[Transaction]):
        self.transactions: Dict[str, Transaction] = {tx.tx_id: tx for tx in transactions}
        self.edges: List[ConflictEdge] = []
        self.adjacency: Dict[str, List[ConflictEdge]] = defaultdict(list)
        self._build_graph()

    def _keys_overlap(self, keys1: List[str], keys2: List[str]) -> Tuple[bool, str]:
        """Checks if two operation key sets refer to the same database row/entity."""
        s1 = set(keys1)
        s2 = set(keys2)
        common = s1.intersection(s2)
        if common:
            return True, next(iter(common))

        # Check wildcard/table-level overlap
        for k1 in s1:
            for k2 in s2:
                parts1 = k1.split(":")
                parts2 = k2.split(":")
                if parts1[0] == parts2[0]:  # same table
                    if "*" in k1 or "*" in k2 or "insert" in k1 or "insert" in k2:
                        return True, f"{parts1[0]}:wildcard"
        return False, ""

    def _build_graph(self):
        tx_list = list(self.transactions.values())
        n = len(tx_list)

        for i in range(n):
            t1 = tx_list[i]
            for j in range(n):
                if i == j:
                    continue
                t2 = tx_list[j]

                # Compare operations between t1 and t2
                for op1 in t1.operations:
                    if op1.op_type in [OpType.BEGIN, OpType.COMMIT, OpType.ABORT]:
                        continue

                    for op2 in t2.operations:
                        if op2.op_type in [OpType.BEGIN, OpType.COMMIT, OpType.ABORT]:
                            continue

                        overlap, item_key = self._keys_overlap(op1.keys, op2.keys)
                        if not overlap:
                            continue

                        # 1. Write-Write (WW) Dependency
                        if op1.op_type == OpType.WRITE and op2.op_type == OpType.WRITE:
                            edge = ConflictEdge(
                                source_tx=t1.tx_id,
                                target_tx=t2.tx_id,
                                source_op_id=op1.op_id,
                                target_op_id=op2.op_id,
                                dep_type=DependencyType.WW,
                                item_key=item_key,
                                description=f"{t1.tx_id} writes {item_key}, {t2.tx_id} overwrites {item_key}"
                            )
                            self._add_edge(edge)

                        # 2. Write-Read (WR) Data Dependency
                        elif op1.op_type == OpType.WRITE and op2.op_type in [OpType.READ, OpType.LOCK]:
                            edge = ConflictEdge(
                                source_tx=t1.tx_id,
                                target_tx=t2.tx_id,
                                source_op_id=op1.op_id,
                                target_op_id=op2.op_id,
                                dep_type=DependencyType.WR,
                                item_key=item_key,
                                description=f"{t1.tx_id} writes {item_key}, {t2.tx_id} reads {item_key}"
                            )
                            self._add_edge(edge)

                        # 3. Read-Write (RW) Anti-Dependency
                        elif op1.op_type in [OpType.READ, OpType.LOCK] and op2.op_type == OpType.WRITE:
                            edge = ConflictEdge(
                                source_tx=t1.tx_id,
                                target_tx=t2.tx_id,
                                source_op_id=op1.op_id,
                                target_op_id=op2.op_id,
                                dep_type=DependencyType.RW,
                                item_key=item_key,
                                description=f"{t1.tx_id} reads {item_key}, {t2.tx_id} overwrites {item_key}"
                            )
                            self._add_edge(edge)

    def _add_edge(self, edge: ConflictEdge):
        # Prevent duplicate identical edges
        for existing in self.edges:
            if (existing.source_tx == edge.source_tx and
                existing.target_tx == edge.target_tx and
                existing.dep_type == edge.dep_type and
                existing.item_key == edge.item_key):
                return
        self.edges.append(edge)
        self.adjacency[edge.source_tx].append(edge)

    def find_cycles(self) -> List[List[ConflictEdge]]:
        """Finds all elementary cycles in the Direct Serialization Graph using DFS."""
        cycles: List[List[ConflictEdge]] = []
        visited = set()
        rec_stack = []

        def dfs(current_tx: str, path: List[ConflictEdge]):
            rec_stack.append(current_tx)
            for edge in self.adjacency.get(current_tx, []):
                target = edge.target_tx
                if target in rec_stack:
                    # Cycle detected
                    cycle_start_idx = rec_stack.index(target)
                    cycle_txs = rec_stack[cycle_start_idx:]
                    # Extract edges corresponding to this cycle
                    cycle_edges = []
                    sub_path = path + [edge]
                    for idx, t in enumerate(cycle_txs):
                        next_t = cycle_txs[(idx + 1) % len(cycle_txs)]
                        for e in sub_path:
                            if e.source_tx == t and e.target_tx == next_t:
                                cycle_edges.append(e)
                                break
                    if cycle_edges and len(cycle_edges) == len(cycle_txs):
                        # Avoid duplicates
                        edge_keys = tuple(sorted((e.source_tx, e.target_tx, e.dep_type) for e in cycle_edges))
                        if edge_keys not in visited:
                            visited.add(edge_keys)
                            cycles.append(cycle_edges)
                elif target not in rec_stack:
                    dfs(target, path + [edge])

            rec_stack.pop()

        for tx_id in self.transactions:
            dfs(tx_id, [])

        return cycles

    def classify_cycle_anomaly(self, cycle: List[ConflictEdge]) -> Tuple[AnomalyType, str, str]:
        """
        Classifies the exact isolation anomaly represented by a DSG cycle.
        """
        dep_types = [e.dep_type for e in cycle]
        rw_count = dep_types.count(DependencyType.RW)
        ww_count = dep_types.count(DependencyType.WW)
        wr_count = dep_types.count(DependencyType.WR)
        keys_in_cycle = {e.item_key for e in cycle}

        # If all edges in cycle touch the exact same item key and involve R/W or W/W
        if len(keys_in_cycle) == 1 and (ww_count >= 1 or rw_count >= 1):
            return (
                AnomalyType.LOST_UPDATE,
                "Lost Update Anomaly (G0 / P4)",
                "Concurrent transactions read the same initial entity and overwrite each other's updates without row locks."
            )
        elif rw_count >= 2 and len(keys_in_cycle) > 1:
            return (
                AnomalyType.WRITE_SKEW,
                "Write Skew Anomaly (G2 / A5B)",
                "Concurrent transactions read overlapping state and perform disjoint writes that jointly violate global invariants (Snapshot Isolation anomaly)."
            )
        elif rw_count >= 1 and ww_count >= 1:
            return (
                AnomalyType.LOST_UPDATE,
                "Lost Update Anomaly (G0 / P4)",
                "Concurrent transactions perform conflicting read-modify-writes on the same database rows."
            )
        elif wr_count >= 1 and rw_count >= 1:
            return (
                AnomalyType.INCONSISTENT_READ,
                "Inconsistent / Non-Repeatable Read (G1c / P2)",
                "Transaction observes intermediate state resulting in a circular dependency flow."
            )
        elif ww_count >= 2:
            return (
                AnomalyType.LOST_UPDATE,
                "Write-Write Conflict Cycle (G0)",
                "Direct write conflict cycle violating strict serial ordering."
            )
        else:
            return (
                AnomalyType.INVARIANT_VIOLATION,
                "Serialization Cycle Anomaly",
                "Cycle detected in Direct Serialization Graph violating Serializability (SER)."
            )
