"""Document parser dispatcher."""

from __future__ import annotations

from pathlib import Path

from models import DocumentParseResult

__all__ = ["parse_document"]


def parse_document(file_path: str | Path) -> DocumentParseResult:
    """Parse a document and extract product data.

    Routes to the appropriate parser based on file extension.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        from parsers.pdf_parser import parse_pdf

        return parse_pdf(path)
    elif ext == ".docx":
        from parsers.docx_parser import parse_docx

        return parse_docx(path)
    elif ext in (".xlsx", ".xlsm", ".xltx"):
        from parsers.xlsx_parser import parse_xlsx

        return parse_xlsx(path)
    elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".gif"):
        from parsers.image_parser import parse_image

        return parse_image(path)
    else:
        return DocumentParseResult(
            file_path=path,
            file_type="unknown",
            products=[],
            errors=[f"Unsupported file type: {ext}"],
        )
