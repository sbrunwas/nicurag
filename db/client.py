from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import psycopg
from pgvector.psycopg import register_vector

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is required")
    return database_url


def get_embedding_dim() -> int:
    return int(os.getenv("EMBEDDING_DIM", "1536"))


@contextmanager
def get_conn() -> Generator[psycopg.Connection, None, None]:
    conn = psycopg.connect(get_database_url(), autocommit=False)
    register_vector(conn)
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    schema_template = SCHEMA_PATH.read_text()
    schema_sql = schema_template.replace("__EMBEDDING_DIM__", str(get_embedding_dim()))

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
