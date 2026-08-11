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
    Applies image enhancement algorithms tuned for handwriting:
    - Grayscale conversion
    - Contrast amplification & Sharpness boost
    - Binarization / noise reduction for pen/pencil strokes
    """
    try:
        # Convert to Grayscale
        gray = image.convert("L")
        
        # Increase Contrast (amplifies light pencil/pen strokes)
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(2.0)
        
        # Increase Sharpness
        sharp_enhancer = ImageEnhance.Sharpness(enhanced)
        sharp = sharp_enhancer.enhance(2.5)
        
        # Apply subtle Median Filter to reduce paper noise/grain
        filtered = sharp.filter(ImageFilter.MedianFilter(size=3))
        
        # Adaptive Binarization (Numpy Thresholding)
        img_np = np.array(filtered)
        # Calculate adaptive mean threshold
        mean_val = np.mean(img_np)
        thresh_val = max(100, int(mean_val * 0.85))
        
        # Binarize: dark strokes -> 0, light background -> 255
        bin_np = np.where(img_np < thresh_val, 0, 255).astype(np.uint8)
        
        bin_image = Image.fromarray(bin_np)
        return bin_image
        
    except Exception as e:
        logger.warning(f"Error during handwriting image preprocessing: {e}")
        return image

def extract_handwritten_text(image: Image.Image) -> str:
    """
    Extract handwritten English text from PIL Image using RapidOCR / Tesseract.
    """
    try:
        # Preprocess image for handwriting recognition
        prep_img = preprocess_handwritten_image(image)
        
        extracted_text = ""
        
        # 1. Try RapidOCR (Primary Fast Engine)
        from backend.core.ocr_engine import OCR_ENGINE_INSTANCE
        if OCR_ENGINE_INSTANCE is not None:
            img_np = np.array(prep_img)
            ocr_result, _ = OCR_ENGINE_INSTANCE(img_np)
            if ocr_result:
                lines = [line[1] for line in ocr_result if line and len(line) >= 2]
                extracted_text = "\n".join(lines)
                
        # 2. Fallback to Tesseract OCR with Sparse Text / Handwriting PSM
        if not extracted_text.strip():
            try:
                import pytesseract
                # PSM 6: Assume a single uniform block of text
                # PSM 11: Sparse text / find as much text as possible
                config = r'--oem 3 --psm 6'
                extracted_text = pytesseract.image_to_string(prep_img, config=config)
            except Exception as tess_err:
                logger.debug(f"Tesseract handwriting OCR fallback error: {tess_err}")
                
        return extracted_text.strip()
        
    except Exception as e:
        logger.error(f"Failed to extract handwritten text: {e}")
        return ""
