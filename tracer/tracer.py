"""
Transaction Tracer and Hook Collector for DataRace.
Captures thread-local and process-level execution traces with query metadata.
"""

import threading
import time
import uuid
from typing import Dict, List, Optional, Any
from datarace.core.models import Operation, Transaction, OpType, IsolationLevel
from datarace.tracer.sql_parser import SQLParser


class Tracer:
    """Thread-safe transaction trace recorder."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.transactions: Dict[str, Transaction] = {}
        self._thread_local = threading.local()
        self._op_counter = 0
        self._trace_lock = threading.Lock()
        self.enabled = True

    @classmethod
    def get_instance(cls) -> "Tracer":
        with cls._lock:
            if cls._instance is None:
                cls._instance = Tracer()
            return cls._instance

    def clear(self):
        with self._trace_lock:
            self.transactions.clear()
            self._op_counter = 0

    def start_transaction(
        self,
        tx_id: Optional[str] = None,
        name: str = "",
        isolation_level: IsolationLevel = IsolationLevel.READ_COMMITTED
    ) -> Transaction:
        if not tx_id:
            tx_id = f"T_{uuid.uuid4().hex[:6]}"
        tx = Transaction(
            tx_id=tx_id,
            name=name or tx_id,
            isolation_level=isolation_level,
            status="ACTIVE",
            start_time=time.time()
        )
        # Record initial BEGIN op
        begin_op = Operation(
            op_id=f"op_{self._next_op_id()}",
            tx_id=tx_id,
            op_type=OpType.BEGIN,
            sql="BEGIN;"
        )
        tx.operations.append(begin_op)

        with self._trace_lock:
            self.transactions[tx_id] = tx
            self._thread_local.current_tx_id = tx_id
        return tx

    def get_current_tx_id(self) -> Optional[str]:
        return getattr(self._thread_local, "current_tx_id", None)

    def record_query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        tx_id: Optional[str] = None
    ) -> Optional[Operation]:
        if not self.enabled:
            return None

        active_tx_id = tx_id or self.get_current_tx_id()
        if not active_tx_id:
            return None

        op_type, table, cols, keys = SQLParser.parse_statement(sql, params)

        op = Operation(
            op_id=f"op_{self._next_op_id()}",
            tx_id=active_tx_id,
            op_type=op_type,
            table=table,
            columns=cols,
            keys=keys,
            sql=sql,
            params=params or {},
            timestamp=time.time()
        )

        with self._trace_lock:
            if active_tx_id in self.transactions:
                tx = self.transactions[active_tx_id]
                tx.operations.append(op)
                if op_type == OpType.COMMIT:
                    tx.status = "COMMITTED"
                    tx.end_time = time.time()
                elif op_type == OpType.ABORT:
                    tx.status = "ABORTED"
                    tx.end_time = time.time()
        return op

    def commit_transaction(self, tx_id: Optional[str] = None):
        active_tx_id = tx_id or self.get_current_tx_id()
        if active_tx_id:
            self.record_query("COMMIT;", tx_id=active_tx_id)
            if hasattr(self._thread_local, "current_tx_id"):
                self._thread_local.current_tx_id = None

    def rollback_transaction(self, tx_id: Optional[str] = None):
        active_tx_id = tx_id or self.get_current_tx_id()
        if active_tx_id:
            self.record_query("ROLLBACK;", tx_id=active_tx_id)
            if hasattr(self._thread_local, "current_tx_id"):
                self._thread_local.current_tx_id = None

    def get_trace(self) -> List[Transaction]:
        with self._trace_lock:
            return list(self.transactions.values())

    def _next_op_id(self) -> int:
        with self._trace_lock:
            self._op_counter += 1
            return self._op_counter
