"""
Declarative Invariant Engine for DataRace.
Evaluates domain constraints across SQL tables and Python application state.
"""

from typing import Callable, Dict, List, Optional, Tuple, Any
import sqlite3


class Invariant:
    def __init__(
        self,
        name: str,
        sql_check: Optional[str] = None,
        python_check: Optional[Callable[[Any], bool]] = None,
        description: str = "",
        expected: str = "True"
    ):
        self.name = name
        self.sql_check = sql_check
        self.python_check = python_check
        self.description = description
        self.expected = expected

    def evaluate(self, db_connection=None, app_state=None) -> Tuple[bool, str, str]:
        """
        Evaluates the invariant against the database connection or application state.
        Returns: (passed: bool, expected_str: str, actual_str: str)
        """
        if self.sql_check and db_connection is not None:
            try:
                cursor = db_connection.cursor()
                cursor.execute(self.sql_check)
                row = cursor.fetchone()
                if row is None:
                    return False, self.expected, "No rows returned"
                res_val = row[0]
                # If sql_check returns a boolean or count, evaluate truthiness
                passed = bool(res_val) if isinstance(res_val, (bool, int)) else (res_val is not None)
                return passed, self.expected, f"Query result: {res_val}"
            except Exception as e:
                return False, self.expected, f"SQL error evaluating invariant: {e}"

        if self.python_check and app_state is not None:
            try:
                passed = bool(self.python_check(app_state))
                return passed, self.expected, f"State: {app_state}"
            except Exception as e:
                return False, self.expected, f"Python error evaluating invariant: {e}"

        return True, self.expected, "No checks specified"


class InvariantEngine:
    """Registry and runner for domain invariants."""

    def __init__(self):
        self.invariants: Dict[str, Invariant] = {}

    def register(self, invariant: Invariant):
        self.invariants[invariant.name] = invariant

    def register_sql(self, name: str, sql_query: str, description: str = "", expected: str = "Query returns >= 0 / truthy"):
        self.invariants[name] = Invariant(
            name=name,
            sql_check=sql_query,
            description=description,
            expected=expected
        )

    def check_all(self, db_connection=None, app_state=None) -> List[Tuple[str, bool, str, str]]:
        """
        Runs all registered invariants.
        Returns list of (name, passed, expected, actual).
        """
        results = []
        for name, inv in self.invariants.items():
            passed, exp, act = inv.evaluate(db_connection=db_connection, app_state=app_state)
            results.append((name, passed, exp, act))
        return results
