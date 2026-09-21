# -*- coding: utf-8 -*-

"""
Mento.AI OCR Engine

Primary OCR:
    RapidOCR (ONNX)

Optional fallback:
    Tesseract via pytesseract

Designed for:
    - Windows local development
    - Linux cloud deployment such as Render
"""

import io
import logging
import os

import numpy as np
from PIL import Image, ImageEnhance, ImageOps


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ocr_engine")


# =========================================================
# RAPIDOCR
# =========================================================

_RAPIDOCR_INSTANCE = None
RAPIDOCR_AVAILABLE = False

try:
    from rapidocr_onnxruntime import RapidOCR

    RAPIDOCR_AVAILABLE = True
    logger.info("RapidOCR package is available.")

except ImportError:
    logger.warning("RapidOCR is not installed.")


# =========================================================
# TESSERACT
# =========================================================

TESSERACT_AVAILABLE = False
pytesseract = None

try:
    import pytesseract

    def configure_tesseract():
        """
        Detect whether Tesseract is installed.
        """

        # Try Tesseract available in system PATH
        try:
            pytesseract.get_tesseract_version()

            logger.info("Tesseract executable detected.")

            return True

        except Exception:
            pass

        # Windows installation paths
        if os.name == "nt":

            windows_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expanduser(
                    r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
                ),
            ]

            for path in windows_paths:

                if os.path.exists(path):

                    try:
                        pytesseract.pytesseract.tesseract_cmd = path

                        pytesseract.get_tesseract_version()

                        logger.info(
                            "Tesseract found at: %s",
                            path
                        )

                        return True

                    except Exception:
                        continue

        logger.warning(
            "Tesseract executable not found. "
            "RapidOCR will be used."
        )

        return False


    TESSERACT_AVAILABLE = configure_tesseract()

except ImportError:

    logger.warning(
        "pytesseract is not installed. "
        "Tesseract fallback disabled."
    )


# =========================================================
# OCR AVAILABILITY
# =========================================================

OCR_AVAILABLE = (
    RAPIDOCR_AVAILABLE or
    TESSERACT_AVAILABLE
)


# =========================================================
# RAPIDOCR LAZY INITIALIZATION
# =========================================================

def get_rapidocr():
    """
    Initialize RapidOCR only when required.
    """

    global _RAPIDOCR_INSTANCE

    if (
        _RAPIDOCR_INSTANCE is None
        and RAPIDOCR_AVAILABLE
    ):

        try:

            logger.info(
                "Initializing RapidOCR engine..."
            )

            _RAPIDOCR_INSTANCE = RapidOCR()

            logger.info(
                "RapidOCR initialized successfully."
            )

        except Exception as exc:

            logger.exception(
                "Failed to initialize RapidOCR: %s",
                exc
            )

            _RAPIDOCR_INSTANCE = None

    return _RAPIDOCR_INSTANCE


# =========================================================
# COMPATIBILITY ALIAS
# =========================================================

OCR_ENGINE_INSTANCE = None


# =========================================================
# IMAGE PREPROCESSING
# =========================================================

def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Improve image quality before OCR.
    """

    try:

        gray = image.convert("L")

        enhancer = ImageEnhance.Contrast(gray)

        enhanced = enhancer.enhance(2.0)

        normalized = ImageOps.autocontrast(
            enhanced
        )

        return normalized

    except Exception as exc:

        logger.error(
            "Image preprocessing error: %s",
            exc
        )

        return image


# =========================================================
# RAPIDOCR EXTRACTION
# =========================================================

def _extract_with_rapidocr(
    image: Image.Image
) -> str:

    engine = get_rapidocr()

    if engine is None:
        return ""

    try:

        img_array = np.array(
            image.convert("RGB")
        )

        result, _ = engine(img_array)

        if not result:
            return ""

        lines = []

        for line in result:

            if line and len(line) > 1:

                text = line[1]

                if text:
                    lines.append(str(text))

        return "\n".join(lines).strip()

    except Exception as exc:

        logger.exception(
            "RapidOCR extraction error: %s",
            exc
        )

        return ""


# =========================================================
# TESSERACT EXTRACTION
# =========================================================

def _extract_with_tesseract(
    image: Image.Image
) -> str:

    if (
        not TESSERACT_AVAILABLE
        or pytesseract is None
    ):
        return ""

    try:

        processed_image = preprocess_image(
            image
        )

        text = pytesseract.image_to_string(
            processed_image
        )

        return text.strip()

    except Exception as exc:

        logger.exception(
            "Tesseract extraction error: %s",
            exc
        )

        return ""


# =========================================================
# PUBLIC IMAGE OCR
# =========================================================

def extract_text_from_image(
    image: Image.Image
) -> str:
    """
    Extract text from an image.

    Priority:

    1. RapidOCR
    2. Tesseract
    3. Empty string
    """

    if not OCR_AVAILABLE:

        logger.warning(
            "No OCR engine is available."
        )

        return ""

    # -----------------------------------------------------
    # RapidOCR
    # -----------------------------------------------------

    if RAPIDOCR_AVAILABLE:

        text = _extract_with_rapidocr(
            image
        )

        if text:
            return text

    # -----------------------------------------------------
    # Tesseract fallback
    # -----------------------------------------------------

    if TESSERACT_AVAILABLE:

        text = _extract_with_tesseract(
            image
        )

        if text:
            return text

    return ""


# =========================================================
# PYMUPDF PIXMAP OCR
# =========================================================

def extract_text_from_pixmap(
    pixmap
) -> str:
    """
    Convert PyMuPDF Pixmap to Pillow Image
    and run OCR.
    """

    try:

        png_bytes = pixmap.tobytes(
            "png"
        )

        image = Image.open(
            io.BytesIO(png_bytes)
        )

        return extract_text_from_image(
            image
        )

    except Exception as exc:

        logger.exception(
            "Pixmap OCR error: %s",
            exc
        )

        return ""