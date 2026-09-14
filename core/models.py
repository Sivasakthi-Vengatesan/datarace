"""
DataRace Core Data Models & Mathematical Formalisms.
Defines Transactions, Operations, Read/Write sets, Schedules, Conflict Dependencies, and Anomalies.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import json
import time


class OpType(str, Enum):
    BEGIN = "BEGIN"
    COMMIT = "COMMIT"
    ABORT = "ABORT"
    READ = "READ"
    WRITE = "WRITE"
    LOCK = "LOCK"


class IsolationLevel(str, Enum):
    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


class DependencyType(str, Enum):
    WW = "WW"  # Write-Write: Ti writes version, Tj overwrites
    WR = "WR"  # Write-Read: Ti writes version, Tj reads it (data dependency)
    RW = "RW"  # Read-Write: Ti reads version, Tj overwrites it (anti-dependency)


class AnomalyType(str, Enum):
    LOST_UPDATE = "LOST_UPDATE"                # G0 / P4
    DIRTY_READ = "DIRTY_READ"                  # G1a / P1
    NON_REPEATABLE_READ = "NON_REPEATABLE_READ"  # P2
    INCONSISTENT_READ = "INCONSISTENT_READ"    # G1c
    WRITE_SKEW = "WRITE_SKEW"                  # G2 / A5B
    PHANTOM_READ = "PHANTOM_READ"              # P3 / A3
    DEADLOCK = "DEADLOCK"
    INVARIANT_VIOLATION = "INVARIANT_VIOLATION"


@dataclass
class Operation:
    op_id: str
    tx_id: str
    op_type: OpType
    table: Optional[str] = None
    columns: List[str] = field(default_factory=list)
    keys: List[str] = field(default_factory=list)  # e.g., ["users:42", "balance"]
    sql: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    line_number: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op_id": self.op_id,
            "tx_id": self.tx_id,
            "op_type": self.op_type.value,
            "table": self.table,
            "columns": self.columns,
            "keys": self.keys,
            "sql": self.sql,
            "params": self.params,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


@dataclass
class Transaction:
    tx_id: str
    name: str = ""
    isolation_level: IsolationLevel = IsolationLevel.READ_COMMITTED
    operations: List[Operation] = field(default_factory=list)
    status: str = "PENDING"  # PENDING, COMMITTED, ABORTED
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def read_set(self) -> Set[str]:
        keys = set()
        for op in self.operations:
            if op.op_type == OpType.READ:
                keys.update(op.keys)
        return keys

    @property
    def write_set(self) -> Set[str]:
        keys = set()
        for op in self.operations:
            if op.op_type == OpType.WRITE:
                keys.update(op.keys)
        return keys

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tx_id": self.tx_id,
            "name": self.name,
            "isolation_level": self.isolation_level.value,
            "operations": [op.to_dict() for op in self.operations],
            "status": self.status,
            "read_set": list(self.read_set),
            "write_set": list(self.write_set)
        }


@dataclass
class ConflictEdge:
    source_tx: str
    target_tx: str
    source_op_id: str
    target_op_id: str
    dep_type: DependencyType
    item_key: str
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_tx": self.source_tx,
            "target_tx": self.target_tx,
            "source_op_id": self.source_op_id,
            "target_op_id": self.target_op_id,
            "dep_type": self.dep_type.value,
            "item_key": self.item_key,
            "description": self.description
        }


@dataclass
class Schedule:
    schedule_id: str
    steps: List[Tuple[str, int]]  # List of (tx_id, operation_index_in_tx)
    preemption_points: int = 0
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "steps": self.steps,
            "preemption_points": self.preemption_points,
            "description": self.description
        }


@dataclass
class AnomalyReport:
    anomaly_type: AnomalyType
    title: str
    description: str
    involved_transactions: List[str]
    conflicting_keys: List[str]
    conflict_edges: List[ConflictEdge]
    counterexample_schedule: Schedule
    minimal_schedule: Optional[Schedule] = None
    invariant_name: Optional[str] = None
    expected_state: Optional[str] = None
    actual_state: Optional[str] = None
    reproduced: bool = False
    suggested_fix: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly_type": self.anomaly_type.value,
            "title": self.title,
            "description": self.description,
            "involved_transactions": self.involved_transactions,
            "conflicting_keys": self.conflicting_keys,
            "conflict_edges": [e.to_dict() for e in self.conflict_edges],
            "counterexample_schedule": self.counterexample_schedule.to_dict(),
            "minimal_schedule": self.minimal_schedule.to_dict() if self.minimal_schedule else None,
            "invariant_name": self.invariant_name,
            "expected_state": self.expected_state,
            "actual_state": self.actual_state,
            "reproduced": self.reproduced,
            "suggested_fix": self.suggested_fix
        }
