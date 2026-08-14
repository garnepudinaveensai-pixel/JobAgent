from pathlib import Path

import pymupdf
import numpy as np
from rapidocr_onnxruntime import RapidOCR


# ============================================================
# OCR ENGINE
# ============================================================

# Do NOT load OCR when this file is imported.
# OCR will only start if a PDF page actually needs it.
ocr_engine = None


def get_ocr_engine():
    """
    Create and return the OCR engine only when required.
    """

    global ocr_engine

    if ocr_engine is None:
        print("OCR required. Loading OCR engine...")
        ocr_engine = RapidOCR()

    return ocr_engine


# ============================================================
# PAGE TEXT EXTRACTION
# ============================================================

def extract_text_from_page(page) -> str:
    """
    Extract text from one PDF page.

    First tries normal PDF text extraction.
    If no usable text is found, falls back to OCR.

    Supports:
    - Normal text PDFs
    - Scanned PDFs
    - Image PDFs
    - Mixed PDFs
    """

    # --------------------------------------------------------
    # 1. Try normal PDF text extraction
    # --------------------------------------------------------

    text = page.get_text("text").strip()

    # If PyMuPDF found text, use it immediately.
    # This avoids unnecessary OCR.
    if text:
        return text

    # --------------------------------------------------------
    # 2. OCR fallback
    # --------------------------------------------------------

    print("No usable text found. Running OCR...")

    # Render PDF page as an image.
    # 1.5x is faster than 2x while maintaining
    # reasonable OCR quality.
    pix = page.get_pixmap(
        matrix=pymupdf.Matrix(1.5, 1.5),
        alpha=False
    )

    # --------------------------------------------------------
    # Convert PyMuPDF image to NumPy array
    # --------------------------------------------------------

    image = np.frombuffer(
        pix.samples,
        dtype=np.uint8
    ).reshape(
        pix.height,
        pix.width,
        pix.n
    )

    # --------------------------------------------------------
    # Load OCR engine only when necessary
    # --------------------------------------------------------

    ocr = get_ocr_engine()

    # Run OCR
    result, _ = ocr(image)

    if not result:
        return ""

    # --------------------------------------------------------
    # Extract recognized text
    # --------------------------------------------------------

    ocr_lines = []

    for item in result:
        # RapidOCR result:
        # [bounding_box, text, confidence]

        if len(item) >= 2:
            recognized_text = item[1]

            if recognized_text:
                ocr_lines.append(recognized_text)

    return "\n".join(ocr_lines)


# ============================================================
# COMPLETE PDF RESUME LOADER
# ============================================================

def load_resume(resume_path: str) -> str:
    """
    Load a PDF resume and extract all available text.

    Supports:
    - Normal text PDFs
    - Scanned PDFs
    - Image PDFs
    - Mixed PDFs
    - Multi-page PDFs
    - Password-protected PDFs
    """

    # --------------------------------------------------------
    # 1. Check file
    # --------------------------------------------------------

    path = Path(resume_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Resume not found: {path}"
        )

    # --------------------------------------------------------
    # 2. Check extension
    # --------------------------------------------------------

    if path.suffix.lower() != ".pdf":
        raise ValueError(
            "Only PDF files are currently supported."
        )

    # Store extracted text from all pages
    text_parts = []

    # --------------------------------------------------------
    # 3. Open PDF
    # --------------------------------------------------------

    with pymupdf.open(path) as document:

        # ----------------------------------------------------
        # 4. Handle encrypted/password-protected PDFs
        # ----------------------------------------------------

        if document.is_encrypted:

            if not document.authenticate(""):
                raise ValueError(
                    "This PDF is password protected."
                )

        # ----------------------------------------------------
        # 5. Process every page
        # ----------------------------------------------------

        for page_number, page in enumerate(
            document,
            start=1
        ):

            try:

                page_text = extract_text_from_page(page)

                # ------------------------------------------------
                # Add page text if something was extracted
                # ------------------------------------------------

                if page_text.strip():

                    text_parts.append(
                        f"\n--- Page {page_number} ---\n"
                        f"{page_text}"
                    )

            except Exception as error:

                print(
                    f"Warning: Could not process "
                    f"page {page_number}: {error}"
                )

    # --------------------------------------------------------
    # 6. Combine all pages
    # --------------------------------------------------------

    return "\n".join(text_parts).strip()