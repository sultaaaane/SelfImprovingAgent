"""
memory.py — SQLite-backed checkpointer for persistent session memory.
"""

import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver


def get_checkpointer():
    conn = sqlite3.connect("memory.db", check_same_thread=False)
    return SqliteSaver(conn=conn)
