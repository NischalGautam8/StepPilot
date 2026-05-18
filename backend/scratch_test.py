import cv2
import numpy as np
import logging
import asyncio
from vision.screen_parser import ScreenParser
from task.planner import TaskPlanner

# Enable detailed logging to catch warnings and errors
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

async def test():
    print("=== STARTING DIAGNOSTIC VISION & PLANNING TEST ===")
    
    # 1. Test Visual Capture & Parsing
    parser = ScreenParser()
    img = np.ones((1080, 1920, 3), dtype=np.uint8) * 255
    cv2.putText(img, "StepPilot Control Panel", (100, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)
    cv2.putText(img, "Connect", (100, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (50, 50, 50), 2)
    
    print("\n[Diagnostic] Executing parse_screen concurrently...")
    elements = await parser.parse_screen(img)
    print(f"[Diagnostic] Screen parsed successfully! Found {len(elements)} elements.")

    # 2. Test Task Planner Serialization
    print("\n[Diagnostic] Instantiating TaskPlanner...")
    planner = TaskPlanner()
    
    print("[Diagnostic] Testing UIElement serialization (Token-Minimization)...")
    serialized_str = planner.serialize_elements(elements)
    print("--- Serialized Compact Elements ---")
    print(serialized_str)
    print("-----------------------------------")
    
    # 3. Test Task Decomposer Pipeline Execution (with mock/env failover)
    user_query = "Click the Connect button to link the WebSocket"
    print(f"\n[Diagnostic] Planning task: '{user_query}'...")
    
    plan = await planner.plan_task(
        query=user_query,
        elements=elements,
        image_bytes=cv2.imencode('.jpg', img)[1].tobytes()
    )
    
    print("\n--- Generated Guidance Plan ---")
    import pprint
    pprint.pprint(plan)
    print("--------------------------------")
    
    print("\n=== DIAGNOSTIC VISION & PLANNING TEST FINISHED ===")

if __name__ == "__main__":
    asyncio.run(test())
