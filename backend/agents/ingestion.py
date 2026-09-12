import io
import os
import logging
from typing import Dict, Any, List, Optional
from backend.schemas import CivicLensState

logger = logging.getLogger("civiclens.agent.ingestion")

def check_ocr_availability() -> bool:
    try:
        import pytesseract
        _ = pytesseract.get_tesseract_version()
        return True
    except Exception as e:
        logger.warning(f"Native Tesseract OCR binary not found or not in PATH ({e}). Running in native pdfplumber mode.")
        return False

def extract_pdf_pages(pdf_bytes: bytes, ocr_available: bool) -> List[str]:
    """Extracts text page-by-page from PDF bytes with OCR fallback."""
    import pdfplumber
    pages_text: List[str] = []
    
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text(layout=True) or page.extract_text() or ""
            
            # If text is empty or sparse, and OCR is available, run OCR on the page image
            if len(text.strip()) < 20 and ocr_available:
                try:
                    import pytesseract
                    img = page.to_image(resolution=300).original
                    ocr_text = pytesseract.image_to_string(img)
                    if len(ocr_text.strip()) > len(text.strip()):
                        text = ocr_text
                except Exception as ocr_err:
                    logger.warning(f"OCR fallback failed on page {page_idx+1}: {ocr_err}")

            # Clean form feeds and null characters without altering offsets significantly
            cleaned = text.replace("\x00", "").replace("\r\n", "\n")
            pages_text.append(cleaned)
            
    return pages_text

async def ingestion_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Ingestion Agent: Ingests PDF bytes or documents dynamically,
    extracting clean text and page maps for downstream verbatim clause snapping.
    """
    logger.info("Executing Ingestion Agent on document...")
    raw_bytes = state.get("raw_bytes")
    filename = state.get("filename", "document.pdf")
    pages_text: List[str] = []
    ocr_available = check_ocr_availability()

    # If bytes not in memory, check sample_docs or disk
    if not raw_bytes and filename:
        disk_path = os.path.join("backend/data/sample_docs", filename)
        if os.path.exists(disk_path):
            with open(disk_path, "rb") as f:
                raw_bytes = f.read()

    if raw_bytes and raw_bytes.startswith(b"%PDF"):
        try:
            pages_text = extract_pdf_pages(raw_bytes, ocr_available)
            logger.info(f"Successfully extracted {len(pages_text)} pages via pdfplumber.")
        except Exception as err:
            logger.error(f"Error parsing PDF with pdfplumber: {err}")
            # Try raw decode or fallback
            try:
                pages_text = [raw_bytes.decode("utf-8", errors="ignore")]
            except Exception:
                pages_text = ["Error extracting text from uploaded PDF."]
    elif raw_bytes:
        # Plaintext or non-PDF bytes
        pages_text = [raw_bytes.decode("utf-8", errors="ignore")]
    else:
        # Retain existing pages or provide clean fallback
        pages_text = state.get("pages_text") or []

    return {
        "pages_text": pages_text,
        "ocr_available": ocr_available
    }
