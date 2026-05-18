import logging
import base64
from io import BytesIO
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from PIL import Image

from core.ws_manager import ws_manager, MessageType

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
    """Handle screenshot messages from Rust client"""
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
        image = Image.open(BytesIO(image_bytes))
        
        logger.info(f"Received screenshot: {width}x{height}, size: {len(image_bytes)} bytes, timestamp: {timestamp}")
        logger.info(f"Image format: {image.format}, mode: {image.mode}, actual size: {image.size}")
        
        # TODO: Process screenshot with OCR and element detection (Sprint 3)
        # For now, just acknowledge receipt
        await ws_manager.send_message({
            "type": MessageType.ACK,
            "received": "screenshot",
            "width": width,
            "height": height,
            "size_bytes": len(image_bytes)
        }, client_id)
        
    except Exception as e:
        logger.error(f"Error handling screenshot: {e}", exc_info=True)
        await ws_manager.send_error(f"Screenshot processing error: {str(e)}", client_id)


async def handle_task_start(message: dict, client_id: str):
    """Handle task start messages from frontend"""
    try:
        query = message.get("query", "")
        timestamp = message.get("timestamp", 0)
        
        logger.info(f"Task started: '{query}' at {timestamp}")
        
        # TODO: Process task with LLM (Sprint 4)
        # For now, just acknowledge
        await ws_manager.send_message({
            "type": MessageType.ACK,
            "received": "task_start",
            "query": query
        }, client_id)
        
    except Exception as e:
        logger.error(f"Error handling task start: {e}", exc_info=True)
        await ws_manager.send_error(f"Task start error: {str(e)}", client_id)


async def handle_cursor_pos(message: dict, client_id: str):
    """Handle cursor position updates from Rust"""
    x = message.get("x", 0)
    y = message.get("y", 0)
    timestamp = message.get("timestamp", 0)
    
    # Log at debug level to avoid spam
    logger.debug(f"Cursor position: ({x}, {y}) at {timestamp}")
    
    # TODO: Use cursor position for guidance rendering (Sprint 6)


# Register message handlers
ws_manager.register_handler(MessageType.SCREENSHOT, handle_screenshot)
ws_manager.register_handler(MessageType.TASK_START, handle_task_start)
ws_manager.register_handler(MessageType.CURSOR_POS, handle_cursor_pos)


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
