from __future__ import annotations

from io import BytesIO

import pytesseract
from PIL import Image


MIN_IMAGE_WIDTH = 500
MIN_IMAGE_HEIGHT = 300


def should_ocr_image(image_bytes: bytes) -> bool:
    with Image.open(BytesIO(image_bytes)) as img:
        return img.width >= MIN_IMAGE_WIDTH and img.height >= MIN_IMAGE_HEIGHT


def run_ocr(image_bytes: bytes) -> str:
    # TODO: improve pre-processing for noisy scans.
    with Image.open(BytesIO(image_bytes)) as img:
        return pytesseract.image_to_string(img).strip()
