"""Explicit SQLite connections with relational and immutable-evidence guards."""

import sqlite3
from pathlib import Path


def connect_database(path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    # Also fire immutable delete guards for INSERT OR REPLACE.
    connection.execute("PRAGMA recursive_triggers = ON")
    return connection
