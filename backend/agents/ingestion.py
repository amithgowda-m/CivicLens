import io
import os
import re
import logging
from typing import Dict, Any, List, Optional
from backend.schemas import CivicLensState

logger = logging.getLogger("civiclens.agent.ingestion")

def configure_tesseract() -> bool:
    """Configures pytesseract with detected local or system tesseract binaries."""
    try:
        import pytesseract
        candidate_paths = [
            os.environ.get("TESSERACT_CMD"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            "tesseract",
        ]
        for p in candidate_paths:
            if p and (os.path.exists(p) or p == "tesseract"):
                try:
                    pytesseract.pytesseract.tesseract_cmd = p
                    _ = pytesseract.get_tesseract_version()
                    tessdata_dir = os.path.join(os.path.dirname(p), "tessdata")
                    if os.path.exists(tessdata_dir) and "TESSDATA_PREFIX" not in os.environ:
                        os.environ["TESSDATA_PREFIX"] = tessdata_dir
                    return True
                except Exception:
                    continue
        return False
    except ImportError:
        return False

def check_ocr_availability() -> bool:
    if configure_tesseract():
        return True
    logger.warning("Native Tesseract OCR binary not found or not in PATH. Running in native pdfplumber mode.")
    return False

def extract_pdf_pages(pdf_bytes: bytes, ocr_available: bool) -> List[str]:
    """Extracts text page-by-page from PDF bytes with OCR fallback."""
    import pdfplumber
    pages_text: List[str] = []
    
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text() or page.extract_text(layout=True) or ""
            
            # If text is empty/sparse, or contains unmapped font CID glyphs (e.g. (cid:3542)), run OCR
            has_cid_corruption = len(re.findall(r"\(cid:\d+\)", text)) > 2
            if (len(text.strip()) < 20 or has_cid_corruption) and ocr_available:
                try:
                    import pytesseract
                    langs = "eng"
                    try:
                        avail = pytesseract.get_languages()
                        if "kan" in avail:
                            langs = "eng+kan"
                    except Exception:
                        pass
                    
                    img = page.to_image(resolution=300).original
                    ocr_text = pytesseract.image_to_string(img, lang=langs)
                    if len(ocr_text.strip()) > 20:
                        text = ocr_text
                        logger.info(f"Page {page_idx+1} recovered via OCR ({langs}).")
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
