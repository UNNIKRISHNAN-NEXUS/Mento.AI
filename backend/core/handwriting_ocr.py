# -*- coding: utf-8 -*-
"""
Mento.AI English Handwriting OCR Engine
Preprocesses images and PDF pages containing handwritten English text
(cursive, print, class notes, board photos, scribbles) and extracts clean text using OCR.
"""

import logging
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from typing import Optional

from backend.core.ocr_engine import get_rapidocr, RAPIDOCR_AVAILABLE, TESSERACT_AVAILABLE, pytesseract
from backend.core.post_processor import clean_and_normalize_text

logger = logging.getLogger("handwriting_ocr")

def preprocess_handwritten_image(image: Image.Image) -> Image.Image:
    """
    Applies non-destructive image enhancement tuned for handwritten notes:
    - Upscale low-resolution crops
    - Grayscale conversion
    - Contrast amplification (prevents faint pen strokes from disappearing)
    - Autocontrast normalization (preserves background gradient / line structure)
    - Sharpness enhancement without aggressive binarization
    """
    try:
        w, h = image.size
        if w < 1400 or h < 1400:
            scale = min(2.0, 1800.0 / max(w, h))
            if scale > 1.1:
                image = image.resize((int(w * scale), int(h * scale)), Image.Resampling.BICUBIC)

        gray = image.convert("L")
        
        # Contrast amplification
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(1.6)
        
        # Autocontrast to maximize dynamic range
        normalized = ImageOps.autocontrast(enhanced, cutoff=0.5)
        
        # Sharpness Boost for character edges
        sharp_enhancer = ImageEnhance.Sharpness(normalized)
        sharp = sharp_enhancer.enhance(1.8)
        
        return sharp
    except Exception as e:
        logger.warning(f"Error during handwriting image preprocessing: {e}")
        return image

def extract_handwritten_text(image: Image.Image) -> str:
    """
    Extract handwritten English text from PIL Image using multi-pass RapidOCR / Tesseract
    followed by post-processing cleanup.
    """
    try:
        prep_img = preprocess_handwritten_image(image)
        extracted_text = ""
        
        engine = get_rapidocr()
        if engine is not None:
            # Pass 1: Preprocessed Image
            img_np = np.array(prep_img.convert("RGB"))
            ocr_result, _ = engine(img_np)
            if ocr_result:
                lines = [str(line[1]).strip() for line in ocr_result if line and len(line) >= 2 and str(line[1]).strip()]
                extracted_text = "\n".join(lines)
                
            # Pass 2: Raw Image fallback if Pass 1 yielded sparse results
            if len(extracted_text.strip()) < 30:
                raw_np = np.array(image.convert("RGB"))
                raw_ocr, _ = engine(raw_np)
                if raw_ocr:
                    raw_lines = [str(line[1]).strip() for line in raw_ocr if line and len(line) >= 2 and str(line[1]).strip()]
                    raw_text = "\n".join(raw_lines)
                    if len(raw_text.strip()) > len(extracted_text.strip()):
                        extracted_text = raw_text
                        
        # Fallback to Tesseract OCR if RapidOCR produced nothing or is unavailable
        if not extracted_text.strip() and TESSERACT_AVAILABLE and pytesseract is not None:
            try:
                config = r'--oem 3 --psm 6'
                extracted_text = pytesseract.image_to_string(prep_img, config=config)
            except Exception as tess_err:
                logger.debug(f"Tesseract handwriting OCR fallback error: {tess_err}")
                
        # Run post-processor to fix spelling, line breaks, and misalignments
        cleaned = clean_and_normalize_text(extracted_text)
        return cleaned
        
    except Exception as e:
        logger.error(f"Failed to extract handwritten text: {e}")
        return ""
