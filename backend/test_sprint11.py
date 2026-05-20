import os
import time
import asyncio
import numpy as np
import cv2
import logging

# Set up logging for output transparency
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test-sprint11")

# Configure environment variables to force enable OmniParser and Mock mode
os.environ["USE_OMNIPARSER"] = "true"
os.environ["USE_GPU"] = "false"

from vision.screen_parser import ScreenParser

async def run_sprint11_test():
    print("\n" + "="*50)
    print("      STEPPILOT SPRINT 11 VERIFICATION TEST      ")
    print("="*50)
    
    # 1. Initialize ScreenParser
    print("\n[Step 1] Initializing ScreenParser...")
    parser = ScreenParser()
    
    # 2. Check if dependencies are present
    from vision.ui_detector import UIDetector
    detector = UIDetector()
    print(f" -> Real OmniParser Dependencies Installed: {detector.has_dependencies}")
    if not detector.has_dependencies:
        print(" -> Running in Mock/Fallback Mode. Using rule-based icon simulator.")
    else:
        print(" -> Running with Real PyTorch & OmniParser ML pipeline.")
        
    # 3. Create mock image (1920x1080) for visual parser
    print("\n[Step 2] Creating synthetic high-resolution screenshot...")
    img = np.ones((1080, 1920, 3), dtype=np.uint8) * 240
    cv2.putText(img, "StepPilot Sprint 11 Dashboard", (50, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (50, 50, 50), 2)
    cv2.putText(img, "Settings Panel", (100, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    
    crop_bounds = (0, 0, 1920, 1080)
    
    # 4. Run ScreenParser with OmniParser ENABLED
    print("\n[Step 3] Running ScreenParser with OmniParser ENABLED (OCR + UIA + OmniParser)...")
    os.environ["USE_OMNIPARSER"] = "true"
    
    t0 = time.time()
    elements_on = await parser.parse_screen(img, crop_bounds)
    duration_on = (time.time() - t0) * 1000
    print(f" -> Done. Found {len(elements_on)} elements. Duration: {duration_on:.2f}ms")
    
    # 5. Clean-Room Merger Unit Test (No UIA/Active Window pollution)
    print("\n[Step 4] Running Clean-Room Merger Unit Test (OCR + OmniParser, empty A11y)...")
    ocr_results = parser.run_ocr_on_preprocessed(img, crop_bounds)
    icon_results = parser.run_ui_detector_on_preprocessed(img, crop_bounds)
    
    # Merge with empty A11y to verify icon detection is preserved completely
    clean_elements = parser.merger.merge(ocr_results, [], icon_results)
    print(f" -> Clean-room merge outputted {len(clean_elements)} elements.")
    
    icon_elements = [e for e in clean_elements if e["source"] == "omniparser" and e["type"].lower() == "icon"]
    print(f" -> Found {len(icon_elements)} standalone icons in clean room.")
    for idx, icon in enumerate(icon_elements):
        print(f"    - Clean Icon #{idx+1}: {icon['text']} at bbox {icon['bbox']} (conf={icon['confidence']:.2f})")
        
    # Assertions to verify mock elements are correct in clean room
    has_close_button = any("close" in icon["text"].lower() for icon in icon_elements)
    has_settings_gear = any("settings" in icon["text"].lower() for icon in icon_elements)
    
    print("\n" + "-"*50)
    print("VERIFICATION RESULTS (CLEAN ROOM):")
    print(f"[*] Close button detected:  {'PASS' if has_close_button else 'FAIL'}")
    print(f"[*] Settings gear detected: {'PASS' if has_settings_gear else 'FAIL'}")
    print("-"*50)
    
    if len(icon_elements) > 0 and has_close_button and has_settings_gear:
        print(">>> SPRINT 11 VERIFICATION SUCCESSFUL! <<<")
    else:
        print(">>> SPRINT 11 VERIFICATION FAILED! <<<")
    print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(run_sprint11_test())
