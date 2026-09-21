# -*- coding: utf-8 -*-
"""
Mento.AI English Handwriting OCR Engine
Preprocesses images and PDF pages containing handwritten English text
(cursive, print, class notes, board photos, scribbles) and extracts clean text using OCR.
"""

import logging
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from typing import Optional

logger = logging.getLogger("handwriting_ocr")

def preprocess_handwritten_image(image: Image.Image) -> Image.Image:
    """
    Applies image enhancement tuned for handwritten notes:
    - Grayscale conversion
    - Mild Contrast amplification (prevents light pen strokes from fading)
    - Sharpness enhancement without aggressive binarization
    """
    try:
        gray = image.convert("L")
        
        # Moderate Contrast amplification
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(1.8)
        
        # Sharpness Boost for character edges
        sharp_enhancer = ImageEnhance.Sharpness(enhanced)
        sharp = sharp_enhancer.enhance(2.0)
        
        return sharp
    except Exception as e:
        logger.warning(f"Error during handwriting image preprocessing: {e}")
        return image

def extract_handwritten_text(image: Image.Image) -> str:
    """
    Extract handwritten English text from PIL Image using multi-pass RapidOCR / Tesseract
    followed by post-processing cleanup.
    """
    from backend.core.post_processor import clean_and_normalize_text
    try:
        prep_img = preprocess_handwritten_image(image)
        extracted_text = ""
        
        from backend.core.ocr_engine import OCR_ENGINE_INSTANCE
        if OCR_ENGINE_INSTANCE is not None:
            # Pass 1: Preprocessed Image
            img_np = np.array(prep_img.convert("RGB"))
            ocr_result, _ = OCR_ENGINE_INSTANCE(img_np)
            if ocr_result:
                lines = [line[1] for line in ocr_result if line and len(line) >= 2]
                extracted_text = "\n".join(lines)
                
            # Pass 2: Raw Image fallback if Pass 1 yielded sparse results
            if len(extracted_text.strip()) < 30:
                raw_np = np.array(image.convert("RGB"))
                raw_ocr, _ = OCR_ENGINE_INSTANCE(raw_np)
                if raw_ocr:
                    raw_lines = [line[1] for line in raw_ocr if line and len(line) >= 2]
                    raw_text = "\n".join(raw_lines)
                    if len(raw_text.strip()) > len(extracted_text.strip()):
                        extracted_text = raw_text
                
        # Fallback to Tesseract OCR if RapidOCR produced nothing
        if not extracted_text.strip():
            try:
                import pytesseract
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
