"""
Deterministic Multi-Thread Barrier Controller for DataRace.
Coordinates thread execution according to exact schedule step indices with sub-millisecond dispatch.
"""

import threading
import time
from typing import List, Tuple, Dict, Optional
from datarace.core.models import Schedule


class BarrierController:
    """
    Coordinates concurrent transaction threads to execute exactly at schedule step `global_step_idx`.
    """

    def __init__(self, schedule: Schedule, timeout_sec: float = 1.0):
        self.schedule = schedule
        self.timeout_sec = timeout_sec
        self.current_step = 0
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.aborted = False
        self.completed = False
        self.execution_log: List[Tuple[str, int, float]] = []

    def wait_for_step(self, expected_step_idx: int) -> bool:
        start_wait = time.time()
        with self.condition:
            while not self.aborted:
                if self.current_step == expected_step_idx:
                    return True
                if self.current_step > expected_step_idx or self.current_step >= len(self.schedule.steps):
                    return False

                elapsed = time.time() - start_wait
                remaining = self.timeout_sec - elapsed
                if remaining <= 0:
                    self.aborted = True
                    self.condition.notify_all()
                    return False

                self.condition.wait(timeout=remaining)

            return not self.aborted

    def mark_step_done(self, tx_id: str, op_index: int):
        with self.condition:
            self.execution_log.append((tx_id, op_index, time.time()))
            self.current_step += 1
            if self.current_step >= len(self.schedule.steps):
                self.completed = True
            self.condition.notify_all()

    def abort(self):
        with self.condition:
            self.aborted = True
            self.condition.notify_all()
