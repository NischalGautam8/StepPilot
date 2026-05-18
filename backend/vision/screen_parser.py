import asyncio
import logging
import cv2
import numpy as np

from vision.ocr_engine import OCREngine
from vision.a11y_reader import A11yReader
from vision.element_merger import ElementMerger

logger = logging.getLogger("cursor-king-backend.screen-parser")

class ScreenParser:
    """
    ScreenParser acts as a facade orchestrating OCR text extraction 
    and Accessibility UIA trees in parallel, applying advanced preprocessing,
    and merging the results into a unified UIElement registry.
    """
    def __init__(self, use_gpu: bool = False, det_db_thresh: float = 0.3, iou_threshold: float = 0.7, max_a11y_depth: int = 6):
        self.ocr_engine = OCREngine(use_gpu=use_gpu, det_db_thresh=det_db_thresh)
        self.a11y_reader = A11yReader(max_depth=max_a11y_depth)
        self.merger = ElementMerger(iou_threshold=iou_threshold)

    @staticmethod
    def enhance_contrast(image_np: np.ndarray) -> np.ndarray:
        """
        Enhances the contrast of the screenshot using LAB space CLAHE,
        making it significantly easier for OCR to read text in various themes.
        """
        try:
            # Convert to LAB color space
            lab = cv2.cvtColor(image_np, cv2.COLOR_BGR2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            cl = clahe.apply(l_channel)
            
            # Merge back and convert to BGR
            limg = cv2.merge((cl, a_channel, b_channel))
            enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
            return enhanced
        except Exception as e:
            logger.warning(f"Contrast enhancement failed: {e}. Using raw image.")
            return image_np

    def _run_ocr(self, image_np: np.ndarray, orig_w: int, orig_h: int) -> list[dict]:
        """
        Applies contrast enhancement, resizes the image to 1280x720 for OCR efficiency,
        runs OCR, and scales resulting coordinates back to original size.
        """
        try:
            enhanced = self.enhance_contrast(image_np)
            
            # Target resolution for OCR
            target_w, target_h = 1280, 720
            resized = cv2.resize(enhanced, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
            
            # Calculate scale ratios
            scale_x = orig_w / float(target_w)
            scale_y = orig_h / float(target_h)
            
            # Run OCR on resized image
            ocr_raw = self.ocr_engine.ocr_image(resized)
            
            # Scale coordinates back to original resolution
            scaled_results = []
            for item in ocr_raw:
                x, y, w, h = item["bbox"]
                
                x_scaled = int(round(x * scale_x))
                y_scaled = int(round(y * scale_y))
                w_scaled = int(round(w * scale_x))
                h_scaled = int(round(h * scale_y))
                
                scaled_results.append({
                    "text": item["text"],
                    "bbox": [x_scaled, y_scaled, w_scaled, h_scaled],
                    "confidence": item["confidence"]
                })
                
            return scaled_results
        except Exception as e:
            logger.error(f"Error in OCR pipeline runner: {e}", exc_info=True)
            return []

    async def parse_screen(self, image_np: np.ndarray) -> list[dict]:
        """
        Parses a screenshot by concurrently executing the OCR pipeline 
        and UIA Accessibility tree reading, then merges results.
        """
        orig_h, orig_w = image_np.shape[:2]
        logger.info(f"Parsing screen size {orig_w}x{orig_h} in parallel...")

        # Concurrently run OCR and Accessibility reading in thread pools
        ocr_task = asyncio.to_thread(self._run_ocr, image_np, orig_w, orig_h)
        a11y_task = asyncio.to_thread(self.a11y_reader.get_active_window_elements, orig_w, orig_h)

        ocr_results, a11y_results = await asyncio.gather(ocr_task, a11y_task)

        # Merge the results
        unified_elements = self.merger.merge(ocr_results, a11y_results)
        
        logger.info(f"Screen parsing complete. Generated {len(unified_elements)} final UIElements.")
        return unified_elements
