import os
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['FLAGS_use_onednn'] = '0'
os.environ['FLAGS_enable_onednn'] = '0'
os.environ['FLAGS_enable_mkldnn'] = '0'
os.environ['FLAGS_enable_pir_api'] = '0'
os.environ['FLAGS_enable_pir_in_executor'] = '0'

import logging
import cv2
import numpy as np

logger = logging.getLogger("cursor-king-backend.ocr-engine")

class OCREngine:
    """
    OCREngine encapsulates PaddleOCR v4 to extract text and bounding boxes
    from screenshots with customized sensitivity parameters.
    """
    def __init__(self, use_gpu: bool = False, det_db_thresh: float = 0.3):
        self.use_gpu = use_gpu
        self.det_db_thresh = det_db_thresh
        self.ocr = None
        self._initialized = False

    def _initialize_ocr(self):
        """
        Lazy-initializes PaddleOCR so that we don't block backend startup,
        allowing models to be downloaded or loaded on first use.
        """
        if self._initialized:
            return
        try:
            from paddleocr import PaddleOCR
            logger.info("Initializing PaddleOCR (use_gpu=%s, det_db_thresh=%s)...", self.use_gpu, self.det_db_thresh)
            self.ocr = PaddleOCR(
                lang="en",
                device="gpu" if self.use_gpu else "cpu",
                text_det_thresh=self.det_db_thresh,
                enable_mkldnn=False
            )
            self._initialized = True
            logger.info("PaddleOCR initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {e}", exc_info=True)
            self.ocr = None

    def ocr_image(self, image_np: np.ndarray) -> list[dict]:
        """
        Performs OCR on a numpy image (BGR format).
        Returns a list of dicts: [{"text": str, "bbox": [x, y, w, h], "confidence": float}]
        """
        self._initialize_ocr()
        if not self._initialized or self.ocr is None:
            logger.warning("OCREngine not initialized or failed to load. Returning empty results.")
            return []

        try:
            # Run OCR on the image
            # PaddleOCR expects a numpy array (BGR or RGB) or file path
            try:
                results = self.ocr.ocr(image_np, cls=True)
            except TypeError:
                results = self.ocr.ocr(image_np)
            
            parsed_results = []
            if not results or not results[0]:
                logger.info("OCREngine detected 0 text elements.")
                return parsed_results
                
            first_res = results[0]
            if isinstance(first_res, dict):
                # Handle dictionary format (PaddleX / PaddleOCR v5 format)
                texts = first_res.get("rec_texts", [])
                scores = first_res.get("rec_scores", [])
                boxes = first_res.get("rec_boxes", [])
                
                for i in range(len(texts)):
                    text = texts[i]
                    confidence = float(scores[i]) if i < len(scores) else 1.0
                    box = boxes[i] if i < len(boxes) else [0, 0, 0, 0]
                    
                    if len(box) == 4:
                        x_min, y_min, x_max, y_max = box
                        w = x_max - x_min
                        h = y_max - y_min
                    elif len(box) == 8 or (hasattr(box, "shape") and len(box.shape) == 2):
                        xs = [pt[0] for pt in box]
                        ys = [pt[1] for pt in box]
                        x_min = int(min(xs))
                        y_min = int(min(ys))
                        w = int(max(xs)) - x_min
                        h = int(max(ys)) - y_min
                    else:
                        x_min, y_min, w, h = 0, 0, 0, 0
                        
                    parsed_results.append({
                        "text": text,
                        "bbox": [int(x_min), int(y_min), int(w), int(h)],
                        "confidence": confidence
                    })
            else:
                # Handle standard list format: [[ [bbox_points, (text, confidence)], ... ]]
                for line in first_res:
                    bbox_points, (text, confidence) = line
                    xs = [pt[0] for pt in bbox_points]
                    ys = [pt[1] for pt in bbox_points]
                    x_min = int(min(xs))
                    y_min = int(min(ys))
                    x_max = int(max(xs))
                    y_max = int(max(ys))
                    w = x_max - x_min
                    h = y_max - y_min
                    
                    parsed_results.append({
                        "text": text,
                        "bbox": [x_min, y_min, w, h],
                        "confidence": float(confidence)
                    })
                
            logger.info(f"OCREngine detected {len(parsed_results)} text elements.")
            return parsed_results
            
        except Exception as e:
            logger.error(f"Error during OCR processing: {e}", exc_info=True)
            return []

