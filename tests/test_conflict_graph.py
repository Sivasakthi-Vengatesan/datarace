import pytest
from datarace.core.models import (
    Transaction,
    Operation,
    OpType,
    DependencyType,
    AnomalyType
)
from datarace.analyzer.conflict_graph import ConflictGraph


def test_lost_update_cycle_detection():
    # T1: Read x, Write x
    t1 = Transaction(tx_id="T1")
    t1.operations = [
        Operation("op1_1", "T1", OpType.BEGIN),
        Operation("op1_2", "T1", OpType.READ, table="accounts", keys=["accounts:id=1"]),
        Operation("op1_3", "T1", OpType.WRITE, table="accounts", keys=["accounts:id=1"]),
        Operation("op1_4", "T1", OpType.COMMIT)
    ]

    # T2: Read x, Write x
    t2 = Transaction(tx_id="T2")
    t2.operations = [
        Operation("op2_1", "T2", OpType.BEGIN),
        Operation("op2_2", "T2", OpType.READ, table="accounts", keys=["accounts:id=1"]),
        Operation("op2_3", "T2", OpType.WRITE, table="accounts", keys=["accounts:id=1"]),
        Operation("op2_4", "T2", OpType.COMMIT)
    ]

    graph = ConflictGraph([t1, t2])
    assert len(graph.edges) > 0

    cycles = graph.find_cycles()
    assert len(cycles) > 0

    anomaly_type, title, desc = graph.classify_cycle_anomaly(cycles[0])
    assert anomaly_type == AnomalyType.LOST_UPDATE


def test_disjoint_transactions_no_cycle():
    # T1 touches accounts:id=1, T2 touches accounts:id=2
    t1 = Transaction(tx_id="T1")
    t1.operations = [
        Operation("op1_1", "T1", OpType.READ, keys=["accounts:id=1"]),
        Operation("op1_2", "T1", OpType.WRITE, keys=["accounts:id=1"])
    ]
    t2 = Transaction(tx_id="T2")
    t2.operations = [
        Operation("op2_1", "T2", OpType.READ, keys=["accounts:id=2"]),
        Operation("op2_2", "T2", OpType.WRITE, keys=["accounts:id=2"])
    ]

    graph = ConflictGraph([t1, t2])
    assert len(graph.edges) == 0
    assert len(graph.find_cycles()) == 0
