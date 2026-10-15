"""Read-only Postgres access."""

from __future__ import annotations

import time

import psycopg2

from firstalarm.config import DB_NAME

SQL_LOG: list[tuple] = []


def connect_readonly(dataset: str):
    import os
    password = os.environ.get("FA_DB_PASSWORD")
    if not password:
        raise RuntimeError("Set FA_DB_PASSWORD (database password is not stored in the repo).")
    con = psycopg2.connect(
        database=DB_NAME[dataset],
        host=os.environ.get("FA_DB_HOST", "postgres"),
        user=os.environ.get("FA_DB_USER", "postgres"),
        password=password,
        port=int(os.environ.get("FA_DB_PORT", "5432")),
    )
    con.set_session(readonly=True, autocommit=True)
    return con, con.cursor()


def query(cur, label: str, sql: str, params=None) -> list[tuple]:
    t0 = time.time()
    cur.execute(sql, params)
    rows = cur.fetchall()
    SQL_LOG.append((label, sql, round(time.time() - t0, 3), len(rows)))
    return rows
