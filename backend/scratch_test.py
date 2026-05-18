import cv2
import numpy as np
import logging
import asyncio
from vision.screen_parser import ScreenParser

# Enable detailed logging to catch warnings and errors
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

async def test():
    print("=== STARTING DIAGNOSTIC VISION TEST ===")
    parser = ScreenParser()
    
    # Create a 1920x1080 dummy image
    img = np.ones((1080, 1920, 3), dtype=np.uint8) * 255
    
    # Draw simple visual text elements
    cv2.putText(img, "TEST STAGE PANEL", (100, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)
    cv2.putText(img, "Username:", (100, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (50, 50, 50), 2)
    cv2.putText(img, "Password:", (100, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (50, 50, 50), 2)
    cv2.rectangle(img, (250, 175), (550, 215), (0, 0, 0), 2) # Draw input box 1
    cv2.rectangle(img, (250, 275), (550, 315), (0, 0, 0), 2) # Draw input box 2
    
    print("\n[Diagnostic] Executing parse_screen concurrently...")
    elements = await parser.parse_screen(img)
    
    print(f"\n[Diagnostic] Parse completed! Extracted {len(elements)} elements:")
    for elem in elements:
        print(f" -> {elem}")
    print("=== DIAGNOSTIC VISION TEST FINISHED ===")

if __name__ == "__main__":
    asyncio.run(test())
