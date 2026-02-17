from __future__ import annotations

from ingest.models import ChunkRecord, DriveFile, ExtractedUnit


def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def build_chunks(
    drive_file: DriveFile,
    units: list[ExtractedUnit],
    chunk_size: int,
    overlap: int,
) -> list[ChunkRecord]:
    out: list[ChunkRecord] = []
    for unit in units:
        text_chunks = split_text(unit.text, chunk_size=chunk_size, overlap=overlap)
        for text in text_chunks:
            out.append(
                ChunkRecord(
                    drive_file_id=drive_file.drive_file_id,
                    doc_title=drive_file.name,
                    folder_path=drive_file.folder_path,
                    doc_modified_time=drive_file.modified_time,
                    doc_url=drive_file.doc_url,
                    source_type=unit.source_type,
                    page_or_slide=unit.page_or_slide,
                    text_origin=unit.text_origin,
                    text=text,
                )
            )
    return out
