"""
SQL AST / Lexical Parser for DataRace.
Extracts Operation Type, Table, Modified Columns, Where Predicates, and Key Access Sets.
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from datarace.core.models import OpType


class SQLParser:
    """Lightweight deterministic SQL parser for OLTP transaction tracing."""

    @staticmethod
    def parse_statement(sql: str, params: Optional[Dict[str, Any]] = None) -> Tuple[OpType, Optional[str], List[str], List[str]]:
        """
        Parses a SQL string and returns:
        (OpType, table_name, columns, keys)
        """
        cleaned = sql.strip()
        cleaned_upper = cleaned.upper()

        if cleaned_upper.startswith("BEGIN"):
            return OpType.BEGIN, None, [], []
        if cleaned_upper.startswith("COMMIT"):
            return OpType.COMMIT, None, [], []
        if cleaned_upper.startswith("ROLLBACK") or cleaned_upper.startswith("ABORT"):
            return OpType.ABORT, None, [], []

        # Check for SELECT ... FOR UPDATE (LOCK)
        is_for_update = "FOR UPDATE" in cleaned_upper or "FOR SHARE" in cleaned_upper

        # SELECT
        if cleaned_upper.startswith("SELECT"):
            op_type = OpType.LOCK if is_for_update else OpType.READ
            table, columns, keys = SQLParser._parse_select(cleaned, params)
            return op_type, table, columns, keys

        # UPDATE
        if cleaned_upper.startswith("UPDATE"):
            table, columns, keys = SQLParser._parse_update(cleaned, params)
            return OpType.WRITE, table, columns, keys

        # INSERT
        if cleaned_upper.startswith("INSERT"):
            table, columns, keys = SQLParser._parse_insert(cleaned, params)
            return OpType.WRITE, table, columns, keys

        # DELETE
        if cleaned_upper.startswith("DELETE"):
            table, columns, keys = SQLParser._parse_delete(cleaned, params)
            return OpType.WRITE, table, columns, keys

        # Default fallback
        return OpType.READ, None, [], []

    @staticmethod
    def _parse_select(sql: str, params: Optional[Dict[str, Any]]) -> Tuple[Optional[str], List[str], List[str]]:
        # Match FROM <table>
        table_match = re.search(r"\bFROM\s+([a-zA-Z0-9_]+)", sql, re.IGNORECASE)
        table = table_match.group(1).lower() if table_match else "unknown"

        # Match columns: SELECT col1, col2 FROM ...
        cols_match = re.search(r"SELECT\s+(.*?)\s+FROM", sql, re.IGNORECASE | re.DOTALL)
        columns = []
        if cols_match:
            raw_cols = cols_match.group(1).split(",")
            columns = [c.strip().split()[-1].replace('"', '').replace('`', '').lower() for c in raw_cols]

        keys = SQLParser._extract_where_keys(table, sql, params)
        return table, columns, keys

    @staticmethod
    def _parse_update(sql: str, params: Optional[Dict[str, Any]]) -> Tuple[Optional[str], List[str], List[str]]:
        table_match = re.search(r"UPDATE\s+([a-zA-Z0-9_]+)", sql, re.IGNORECASE)
        table = table_match.group(1).lower() if table_match else "unknown"

        # Match SET col1 = val1, col2 = val2
        set_match = re.search(r"SET\s+(.*?)(?:\s+WHERE|$)", sql, re.IGNORECASE | re.DOTALL)
        columns = []
        if set_match:
            assignments = set_match.group(1).split(",")
            for assign in assignments:
                parts = assign.split("=")
                if len(parts) > 0:
                    columns.append(parts[0].strip().replace('"', '').replace('`', '').lower())

        keys = SQLParser._extract_where_keys(table, sql, params)
        return table, columns, keys

    @staticmethod
    def _parse_insert(sql: str, params: Optional[Dict[str, Any]]) -> Tuple[Optional[str], List[str], List[str]]:
        table_match = re.search(r"INSERT\s+INTO\s+([a-zA-Z0-9_]+)", sql, re.IGNORECASE)
        table = table_match.group(1).lower() if table_match else "unknown"

        cols_match = re.search(r"\((.*?)\)\s+VALUES", sql, re.IGNORECASE | re.DOTALL)
        columns = []
        if cols_match:
            raw_cols = cols_match.group(1).split(",")
            columns = [c.strip().replace('"', '').replace('`', '').lower() for c in raw_cols]

        # Key for insert is row identifier if available or table insert slot
        keys = [f"{table}:insert"]
        if params and "id" in params:
            keys.append(f"{table}:{params['id']}")
        return table, columns, keys

    @staticmethod
    def _parse_delete(sql: str, params: Optional[Dict[str, Any]]) -> Tuple[Optional[str], List[str], List[str]]:
        table_match = re.search(r"FROM\s+([a-zA-Z0-9_]+)", sql, re.IGNORECASE)
        table = table_match.group(1).lower() if table_match else "unknown"
        keys = SQLParser._extract_where_keys(table, sql, params)
        return table, ["*"], keys

    @staticmethod
    def _extract_where_keys(table: str, sql: str, params: Optional[Dict[str, Any]]) -> List[str]:
        keys = []
        where_match = re.search(r"WHERE\s+(.*?)(?:FOR\s+UPDATE|ORDER\s+BY|LIMIT|GROUP\s+BY|;|$)", sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            clause = where_match.group(1).strip()
            # Match patterns like id = 42, item_id = 10, user_id = 'alice'
            id_matches = re.findall(r"([a-zA-Z0-9_]+)\s*=\s*(['\"]?[a-zA-Z0-9_\-]+['\"]?|\:\w+|\?)", clause)
            for col, val in id_matches:
                col_clean = col.lower()
                val_clean = val.strip("'\"")
                if val_clean.startswith(":") and params and val_clean[1:] in params:
                    val_clean = str(params[val_clean[1:]])
                elif val_clean == "?" and params and col_clean in params:
                    val_clean = str(params[col_clean])
                keys.append(f"{table}:{col_clean}={val_clean}")
        if not keys:
            # Fallback to whole table key if no specific predicate
            keys.append(f"{table}:*")
        return keys
