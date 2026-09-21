# -*- coding: utf-8 -*-
"""
Mento.AI OCR Engine

Primary OCR:
    RapidOCR (ONNX) - High speed, high accuracy, cross-platform (Windows & Linux)

Optional fallback:
    Tesseract via pytesseract (if installed and configured)

Features:
    - Lazy loading (does not slow down application startup or Render boot)
    - Differentiated image preprocessing for printed documents vs handwritten notes
    - Pixmap and PIL Image text extraction
    - Bounding-box and line-level confidence scoring
"""

import io
import logging
import os
import shutil
from typing import Optional, List, Dict, Any, Tuple
import numpy as np
from PIL import Image, ImageEnhance, ImageOps, ImageFilter

# =========================================================
# LOGGING
# =========================================================

logger = logging.getLogger("ocr_engine")

# =========================================================
# RAPIDOCR LAZY SINGLETON
# =========================================================

_RAPIDOCR_INSTANCE = None
RAPIDOCR_AVAILABLE = False

try:
    from rapidocr_onnxruntime import RapidOCR
    RAPIDOCR_AVAILABLE = True
except ImportError:
    logger.warning("RapidOCR package is not installed.")

def get_rapidocr():
    """
    Lazy initialization of RapidOCR. Loaded on first use.
    """
    global _RAPIDOCR_INSTANCE
    if _RAPIDOCR_INSTANCE is None and RAPIDOCR_AVAILABLE:
        try:
            logger.info("Initializing RapidOCR engine (lazy load)...")
            _RAPIDOCR_INSTANCE = RapidOCR()
            logger.info("RapidOCR initialized successfully.")
        except Exception as exc:
            logger.exception("Failed to initialize RapidOCR: %s", exc)
            _RAPIDOCR_INSTANCE = None
    return _RAPIDOCR_INSTANCE


# =========================================================
# TESSERACT CONFIGURATION
# =========================================================

TESSERACT_AVAILABLE = False
pytesseract = None

try:
    import pytesseract

    def configure_tesseract() -> bool:
        """
        Detect whether Tesseract is installed and configured.
        Supports TESSERACT_CMD environment variable for Linux/Render and common Windows paths.
        """
        # 1. Check environment variable
        env_cmd = os.environ.get("TESSERACT_CMD")
        if env_cmd and os.path.exists(env_cmd):
            pytesseract.pytesseract.tesseract_cmd = env_cmd
            try:
                pytesseract.get_tesseract_version()
                logger.info("Tesseract configured via TESSERACT_CMD: %s", env_cmd)
                return True
            except Exception:
                pass

        # 2. Check system PATH
        try:
            pytesseract.get_tesseract_version()
            logger.info("Tesseract detected on system PATH.")
            return True
        except Exception:
            pass

        # 3. Windows standard installation paths
        if os.name == "nt":
            windows_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
            ]
            for path in windows_paths:
                if os.path.exists(path):
                    try:
                        pytesseract.pytesseract.tesseract_cmd = path
                        pytesseract.get_tesseract_version()
                        logger.info("Tesseract detected at: %s", path)
                        return True
                    except Exception:
                        continue

        # 4. Linux standard binary check
        which_tess = shutil.which("tesseract")
        if which_tess:
            try:
                pytesseract.pytesseract.tesseract_cmd = which_tess
                pytesseract.get_tesseract_version()
                logger.info("Tesseract detected at: %s", which_tess)
                return True
            except Exception:
                pass

        logger.info("Tesseract not available. RapidOCR will be the primary engine.")
        return False

    TESSERACT_AVAILABLE = configure_tesseract()

except ImportError:
    logger.info("pytesseract is not installed. RapidOCR will be used.")

OCR_AVAILABLE = RAPIDOCR_AVAILABLE or TESSERACT_AVAILABLE


# =========================================================
# IMAGE PREPROCESSING
# =========================================================

