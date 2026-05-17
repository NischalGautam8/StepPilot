import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

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

@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "service": "steppilot-backend",
        "version": "0.1.0"
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket communication bridge between Rust client and Python server."""
    await websocket.accept()
    logger.info("WebSocket connection accepted from client")
    try:
        while True:
            # Receive message from Rust sidecar or React frontend
            message = await websocket.receive_text()
            logger.info(f"Received message: {message[:100]}...")
            
            # Temporary echo/acknowledgement response
            response = f'{{"type": "ack", "received": {message}}}'
            await websocket.send_text(response)
    except WebSocketDisconnect:
        logger.info("WebSocket connection disconnected by client")
    except Exception as e:
        logger.error(f"WebSocket error occurred: {e}", exc_info=True)
    finally:
        logger.info("WebSocket cleanup complete")

if __name__ == "__main__":
    # Start the FastAPI app using Uvicorn on port 8765
    logger.info("Starting FastAPI Uvicorn server on http://127.0.0.1:8765")
    uvicorn.run("main:app", host="127.0.0.1", port=8765, log_level="info")
