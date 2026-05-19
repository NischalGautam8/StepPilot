import logging
import base64
from io import BytesIO
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from PIL import Image
import cv2
import numpy as np

from core.ws_manager import ws_manager, MessageType
from core.settings_manager import apply_settings
from vision.screen_parser import ScreenParser

# Apply settings from config and keyring on startup
apply_settings()

# Initialize ScreenParser & TaskPlanner lazily to avoid heavy model loading on startup
screen_parser = None
task_planner = None
last_parsed_elements = []
last_screenshot_bytes = None


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("cursor-king-backend")

app = FastAPI(
    title="StepPilot (Cursor-King) Backend",
    description="Python FastAPI backend for UI parsing, OCR, and planning",
    version="0.1.0"
)

# Enable CORS for frontend accessibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Message handlers
async def handle_screenshot(message: dict, client_id: str):
    """Handle screenshot messages from Rust client and run element parsing pipeline"""
    global screen_parser, last_parsed_elements, last_screenshot_bytes
    try:
        screenshot_data = message.get("data", "")
        width = message.get("width", 0)
        height = message.get("height", 0)
        timestamp = message.get("timestamp", 0)
        
        if not screenshot_data:
            logger.warning("Received empty screenshot data")
            return
            
        # Decode base64 JPEG
        image_bytes = base64.b64decode(screenshot_data)
        
        # Load image via OpenCV for vision processing
        file_bytes = np.frombuffer(image_bytes, dtype=np.uint8)
        image_np = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        
        if image_np is None:
            raise ValueError("Failed to decode screenshot bytes into image buffer")
            
        logger.info(f"Received screenshot: {width}x{height}, size: {len(image_bytes)} bytes, timestamp: {timestamp}")
        
        # Lazy initialization of ScreenParser
        if screen_parser is None:
            logger.info("First screenshot received. Initializing ScreenParser...")
            screen_parser = ScreenParser()
            
        # Process screenshot (Run OCR + A11y and merge results with Sprint 9 Preprocessing)
        preprocessed_np, crop_bounds = screen_parser.preprocess_image(image_np)
        
        # Convert preprocessed_np to JPEG bytes for downstream LLM vision consumption
        _, encoded_img = cv2.imencode(".jpg", preprocessed_np)
        last_screenshot_bytes = encoded_img.tobytes()
        
        detected_elements = await screen_parser.parse_screen(preprocessed_np, crop_bounds)
        
        # Cache results for downstream LLM planning
        last_parsed_elements = detected_elements
        
        # Log detected elements to stdout
        logger.info(f"Screenshot parsed. Found {len(detected_elements)} elements.")
        for elem in detected_elements[:10]:
            logger.info(f" - [{elem['source'].upper()}] ID={elem['id']} Type={elem['type']} Text='{elem['text']}' BBox={elem['bbox']}")
            
        # Acknowledge receipt and send parsed elements back to client
        await ws_manager.send_message({
            "type": MessageType.ACK,
            "received": "screenshot",
            "width": width,
            "height": height,
            "size_bytes": len(image_bytes),
            "elements": detected_elements
        }, client_id)
        
    except Exception as e:
        logger.error(f"Error handling and parsing screenshot: {e}", exc_info=True)
        await ws_manager.send_error(f"Screenshot processing error: {str(e)}", client_id)



async def handle_task_start(message: dict, client_id: str):
    """Handle task start messages from frontend, running LLM planning"""
    global task_planner, last_parsed_elements, last_screenshot_bytes
    try:
        query = message.get("query", "")
        timestamp = message.get("timestamp", 0)
        
        logger.info(f"Task started: '{query}' at {timestamp}")
        
        # Lazy initialization of TaskPlanner
        if task_planner is None:
            logger.info("Initializing TaskPlanner...")
            from task.planner import TaskPlanner
            task_planner = TaskPlanner()
        else:
            task_planner.context_manager.clear()
            
        # Generate the structured plan using the planner
        plan = await task_planner.plan_task(
            query=query,
            elements=last_parsed_elements,
            image_bytes=last_screenshot_bytes
        )
        
        logger.info(f"Task plan generated successfully for query '{query}': {len(plan.get('steps', []))} steps found.")
        
        # Send planning result as the WebSocket response
        await ws_manager.send_message({
            "type": MessageType.ACK,
            "received": "task_start",
            "query": query,
            "plan": plan
        }, client_id)
        
    except Exception as e:
        logger.error(f"Error handling task start planning: {e}", exc_info=True)
        await ws_manager.send_error(f"Task start error: {str(e)}", client_id)


