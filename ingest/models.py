from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass
class DriveFile:
    drive_file_id: str
    name: str
    mime_type: str
    folder_path: str
    modified_time: datetime | None
    local_path: Path
    doc_url: str


@dataclass
class ExtractedUnit:
    source_type: Literal["pdf_page", "ppt_slide"]
    page_or_slide: int
    text: str
    text_origin: Literal["native_text", "ocr"]


@dataclass
class ChunkRecord:
    drive_file_id: str
    doc_title: str
    folder_path: str
    doc_modified_time: datetime | None
    doc_url: str
    source_type: Literal["pdf_page", "ppt_slide"]
    page_or_slide: int
    text_origin: Literal["native_text", "ocr"]
    text: str
