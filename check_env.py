import sys
import sqlite3

print("Python:", sys.version)
print("SQLite:", sqlite3.sqlite_version)

try:
    import pytest
    print("pytest:", pytest.__version__)
except ImportError:
    print("pytest: not installed")

try:
    import sqlalchemy
    print("sqlalchemy:", sqlalchemy.__version__)
except ImportError:
    print("sqlalchemy: not installed")
