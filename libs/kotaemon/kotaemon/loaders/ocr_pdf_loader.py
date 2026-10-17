"""PDF reader that OCRs the pages which carry no usable text layer.

Scanned PDFs frequently ship a text layer that holds only the headings while the
body of the page is an image. Plain extraction then indexes almost nothing: the
retriever returns section titles, the answer model has no content to work with,
and it either refuses to answer or answers from its own memory.

This reader walks the pages and decides per page:

* the page has a real text layer (>= ``min_text_chars``) -> keep it as is, so
  digital PDFs are not slowed down and their text is not degraded;
* the text layer is thin -> render the page and recognize it locally.

Recognition uses ``rapidocr-onnxruntime`` (PP-OCR models on onnxruntime, no
PyTorch, models bundled in the wheel), so it runs fully offline once installed.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from decouple import config

from kotaemon.base import Document

from .base import BaseReader

logger = logging.getLogger(__name__)

#: A page whose text layer is shorter than this is treated as scanned.
MIN_TEXT_CHARS = config("PDF_OCR_MIN_CHARS", default=200, cast=int)
#: Rendering resolution handed to the OCR engine (200 dpi is a good trade-off).
OCR_DPI = config("PDF_OCR_DPI", default=200, cast=int)

#: The engine holds onnx sessions; build it once and serialize the calls, since
#: indexing may run several files in parallel.
_ENGINE: Any = None
_ENGINE_LOCK = threading.Lock()
_RUN_LOCK = threading.Lock()


def get_ocr_engine() -> Any:
    """Return the shared OCR engine, or ``None`` when it is not installed."""
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except ImportError:
                logger.warning(
                    "rapidocr-onnxruntime is not installed: pages without a text "
                    "layer will stay empty. Install it with "
                    "`uv pip install rapidocr-onnxruntime`"
                )
                return None
            _ENGINE = RapidOCR()
    return _ENGINE


class OCRPDFReader(BaseReader):
    """One document per page, OCR-ing the pages that have no usable text layer."""

    min_text_chars: int = MIN_TEXT_CHARS
    dpi: int = OCR_DPI

    def load_data(
        self,
        file: Path,
        extra_info: Optional[Dict] = None,
        fs: Optional[Any] = None,
        **kwargs: Any,
    ) -> List[Document]:
        """Parse the PDF, page by page.

        Args:
            file: path to the PDF.
            extra_info: metadata merged into every produced document.
            fs: unused, kept for signature compatibility with other readers.

        Returns:
            One document per non-empty page.
        """
        import fitz  # PyMuPDF

        path = Path(file)
        extra = dict(extra_info or {})
        engine = get_ocr_engine()
        base_metadata = {
            "file_path": str(path),
            "file_name": path.name,
            "file_type": "application/pdf",
            "file_size": os.path.getsize(path),
        }

        documents: List[Document] = []
        ocr_pages = 0
        with fitz.open(str(path)) as doc:
            for page_number, page in enumerate(doc):
                text = page.get_text("text").strip()
                used_ocr = False
                if len(text) < self.min_text_chars and engine is not None:
                    recognized = self._recognize(page, engine)
                    if recognized.strip():
                        text = recognized.strip()
                        used_ocr = True
                        ocr_pages += 1

                if not text:
                    logger.warning(
                        "page %d of %s produced no text (text layer too thin, OCR "
                        "unavailable or empty)",
                        page_number + 1,
                        path.name,
                    )
                    continue

                metadata = {
                    **base_metadata,
                    "page_label": str(page_number + 1),
                    "page_number": page_number,
                    "ocr": used_ocr,
                    **extra,
                }
                documents.append(Document(text=text, metadata=metadata))

        if ocr_pages:
            logger.info("OCR used for %d page(s) of %s", ocr_pages, path.name)
        return documents

    def run(
        self,
        file_path: str | Path,
        extra_info: Optional[dict] = None,
        **kwargs: Any,
    ) -> List[Document]:
        return self.load_data(Path(file_path), extra_info=extra_info, **kwargs)

    def _recognize(self, page: Any, engine: Any) -> str:
        """Render one page and run OCR on it."""
        pixmap = page.get_pixmap(dpi=self.dpi)
        png = pixmap.tobytes("png")
        with _RUN_LOCK:
            result, _ = engine(png)
        if not result:
            return ""
        lines = [str(item[1]) for item in result if len(item) > 1 and item[1]]
        return "\n".join(lines)
