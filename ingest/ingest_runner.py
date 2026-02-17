from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from db.client import init_db
from ingest.chunking import build_chunks
from ingest.drive_sync import PublicDriveWebProvider, content_hash, resolve_drive_folder_id
from ingest.embed_and_upsert import (
    embed_texts,
    get_existing_document,
    replace_chunks,
    upsert_document,
)
from ingest.parse_pdf import parse_pdf
from ingest.parse_pptx import parse_pptx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PDF_MIME = "application/pdf"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


@dataclass
class Summary:
    scanned: int = 0
    ingested: int = 0
    skipped: int = 0
    failed: int = 0
    chunks_inserted: int = 0
    ocr_pages: int = 0


def should_ingest(existing: dict | None, new_modified_time, new_folder_path: str, new_hash: str, force_all: bool) -> bool:
    if force_all or not existing:
        return True
    if existing["folder_path"] != new_folder_path:
        return True
    if existing["modified_time"] != new_modified_time:
        return True
    return existing.get("content_hash") != new_hash


def parse_file(file_path, mime_type: str, text_min_chars: int):
    if mime_type == PDF_MIME:
        return parse_pdf(file_path, text_min_chars=text_min_chars)
    if mime_type == PPTX_MIME:
        return parse_pptx(file_path, text_min_chars=text_min_chars)
    return [], 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-all", action="store_true")
    parser.add_argument("--force-file-id")
    parser.add_argument("--since-days", type=int, default=int(os.getenv("INGEST_SINCE_DAYS", "8")))
    parser.add_argument("--text-min-chars", type=int, default=80)
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    args = parser.parse_args()

    init_db()
    summary = Summary()

    provider = PublicDriveWebProvider()
    threshold = datetime.now(timezone.utc) - timedelta(days=args.since_days)

    for drive_file in provider.list_files_recursive(resolve_drive_folder_id()):
        summary.scanned += 1

        if args.force_file_id and drive_file.drive_file_id != args.force_file_id:
            continue

        if drive_file.mime_type not in {PDF_MIME, PPTX_MIME}:
            summary.skipped += 1
            continue

        existing = get_existing_document(drive_file.drive_file_id)
        file_hash = content_hash(drive_file.local_path)

        if not args.force_all and drive_file.modified_time and drive_file.modified_time < threshold and not args.force_file_id:
            if existing and existing.get("content_hash") == file_hash:
                summary.skipped += 1
                continue

        if not should_ingest(existing, drive_file.modified_time, drive_file.folder_path, file_hash, args.force_all):
            summary.skipped += 1
            continue

        try:
            units, ocr_count = parse_file(drive_file.local_path, drive_file.mime_type, args.text_min_chars)
            summary.ocr_pages += ocr_count
            chunks = build_chunks(drive_file, units, chunk_size=args.chunk_size, overlap=args.chunk_overlap)
            embeddings = embed_texts([chunk.text for chunk in chunks]) if chunks else []
            inserted = replace_chunks(drive_file.drive_file_id, chunks, embeddings) if chunks else 0
            upsert_document(drive_file, status="indexed", content_hash=file_hash)
            summary.ingested += 1
            summary.chunks_inserted += inserted
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to ingest file %s", drive_file.drive_file_id)
            upsert_document(drive_file, status="failed", content_hash=file_hash, error=str(exc))
            summary.failed += 1
            continue

    logger.info(
        "Ingestion summary: scanned=%d ingested=%d skipped=%d failed=%d chunks_inserted=%d ocr_pages=%d",
        summary.scanned,
        summary.ingested,
        summary.skipped,
        summary.failed,
        summary.chunks_inserted,
        summary.ocr_pages,
    )


if __name__ == "__main__":
    main()
