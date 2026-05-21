import asyncio
import logging
import os
import cv2
import numpy as np
import time
import win32gui

from vision.ocr_engine import OCREngine
from vision.a11y_reader import A11yReader
from vision.element_merger import ElementMerger

logger = logging.getLogger("cursor-king-backend.screen-parser")

class ScreenParser:
    """
    ScreenParser facade orchestrating OCR text extraction and UIA Accessibility trees.
    Applies advanced pre-processing (cropping, scaling, contrast-enhancement) 
    and handles cache/privacy filtering.
    """
    def __init__(self, use_gpu: bool = False, det_db_thresh: float = 0.3, iou_threshold: float = 0.7, max_a11y_depth: int = 6):
        # OCR engine is created lazily — PaddleOCR is never loaded unless OCR is actually needed
        self._ocr_engine = None
        self._use_gpu = use_gpu
        self._det_db_thresh = det_db_thresh
        self.a11y_reader = A11yReader(max_depth=max_a11y_depth)
        self.merger = ElementMerger(iou_threshold=iou_threshold)
        
        # Lazy initialization of UIDetector (Sprint 11)
        self.ui_detector = None
        self.use_gpu = use_gpu
        
        # In-memory element cache (Sprint 9)
        self.cache_elements = None
        self.cache_time = 0.0
        self.cache_hwnd = 0
    
    @property
    def ocr_engine(self):
        """Lazy-create OCR engine on first access to avoid loading PaddleOCR at startup."""
        if self._ocr_engine is None:
            logger.info("Creating OCREngine on first use...")
            self._ocr_engine = OCREngine(use_gpu=self._use_gpu, det_db_thresh=self._det_db_thresh)
        return self._ocr_engine

    @staticmethod
    def enhance_contrast(image_np: np.ndarray) -> np.ndarray:
        """
        Enhances contrast of the screenshot using LAB CLAHE, facilitating OCR in various themes.
        """
        try:
            lab = cv2.cvtColor(image_np, cv2.COLOR_BGR2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            cl = clahe.apply(l_channel)
            
            limg = cv2.merge((cl, a_channel, b_channel))
            enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
            return enhanced
        except Exception as e:
            logger.warning(f"Contrast enhancement failed: {e}. Using raw image.")
            return image_np

    def redact_sensitive_data(self, elements: list[dict]) -> list[dict]:
        """
        Redacts labels/inputs containing password or other credential signatures.
        """
        sensitive_keywords = ["password", "secret", "cvv", "creditcard", "ssn", "pin", "key"]
        redacted_count = 0
        for elem in elements:
            name = (elem.get("name") or "").lower()
            text = (elem.get("text") or "").lower()
            automation_id = (elem.get("automation_id") or "").lower()
            
            is_sensitive = (
                elem.get("type") == "Edit" and any(k in name or k in automation_id for k in sensitive_keywords)
            ) or any(k in text for k in sensitive_keywords)
            
            if is_sensitive:
                elem["text"] = "[REDACTED SENSITIVE INFO]"
                if "name" in elem and elem["name"]:
                    elem["name"] = "[REDACTED]"
                redacted_count += 1
        if redacted_count > 0:
            logger.info(f"Redacted {redacted_count} elements containing potentially sensitive keywords.")
        return elements

    def preprocess_image(self, image_np: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int]]:
        """
        Crops screenshot to foreground window bounds, enhances contrast, and resizes to max 1280x720.
        Returns: (preprocessed_image_np, (x1, y1, x2, y2) bounds)
        """
        img_h, img_w = image_np.shape[:2]
        x1, y1, x2, y2 = 0, 0, img_w, img_h
        
        # 1. Crop to active window bounds
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd and not win32gui.IsIconic(hwnd) and hwnd != win32gui.GetDesktopWindow():
                rect = win32gui.GetWindowRect(hwnd)
                left, top, right, bottom = rect
                
                x1 = max(0, min(left, img_w - 1))
                y1 = max(0, min(top, img_h - 1))
                x2 = max(0, min(right, img_w))
                y2 = max(0, min(bottom, img_h))
                
                if (x2 - x1) > 100 and (y2 - y1) > 100:
                    logger.info(f"Cropping screen to active window bounds: left={x1}, top={y1}, width={x2-x1}, height={y2-y1}")
                    image_np = image_np[y1:y2, x1:x2]
                else:
                    x1, y1, x2, y2 = 0, 0, img_w, img_h
        except Exception as e:
            logger.warning(f"Failed to crop to active window: {e}. Using full screenshot.")
            x1, y1, x2, y2 = 0, 0, img_w, img_h
            
        # 2. Skip contrast enhancement for desktop screenshots — they have crisp text
        # on solid backgrounds, so CLAHE just wastes CPU cycles.
        # Only enable for unusual scenarios (e.g., remote desktop, dark themes)
        # enhanced = self.enhance_contrast(image_np)
        enhanced = image_np
        
        # 3. Resize maintaining aspect ratio (960x540 is sufficient for desktop OCR)
        h, w = enhanced.shape[:2]
        max_w, max_h = 960, 540
        scale = min(max_w / w, max_h / h)
        
        if scale < 1.0:
            new_w = int(round(w * scale))
            new_h = int(round(h * scale))
            logger.info(f"Resizing cropped screen from {w}x{h} to {new_w}x{new_h} (scale={scale:.2f})")
            preprocessed = cv2.resize(enhanced, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            preprocessed = enhanced
            
        return preprocessed, (x1, y1, x2, y2)

    def _run_ocr(self, preprocessed_np: np.ndarray, crop_x1: int, crop_y1: int) -> list[dict]:
        """
        Runs OCR on the cropped, preprocessed image and scales coordinates back to screen space.
        """
        try:
            # We assume preprocessed_np is already contrast-enhanced and resized.
            # We only need to run OCR and reverse the scaling + crop offsets.
            # Let's get original sizes (which correspond to the cropped region's original size)
            # Wait, how to find scale factor?
            # In preprocess_image, the aspect ratio resized size is preprocessed_np.shape
            # The cropped region size is (crop_x2 - crop_x1, crop_y2 - crop_y1)
            # Let's compute scaling factor:
            # We don't have crop_x2/crop_y2 here, but we can compute it since we know the aspect ratio scale.
            # Wait, a cleaner way is to simply measure the scale between preprocessed_np and cropped dimensions!
            # But we can calculate scale from target width/height or pass it.
            # Let's pass scale, or let _run_ocr calculate scale:
            pass
        except Exception:
            pass
        return []

    def run_ocr_on_preprocessed(self, preprocessed_np: np.ndarray, crop_bounds: tuple[int, int, int, int]) -> list[dict]:
        """
        Runs OCR on preprocessed image and maps coordinates back to absolute screen space.
        """
        try:
            x1, y1, x2, y2 = crop_bounds
            crop_w = x2 - x1
            crop_h = y2 - y1
            
            prep_h, prep_w = preprocessed_np.shape[:2]
            scale_x = crop_w / float(prep_w)
            scale_y = crop_h / float(prep_h)
            
            ocr_raw = self.ocr_engine.ocr_image(preprocessed_np)
            scaled_results = []
            for item in ocr_raw:
                ox, oy, ow, oh = item["bbox"]
                
                # Scale back to cropped coordinates
                ox_scaled = int(round(ox * scale_x))
                oy_scaled = int(round(oy * scale_y))
                ow_scaled = int(round(ow * scale_x))
                oh_scaled = int(round(oh * scale_y))
                
                # Offset to absolute screen coordinate space
                abs_x = ox_scaled + x1
                abs_y = oy_scaled + y1
                
                scaled_results.append({
                    "text": item["text"],
                    "bbox": [abs_x, abs_y, ow_scaled, oh_scaled],
                    "confidence": item["confidence"]
                })
            return scaled_results
        except Exception as e:
            logger.error(f"Error in OCR preprocessed pipeline: {e}", exc_info=True)
            return []

    def run_ui_detector_on_preprocessed(self, preprocessed_np: np.ndarray, crop_bounds: tuple[int, int, int, int], existing_elements: list[dict] = None) -> list[dict]:
        """
        Runs OmniParser icon detection on preprocessed image and maps coordinates back to absolute screen space.
        Uses existing_elements to avoid captioning icons that overlap with text/labeled components.
        """
        if self.ui_detector is None:
            from vision.ui_detector import UIDetector
            use_gpu = os.getenv("USE_GPU", "false").lower() == "true"
            logger.info(f"Initializing UIDetector with use_gpu={use_gpu}...")
            self.ui_detector = UIDetector(use_gpu=use_gpu)
            
        try:
            x1, y1, x2, y2 = crop_bounds
            crop_w = x2 - x1
            crop_h = y2 - y1
            
            prep_h, prep_w = preprocessed_np.shape[:2]
            scale_x = crop_w / float(prep_w)
            scale_y = crop_h / float(prep_h)
            
            # Map existing absolute-space elements back to preprocessed space
            mapped_existing = []
            if existing_elements:
                for elem in existing_elements:
                    eb = elem.get("bbox", [0, 0, 0, 0])
                    rx = eb[0] - x1
                    ry = eb[1] - y1
                    rw = eb[2]
                    rh = eb[3]
                    
                    px = rx / scale_x if scale_x > 0 else rx
                    py = ry / scale_y if scale_y > 0 else ry
                    pw = rw / scale_x if scale_x > 0 else rw
                    ph = rh / scale_y if scale_y > 0 else rh
                    
                    mapped_existing.append({
                        "text": elem.get("text") or elem.get("name") or "",
                        "bbox": [px, py, pw, ph]
                    })
            
            # Detect icons on the preprocessed image with mapped existing elements
            raw_icons = self.ui_detector.detect_icons(preprocessed_np, existing_elements=mapped_existing)
            
            scaled_results = []
            for item in raw_icons:
                ox, oy, ow, oh = item["bbox"]
                
                # Scale back to cropped coordinates
                ox_scaled = int(round(ox * scale_x))
                oy_scaled = int(round(oy * scale_y))
                ow_scaled = int(round(ow * scale_x))
                oh_scaled = int(round(oh * scale_y))
                
                # Offset to absolute screen coordinate space
                abs_x = ox_scaled + x1
                abs_y = oy_scaled + y1
                
                scaled_results.append({
                    "type": item["type"],
                    "text": item["text"],
                    "bbox": [abs_x, abs_y, ow_scaled, oh_scaled],
                    "confidence": item["confidence"],
                    "source": item["source"],
                    "enabled": item["enabled"],
                    "automation_id": item["automation_id"]
                })
            return scaled_results
        except Exception as e:
            logger.error(f"Error in OmniParser preprocessed pipeline: {e}", exc_info=True)
            return []

    async def parse_screen(self, preprocessed_np: np.ndarray, crop_bounds: tuple[int, int, int, int]) -> list[dict]:
        """
        Parses screenshot using A11y-first strategy for near-instant results.
        
        OCR Strategy (controlled by OCR_MODE env var):
        - "auto" (default): Run A11y first. Only run OCR if A11y returns < 10 elements.
        - "always": Always run both A11y and OCR (slow but thorough).
        - "never": Only use A11y tree, skip OCR entirely (fastest).
        """
        total_t0 = time.time()
        hwnd = win32gui.GetForegroundWindow()
        current_time = time.time()
        
        # Cache Hit Check (TTL 10 seconds & same window)
        if self.cache_elements is not None and (current_time - self.cache_time < 10.0) and (hwnd == self.cache_hwnd):
            logger.info("Using cached screen elements (TTL < 10s and same active window).")
            return self.cache_elements
            
        x1, y1, x2, y2 = crop_bounds
        logger.info(f"Parsing active window screen slice {x2-x1}x{y2-y1}...")
        
        # Fetch display bounds for UIA Sweep
        orig_w = 1920
        orig_h = 1080
        try:
            desktop_hwnd = win32gui.GetDesktopWindow()
            _, _, dw, dh = win32gui.GetWindowRect(desktop_hwnd)
            orig_w, orig_h = dw, dh
        except Exception:
            pass
        
        ocr_mode = os.getenv("OCR_MODE", "auto").lower()
        
        # ── Stage 1: Accessibility Tree (fast, ~200-800ms) ──
        t0 = time.time()
        a11y_results = self.a11y_reader.get_active_window_elements(orig_w, orig_h)
        a11y_ms = (time.time() - t0) * 1000
        logger.info(f"[TIMING] A11y tree: {a11y_ms:.0f}ms → {len(a11y_results)} elements")
        
        # ── Stage 2: OCR (conditional, can be slow) ──
        ocr_results = []
        should_run_ocr = False
        
        if ocr_mode == "always":
            should_run_ocr = True
        elif ocr_mode == "never":
            should_run_ocr = False
        else:  # "auto" — only run OCR if A11y didn't find enough
            # If the A11y tree has enough interactive elements, skip OCR entirely.
            # Desktop apps with proper accessibility (Chrome, VS Code, Explorer, etc.)
            # typically expose 50-200+ UIA elements. If we got < 10, the app likely
            # has poor accessibility and OCR is needed as a fallback.
            MIN_A11Y_ELEMENTS = 10
            if len(a11y_results) < MIN_A11Y_ELEMENTS:
                should_run_ocr = True
                logger.info(f"A11y returned only {len(a11y_results)} elements (< {MIN_A11Y_ELEMENTS}). Falling back to OCR...")
            else:
                logger.info(f"A11y returned {len(a11y_results)} elements. Skipping OCR (sufficient coverage).")
        
        if should_run_ocr:
            t0 = time.time()
            ocr_results = self.run_ocr_on_preprocessed(preprocessed_np, crop_bounds)
            ocr_ms = (time.time() - t0) * 1000
            logger.info(f"[TIMING] OCR: {ocr_ms:.0f}ms → {len(ocr_results)} elements")
        
        # ── Stage 3: OmniParser Icon Detection (conditional) ──
        use_omniparser = os.getenv("USE_OMNIPARSER", "false").lower() == "true"
        icon_results = []
        if use_omniparser:
            t0 = time.time()
            logger.info("OmniParser is enabled. Running icon detection...")
            existing = ocr_results + a11y_results
            icon_results = self.run_ui_detector_on_preprocessed(preprocessed_np, crop_bounds, existing)
            omni_ms = (time.time() - t0) * 1000
            logger.info(f"[TIMING] OmniParser: {omni_ms:.0f}ms → {len(icon_results)} icons")
        
        # ── Stage 4: Merge & Finalize ──
        t0 = time.time()
        unified_elements = self.merger.merge(ocr_results, a11y_results, icon_results)
        unified_elements = self.redact_sensitive_data(unified_elements)
        merge_ms = (time.time() - t0) * 1000
        
        # Cache results
        self.cache_elements = unified_elements
        self.cache_time = current_time
        self.cache_hwnd = hwnd
        
        total_ms = (time.time() - total_t0) * 1000
        logger.info(
            f"[TIMING] Screen parsing complete in {total_ms:.0f}ms. "
            f"Extracted {len(unified_elements)} UIElements "
            f"(a11y={len(a11y_results)}, ocr={len(ocr_results)}, icons={len(icon_results)}, merge={merge_ms:.0f}ms)"
        )
        return unified_elements

