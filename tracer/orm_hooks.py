"""
SQLAlchemy & DB-API Connection Event Hooks for DataRace.
Automatically intercepts cursor execution and routes queries to Tracer.
"""

from datarace.tracer.tracer import Tracer

try:
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


def attach_sqlalchemy_tracer(engine, tracer: Tracer = None):
    """Hooks into a SQLAlchemy Engine to record queries automatically."""
    if not HAS_SQLALCHEMY:
        return

    active_tracer = tracer or Tracer.get_instance()

    @event.listens_for(engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        params_dict = {}
        if isinstance(parameters, dict):
            params_dict = parameters
        elif isinstance(parameters, (list, tuple)):
            params_dict = {f"p_{i}": v for i, v in enumerate(parameters)}

        active_tracer.record_query(statement, params=params_dict)

    @event.listens_for(engine, "begin")
    def receive_begin(conn):
        active_tracer.start_transaction()

    @event.listens_for(engine, "commit")
    def receive_commit(conn):
        active_tracer.commit_transaction()

    @event.listens_for(engine, "rollback")
    def receive_rollback(conn):
        active_tracer.rollback_transaction()
