"""Image parser with OCR support."""

from __future__ import annotations

import logging
from pathlib import Path

from config import settings
from models import DocumentParseResult
from parsers.utils import extract_products_from_text

logger = logging.getLogger(__name__)


def parse_image(file_path: Path) -> DocumentParseResult:
    """Extract product data from an image using OCR."""
    errors: list[str] = []
    raw_text = ""
    confidences: list[float] = []

    # Try pytesseract first
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(str(file_path))
        data = pytesseract.image_to_data(img, lang="rus+eng", output_type=pytesseract.Output.DICT)
        words: list[str] = []
        for text, conf in zip(data.get("text", []), data.get("conf", []), strict=False):
            try:
                c = float(conf)
            except (TypeError, ValueError):
                continue
            if text and text.strip() and c >= 0:
                words.append(text)
                confidences.append(c)
        raw_text = " ".join(words)
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

    mean_conf = sum(confidences) / len(confidences) if confidences else None
    if mean_conf is not None:
        for p in products:
            p.ocr_confidence = mean_conf
        if mean_conf < settings.ocr.low_confidence_threshold:
            errors.append(
                f"Позиции с низким OCR-confidence: среднее {mean_conf:.1f} < "
                f"порога {settings.ocr.low_confidence_threshold}"
            )

    return DocumentParseResult(
        file_path=file_path,
        file_type="image",
        products=products,
        raw_text=raw_text,
        errors=errors,
    )
