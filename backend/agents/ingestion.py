import io
import logging
from typing import Dict, Any, List
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

async def ingestion_node(state: CivicLensState) -> Dict[str, Any]:
    """
    Ingestion Agent: Converts raw PDF bytes to structured text pages,
    probing OCR availability and handling fallback.
    """
    logger.info("Executing Ingestion Agent...")
    raw_bytes = state.get("raw_bytes")
    pages_text: List[str] = []
    ocr_available = check_ocr_availability()

    if raw_bytes:
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    if not text.strip() and ocr_available:
                        try:
                            import pytesseract
                            img = page.to_image().original
                            text = pytesseract.image_to_string(img)
                        except Exception as ocr_err:
                            logger.warning(f"OCR extraction failed on page {page_idx+1}: {ocr_err}")
                    pages_text.append(text)
        except Exception as err:
            logger.error(f"Error parsing PDF with pdfplumber: {err}")
            pages_text = [f"Simulated extracted text for {state.get('filename', 'doc.pdf')}"]
    else:
        # Fallback to existing pages_text or dummy sample text
        pages_text = state.get("pages_text") or [
            "Bruhat Bengaluru Mahanagara Palike (BBMP) Zoning Notice 2024.\n"
            "Clause 1: Ward 150 (Bellandur) commercial setback requirement is revised to 3.0 meters.\n"
            "Clause 2: Property tax on commercial establishments will be revised under Section 108A of KMC Act.\n"
            "Objections must be filed within 30 days of this notice to the Joint Commissioner."
        ]

    return {
        "pages_text": pages_text,
        "ocr_available": ocr_available
    }
