"""
WebSocket Connection Manager for handling connections from Rust client.
Implements reconnection logic, message routing, and health checks.
"""
import asyncio
import json
import logging
from typing import Dict, Optional, Callable, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class MessageType:
    """WebSocket message type constants"""
    SCREENSHOT = "screenshot"
    TASK_START = "task_start"
    TASK_STEP = "task_step"
    CURSOR_POS = "cursor_pos"
    ERROR = "error"
    ACK = "ack"
    PING = "ping"
    PONG = "pong"


class WsConnectionManager:
    """
    Manages WebSocket connections with health checks and message routing.
    """
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.message_handlers: Dict[str, Callable] = {}
        self.health_check_interval = 10  # seconds
        self._health_check_tasks: Dict[str, asyncio.Task] = {}
        
    def register_handler(self, message_type: str, handler: Callable):
        """Register a handler function for a specific message type"""
        self.message_handlers[message_type] = handler
        logger.info(f"Registered handler for message type: {message_type}")
        
    async def connect(self, websocket: WebSocket, client_id: str = "default"):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket client '{client_id}' connected. Total connections: {len(self.active_connections)}")
        
        # Start health check for this connection
        self._health_check_tasks[client_id] = asyncio.create_task(
            self._health_check_loop(client_id)
        )
        
    def disconnect(self, client_id: str = "default"):
        """Remove a WebSocket connection"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket client '{client_id}' disconnected. Remaining connections: {len(self.active_connections)}")
            
        # Cancel health check task
        if client_id in self._health_check_tasks:
            self._health_check_tasks[client_id].cancel()
            del self._health_check_tasks[client_id]
            
    async def send_message(self, message: Dict[str, Any], client_id: str = "default"):
        """Send a message to a specific client"""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(json.dumps(message))
                logger.debug(f"Sent message to '{client_id}': {message.get('type', 'unknown')}")
            except Exception as e:
                logger.error(f"Failed to send message to '{client_id}': {e}")
                self.disconnect(client_id)
        else:
            logger.warning(f"Attempted to send message to disconnected client '{client_id}'")
            
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected clients"""
        disconnected_clients = []
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to broadcast to '{client_id}': {e}")
                disconnected_clients.append(client_id)
                
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)
            
    async def handle_message(self, message_data: str, client_id: str = "default"):
        """Parse and route incoming messages to registered handlers"""
        try:
            message = json.loads(message_data)
            message_type = message.get("type")
            
            if not message_type:
                logger.warning(f"Received message without type from '{client_id}'")
                await self.send_error("Missing message type", client_id)
                return
                
            # Handle ping/pong for health checks
            if message_type == MessageType.PING:
                await self.send_message({"type": MessageType.PONG}, client_id)
                return
                
            # Route to registered handler
            if message_type in self.message_handlers:
                handler = self.message_handlers[message_type]
                try:
                    await handler(message, client_id)
                except Exception as e:
                    logger.error(f"Handler error for '{message_type}': {e}", exc_info=True)
                    await self.send_error(f"Handler error: {str(e)}", client_id)
            else:
                logger.warning(f"No handler registered for message type: {message_type}")
                # Send acknowledgement for unhandled messages
                await self.send_message({
                    "type": MessageType.ACK,
                    "received": message_type
                }, client_id)
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from '{client_id}': {e}")
            await self.send_error("Invalid JSON format", client_id)
        except Exception as e:
            logger.error(f"Error handling message from '{client_id}': {e}", exc_info=True)
            await self.send_error(str(e), client_id)
            
    async def send_error(self, error_message: str, client_id: str = "default", code: Optional[str] = None):
        """Send an error message to a client"""
        await self.send_message({
            "type": MessageType.ERROR,
            "message": error_message,
            "code": code,
            "timestamp": datetime.utcnow().isoformat()
        }, client_id)
        
    async def _health_check_loop(self, client_id: str):
        """Periodic health check via ping/pong"""
        try:
            while client_id in self.active_connections:
                await asyncio.sleep(self.health_check_interval)
                if client_id in self.active_connections:
                    await self.send_message({"type": MessageType.PING}, client_id)
        except asyncio.CancelledError:
            logger.debug(f"Health check cancelled for '{client_id}'")
        except Exception as e:
            logger.error(f"Health check error for '{client_id}': {e}")
            self.disconnect(client_id)
            
    async def listen(self, websocket: WebSocket, client_id: str = "default"):
        """Main message listening loop for a connection"""
        try:
            while True:
                message = await websocket.receive_text()
                await self.handle_message(message, client_id)
        except WebSocketDisconnect:
            logger.info(f"Client '{client_id}' disconnected normally")
            self.disconnect(client_id)
        except Exception as e:
            logger.error(f"Error in listen loop for '{client_id}': {e}", exc_info=True)
            self.disconnect(client_id)


# Global connection manager instance
ws_manager = WsConnectionManager()