async def handle_cursor_pos(message: dict, client_id: str):
    """Handle cursor position updates from Rust"""
    x = message.get("x", 0)
    y = message.get("y", 0)
    timestamp = message.get("timestamp", 0)
    
    # Log at debug level to avoid spam
    logger.debug(f"Cursor position: ({x}, {y}) at {timestamp}")
    
    # TODO: Use cursor position for guidance rendering (Sprint 6)


async def handle_get_settings(message: dict, client_id: str):
    """Handle get_settings message from frontend and return current settings"""
    try:
        from core.settings_manager import load_settings
        settings = load_settings()
        await ws_manager.send_message({
            "type": "settings_data",
            "settings": settings
        }, client_id)
        logger.info(f"Sent settings data to client: {client_id}")
    except Exception as e:
        logger.error(f"Error handling get_settings: {e}", exc_info=True)
        await ws_manager.send_error(f"Get settings error: {str(e)}", client_id)


async def handle_save_settings(message: dict, client_id: str):
    """Handle save_settings message from frontend and update config"""
    try:
        from core.settings_manager import save_settings
        settings = message.get("settings", {})
        save_settings(settings)
        await ws_manager.send_message({
            "type": "settings_saved",
            "status": "success"
        }, client_id)
        logger.info(f"Saved settings updated by client: {client_id}")
    except Exception as e:
        logger.error(f"Error handling save_settings: {e}", exc_info=True)
        await ws_manager.send_error(f"Save settings error: {str(e)}", client_id)


async def handle_step_result(message: dict, client_id: str):
    """Handle step execution updates from client frontend"""
    global task_planner
    try:
        if task_planner is None:
            from task.planner import TaskPlanner
            task_planner = TaskPlanner()
            
        step_number = message.get("step_number", 0)
        description = message.get("description", "")
        action = message.get("action", "")
        status = message.get("status", "")
        details = message.get("details", "")
        
        task_planner.context_manager.add_step_result(
            step_number=step_number,
            description=description,
            action=action,
            status=status,
            details=details
        )
        logger.info(f"Registered step result: Step {step_number} ({action}) -> {status}")
    except Exception as e:
        logger.error(f"Error handling step_result: {e}", exc_info=True)


# Register message handlers
ws_manager.register_handler(MessageType.SCREENSHOT, handle_screenshot)
ws_manager.register_handler(MessageType.TASK_START, handle_task_start)
ws_manager.register_handler(MessageType.CURSOR_POS, handle_cursor_pos)
ws_manager.register_handler("get_settings", handle_get_settings)
ws_manager.register_handler("save_settings", handle_save_settings)
ws_manager.register_handler("step_result", handle_step_result)


@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "service": "steppilot-backend",
        "version": "0.1.0",
        "active_connections": len(ws_manager.active_connections)
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket communication bridge between Rust client and Python server."""
    client_id = "rust-client"  # Could be made dynamic based on connection params
    
    try:
        await ws_manager.connect(websocket, client_id)
        await ws_manager.listen(websocket, client_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        ws_manager.disconnect(client_id)


if __name__ == "__main__":
    # Start the FastAPI app using Uvicorn on port 8765
    logger.info("Starting FastAPI Uvicorn server on http://127.0.0.1:8765")
    uvicorn.run("main:app", host="127.0.0.1", port=8765, log_level="info")
