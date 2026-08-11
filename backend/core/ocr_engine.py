# -*- coding: utf-8 -*-
"""
Mento.AI OCR Engine
Handles text extraction from scanned documents and images using RapidOCR (ONNX) with pytesseract fallback.
"""

import os
import sys
import logging
import numpy as np
from PIL import Image, ImageEnhance, ImageOps

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ocr_engine")

_RAPIDOCR_INSTANCE = None
RAPIDOCR_AVAILABLE = False

try:
    from rapidocr_onnxruntime import RapidOCR
    RAPIDOCR_AVAILABLE = True
    logger.info("RapidOCR (ONNX) engine is available.")
except ImportError:
    logger.warning("RapidOCR is not installed.")

# Fallback pytesseract support
import pytesseract

TESSERACT_COMMON_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
]

def configure_tesseract() -> bool:
    """Try to configure Tesseract path on Windows if available."""
    try:
        pytesseract.get_tesseract_version()
        return True
    except pytesseract.TesseractNotFoundError:
        for path in TESSERACT_COMMON_PATHS:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                try:
                    pytesseract.get_tesseract_version()
                    return True
                except Exception:
                    pass
        return False

TESSERACT_AVAILABLE = configure_tesseract()
OCR_AVAILABLE = RAPIDOCR_AVAILABLE or TESSERACT_AVAILABLE

def get_rapidocr():
    """Lazy initialization of RapidOCR model."""
    global _RAPIDOCR_INSTANCE
    if _RAPIDOCR_INSTANCE is None and RAPIDOCR_AVAILABLE:
        try:
            logger.info("Initializing RapidOCR engine...")
            _RAPIDOCR_INSTANCE = RapidOCR()
            logger.info("RapidOCR engine initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize RapidOCR: {e}")
    return _RAPIDOCR_INSTANCE

def preprocess_image(image: Image.Image) -> Image.Image:
    """Enhance the image for better OCR accuracy."""
    try:
        gray = image.convert("L")
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(2.0)
        normalized = ImageOps.autocontrast(enhanced)
        return normalized
    except Exception as e:
        logger.error(f"Error in image preprocessing: {e}")
        return image

def extract_text_from_image(image: Image.Image) -> str:
    """Extract text from a Pillow Image using RapidOCR or pytesseract fallback."""
    if not OCR_AVAILABLE:
        logger.warning("No OCR engine available.")
        return ""

    # Try RapidOCR first
    if RAPIDOCR_AVAILABLE:
        try:
            engine = get_rapidocr()
            if engine:
                img_array = np.array(image.convert("RGB"))
                result, _ = engine(img_array)
                if result:
                    lines = [line[1] for line in result if line and len(line) > 1]
                    extracted_text = "\n".join(lines).strip()
                    if extracted_text:
                        return extracted_text
        except Exception as e:
            logger.error(f"RapidOCR extraction error: {e}")

    # Fallback to Tesseract
    if TESSERACT_AVAILABLE:
        try:
            processed_img = preprocess_image(image)
            text = pytesseract.image_to_string(processed_img)
            return text.strip()
        except Exception as e:
            logger.error(f"Tesseract OCR extraction error: {e}")

    return ""

def extract_text_from_pixmap(pixmap) -> str:
    """Convert a PyMuPDF Pixmap to a Pillow Image and perform OCR."""
    import io
    try:
        png_bytes = pixmap.tobytes("png")
        image = Image.open(io.BytesIO(png_bytes))
        return extract_text_from_image(image)
    except Exception as e:
        logger.error(f"Error processing page pixmap: {e}")
        return ""
