from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import requests
from dateutil import parser as dt_parser

from ingest.models import DriveFile

FOLDER_MIME = "application/vnd.google-apps.folder"


@dataclass
class DriveNode:
    id: str
    name: str
    mime_type: str
    modified_time: datetime | None


class DriveProvider(Protocol):
    def list_files_recursive(self, folder_id: str) -> Iterable[DriveFile]: ...


class PublicDriveWebProvider:
    """Public-folder provider via Drive web responses.

    TODO: Replace with official Drive API provider in V2.
    """

    def __init__(self, cache_dir: str = ".cache/drive") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()

    def list_files_recursive(self, folder_id: str) -> Iterable[DriveFile]:
        yield from self._walk_folder(folder_id, [])

    def _walk_folder(self, folder_id: str, path_parts: list[str]) -> Iterable[DriveFile]:
        nodes = self._list_folder_nodes(folder_id)
        for node in nodes:
            if node.mime_type == FOLDER_MIME:
                yield from self._walk_folder(node.id, path_parts + [node.name])
                continue

            folder_path = "/".join(path_parts) if path_parts else ""
            local_path = self._download_file(node.id, node.name)
            yield DriveFile(
                drive_file_id=node.id,
                name=node.name,
                mime_type=node.mime_type,
                folder_path=folder_path,
                modified_time=node.modified_time,
                local_path=local_path,
                doc_url=f"https://drive.google.com/file/d/{node.id}/view",
            )

    def _list_folder_nodes(self, folder_id: str) -> list[DriveNode]:
        url = f"https://drive.google.com/drive/folders/{folder_id}"
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()

        match = re.search(r"window\['_DRIVE_ivd'\] = '([^']+)'", resp.text)
        if not match:
            return []

        decoded = match.group(1).encode("utf-8").decode("unicode_escape")
        payload = json.loads(decoded)

        nodes: list[DriveNode] = []
        for entry in payload:
            if not isinstance(entry, list) or len(entry) < 4:
                continue
            file_id = entry[0]
            name = entry[2]
            mime_type = entry[3]
            modified_time = None
            if len(entry) > 9 and entry[9]:
                try:
                    modified_time = dt_parser.parse(entry[9]).astimezone(timezone.utc)
                except Exception:
                    modified_time = None

            if not file_id or not name or not mime_type:
                continue
            nodes.append(
                DriveNode(
                    id=file_id,
                    name=name,
                    mime_type=mime_type,
                    modified_time=modified_time,
                )
            )
        return nodes

    def _download_file(self, file_id: str, name: str) -> Path:
        safe_name = re.sub(r"[^\w.\- ]+", "_", name)
        ext = Path(safe_name).suffix
        cache_name = f"{file_id}{ext}" if ext else file_id
        output = self.cache_dir / cache_name

        url = "https://drive.google.com/uc"
        params = {"export": "download", "id": file_id}
        with self.session.get(url, params=params, stream=True, timeout=60) as r:
            r.raise_for_status()
            with output.open("wb") as fh:
                for chunk in r.iter_content(chunk_size=1024 * 128):
                    if chunk:
                        fh.write(chunk)
        return output


def resolve_drive_folder_id() -> str:
    return os.getenv("DRIVE_PUBLIC_FOLDER_ID", "1R6BzZ2UVA9ZECmHOwZFxyh3B7m7RYTmZ")


def content_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