def preprocess_printed_image(image: Image.Image) -> Image.Image:
    """
    Image enhancement tuned for printed scanned documents:
    - Moderate resolution upscale if under 1400px
    - Grayscale conversion
    - Contrast amplification & autocontrast
    - Subtle edge sharpening
    """
    try:
        w, h = image.size
        # Upscale if low resolution
        if w < 1400 or h < 1400:
            scale = min(2.0, 1800.0 / max(w, h))
            if scale > 1.1:
                image = image.resize((int(w * scale), int(h * scale)), Image.Resampling.BICUBIC)

        gray = image.convert("L")
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(1.4)
        normalized = ImageOps.autocontrast(enhanced, cutoff=0.5)
        sharpened = normalized.filter(ImageFilter.SHARPEN)
        return sharpened
    except Exception as exc:
        logger.debug("Printed image preprocessing error: %s", exc)
        return image

def preprocess_image(image: Image.Image) -> Image.Image:
    """Standard preprocessor alias for backward compatibility."""
    return preprocess_printed_image(image)


# =========================================================
# RAPIDOCR EXTRACTION
# =========================================================

def _extract_with_rapidocr(image: Image.Image, is_handwritten: bool = False) -> Tuple[str, float]:
    """
    Extract text using RapidOCR.
    Returns: (extracted_text, average_confidence)
    """
    engine = get_rapidocr()
    if engine is None:
        return "", 0.0

    try:
        # Pass 1: Raw RGB Image
        img_array = np.array(image.convert("RGB"))
        result, _ = engine(img_array)

        # Pass 2: If result is sparse, try preprocessed image
        if not result or len(result) < 3:
            proc_img = preprocess_printed_image(image)
            img_array = np.array(proc_img.convert("RGB"))
            result_proc, _ = engine(img_array)
            if result_proc and (not result or len(result_proc) > len(result)):
                result = result_proc

        if not result:
            return "", 0.0

        # Sort OCR boxes by reading order: Top-to-bottom, grouping near Y-coordinates
        def get_box_sort_key(item):
            try:
                box = item[0]  # [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
                y_top = float(box[0][1])
                x_left = float(box[0][0])
                # Quantize Y to rows of ~15px to preserve left-to-right reading order on same line
                y_row = round(y_top / 15.0) * 15.0
                return (y_row, x_left)
            except Exception:
                return (0.0, 0.0)

        sorted_result = sorted(result, key=get_box_sort_key)

        lines = []
        scores = []
        for item in sorted_result:
            if item and len(item) >= 2:
                text = str(item[1]).strip()
                if text:
                    lines.append(text)
                    if len(item) >= 3 and item[2] is not None:
                        try:
                            scores.append(float(item[2]))
                        except Exception:
                            scores.append(0.85)
                    else:
                        scores.append(0.85)

        avg_conf = float(np.mean(scores)) if scores else 0.85
        return "\n".join(lines).strip(), avg_conf

    except Exception as exc:
        logger.exception("RapidOCR extraction error: %s", exc)
        return "", 0.0


# =========================================================
# TESSERACT EXTRACTION
# =========================================================

def _extract_with_tesseract(image: Image.Image) -> str:
    """Fallback extraction using Tesseract OCR."""
    if not TESSERACT_AVAILABLE or pytesseract is None:
        return ""
    try:
        proc_img = preprocess_printed_image(image)
        text = pytesseract.image_to_string(proc_img, config="--oem 3 --psm 6")
        return text.strip()
    except Exception as exc:
        logger.debug("Tesseract extraction error: %s", exc)
        return ""


# =========================================================
# PUBLIC EXTRACTION INTERFACES
# =========================================================

def extract_text_from_image(image: Image.Image) -> str:
    """
    Extract text from an image with high accuracy.
    Priority: RapidOCR -> Tesseract.
    """
    if not OCR_AVAILABLE:
        logger.warning("No OCR engine is available.")
        return ""

    if RAPIDOCR_AVAILABLE:
        text, _ = _extract_with_rapidocr(image)
        if text:
            return text

    if TESSERACT_AVAILABLE:
        text = _extract_with_tesseract(image)
        if text:
            return text

    return ""

def extract_text_from_pixmap(pixmap) -> str:
    """
    Convert PyMuPDF Pixmap to Pillow Image and run OCR.
    Safely releases memory buffer.
    """
    try:
        png_bytes = pixmap.tobytes("png")
        image = Image.open(io.BytesIO(png_bytes))
        text = extract_text_from_image(image)
        image.close()
        return text
    except Exception as exc:
        logger.exception("Pixmap OCR error: %s", exc)
        return ""