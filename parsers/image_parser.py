"""Image parser with OCR support."""

from __future__ import annotations

import logging
from pathlib import Path

from models import DocumentParseResult, Product
from parsers.utils import extract_products_from_text

logger = logging.getLogger(__name__)


def parse_image(file_path: Path) -> DocumentParseResult:
    """Extract product data from an image using OCR."""
    errors: list[str] = []
    raw_text = ""

    # Try pytesseract first
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(str(file_path))
        raw_text = pytesseract.image_to_string(img, lang="rus+eng")
    except ImportError:
        errors.append("pytesseract not installed, trying manual extraction")
    except Exception as e:
        logger.exception("OCR error for %s", file_path)
        errors.append(f"OCR error: {e}")

    # Fallback: basic metadata extraction
    if not raw_text:
        try:
            from PIL import Image
            img = Image.open(str(file_path))
            raw_text = f"[Image: {img.size[0]}x{img.size[1]}, {img.format}]"
        except Exception:
            raw_text = f"[Image file: {file_path.name}]"

    products = extract_products_from_text(raw_text)

    return DocumentParseResult(
        file_path=file_path, file_type="image", products=products,
        raw_text=raw_text, errors=errors,
    )
