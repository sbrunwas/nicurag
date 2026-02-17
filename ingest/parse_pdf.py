from __future__ import annotations

from pathlib import Path

import fitz

from ingest.models import ExtractedUnit
from ingest.ocr import run_ocr, should_ocr_image


def parse_pdf(path: Path, text_min_chars: int) -> tuple[list[ExtractedUnit], int]:
    units: list[ExtractedUnit] = []
    ocr_count = 0

    doc = fitz.open(path)
    try:
        for idx, page in enumerate(doc, start=1):
            native_text = page.get_text("text").strip()
            if len(native_text) >= text_min_chars:
                units.append(
                    ExtractedUnit(
                        source_type="pdf_page",
                        page_or_slide=idx,
                        text=native_text,
                        text_origin="native_text",
                    )
                )
                continue

            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            image_bytes = pix.tobytes("png")
            if should_ocr_image(image_bytes):
                ocr_text = run_ocr(image_bytes)
                if ocr_text:
                    units.append(
                        ExtractedUnit(
                            source_type="pdf_page",
                            page_or_slide=idx,
                            text=ocr_text,
                            text_origin="ocr",
                        )
                    )
                    ocr_count += 1
                elif native_text:
                    units.append(
                        ExtractedUnit(
                            source_type="pdf_page",
                            page_or_slide=idx,
                            text=native_text,
                            text_origin="native_text",
                        )
                    )
            elif native_text:
                units.append(
                    ExtractedUnit(
                        source_type="pdf_page",
                        page_or_slide=idx,
                        text=native_text,
                        text_origin="native_text",
                    )
                )
    finally:
        doc.close()

    return units, ocr_count
