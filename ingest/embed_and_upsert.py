from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Sequence

from openai import OpenAI

from db.client import get_conn
from ingest.models import ChunkRecord, DriveFile


def _openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required")
    return OpenAI(api_key=api_key)


def embed_texts(texts: Sequence[str], model: str = "text-embedding-3-small") -> list[list[float]]:
    client = _openai_client()
    response = client.embeddings.create(model=model, input=list(texts))
    return [item.embedding for item in response.data]


def upsert_document(drive_file: DriveFile, status: str, content_hash: str | None, error: str | None = None) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (drive_file_id, name, mime_type, folder_path, modified_time, content_hash, status, last_ingested_at, error)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (drive_file_id) DO UPDATE
                SET name=EXCLUDED.name,
                    mime_type=EXCLUDED.mime_type,
                    folder_path=EXCLUDED.folder_path,
                    modified_time=EXCLUDED.modified_time,
                    content_hash=EXCLUDED.content_hash,
                    status=EXCLUDED.status,
                    last_ingested_at=EXCLUDED.last_ingested_at,
                    error=EXCLUDED.error
                """,
                (
                    drive_file.drive_file_id,
                    drive_file.name,
                    drive_file.mime_type,
                    drive_file.folder_path,
                    drive_file.modified_time,
                    content_hash,
                    status,
                    datetime.now(timezone.utc),
                    error,
                ),
            )
        conn.commit()


def get_existing_document(drive_file_id: str) -> dict | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT drive_file_id, modified_time, folder_path, content_hash FROM documents WHERE drive_file_id=%s",
                (drive_file_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "drive_file_id": row[0],
                "modified_time": row[1],
                "folder_path": row[2],
                "content_hash": row[3],
            }


def replace_chunks(drive_file_id: str, chunks: Sequence[ChunkRecord], embeddings: Sequence[list[float]]) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE drive_file_id=%s", (drive_file_id,))
            for chunk, embedding in zip(chunks, embeddings, strict=True):
                cur.execute(
                    """
                    INSERT INTO chunks
                    (chunk_id, drive_file_id, doc_title, folder_path, doc_modified_time, doc_url,
                     source_type, page_or_slide, text_origin, text, embedding)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        str(uuid.uuid4()),
                        chunk.drive_file_id,
                        chunk.doc_title,
                        chunk.folder_path,
                        chunk.doc_modified_time,
                        chunk.doc_url,
                        chunk.source_type,
                        chunk.page_or_slide,
                        chunk.text_origin,
                        chunk.text,
                        embedding,
                    ),
                )
        conn.commit()
    return len(chunks)
