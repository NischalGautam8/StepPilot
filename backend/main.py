import os
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['FLAGS_use_onednn'] = '0'
os.environ['FLAGS_enable_onednn'] = '0'
os.environ['FLAGS_enable_mkldnn'] = '0'
os.environ['FLAGS_enable_pir_api'] = '0'
os.environ['FLAGS_enable_pir_in_executor'] = '0'

import logging
import base64
from io import BytesIO
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from PIL import Image
import cv2
import numpy as np
import pyautogui

# Initialize structured logging first
from core.logger import setup_logging, get_logger, log_error, log_websocket_event
logger = setup_logging(log_level="INFO")

from core.ws_manager import ws_manager, MessageType
from core.settings_manager import apply_settings
from vision.screen_parser import ScreenParser

# Apply settings from config and keyring on startup
apply_settings()

# Initialize ScreenParser & TaskPlanner lazily to avoid heavy model loading on startup
screen_parser = None
task_planner = None
agent_executor = None
actuator = None
last_parsed_elements = []
last_screenshot_bytes = None

# Agent state variables
is_agent_running = False
current_task_query = ""
agent_history = []
agent_mode = "supervised"

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


async def capture_and_parse_screen():
    global screen_parser, last_parsed_elements, last_screenshot_bytes
    if screen_parser is None:
        logger.info("Initializing ScreenParser for agent screen capture...")
        screen_parser = ScreenParser()
        
    # Capture screen using PyAutoGUI
    screenshot = pyautogui.screenshot()
    image_np = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    
    preprocessed_np, crop_bounds = screen_parser.preprocess_image(image_np)
    _, encoded_img = cv2.imencode(".jpg", preprocessed_np)
    last_screenshot_bytes = encoded_img.tobytes()
    
    detected_elements = await screen_parser.parse_screen(preprocessed_np, crop_bounds)
    last_parsed_elements = detected_elements
    return detected_elements


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
        from vision.ui_detector import check_models_exist
        settings = load_settings()
        settings["models_downloaded"] = check_models_exist()
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
        from vision.ui_detector import check_models_exist
        settings = message.get("settings", {})
        # Pop models_downloaded so we don't save it to file
        settings.pop("models_downloaded", None)
        save_settings(settings)
        
        settings["models_downloaded"] = check_models_exist()
        await ws_manager.send_message({
            "type": "settings_saved",
            "status": "success",
            "settings": settings
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


async def handle_download_models(message: dict, client_id: str):
    """Handle model download request from frontend"""
    global screen_parser
    try:
        import asyncio
        from vision.screen_parser import ScreenParser
        from vision.ui_detector import UIDetector
        
        if screen_parser is None:
            screen_parser = ScreenParser()
            
        if screen_parser.ui_detector is None:
            screen_parser.ui_detector = UIDetector(use_gpu=screen_parser.use_gpu)
            
        detector = screen_parser.ui_detector
        loop = asyncio.get_running_loop()
        
        # Define progress callback to send websocket progress events
        def progress_callback(percentage: float, status_msg: str):
            try:
                asyncio.run_coroutine_threadsafe(
                    ws_manager.send_message({
                        "type": "download_progress",
                        "percentage": percentage,
                        "status": status_msg
                    }, client_id),
                    loop
                )
            except Exception as ex:
                logger.error(f"Error sending download progress: {ex}")

        logger.info(f"Client '{client_id}' triggered OmniParser models download.")
        
        # Run download pipeline in background thread
        success = await asyncio.to_thread(detector.download_models, progress_callback)
        logger.info(f"OmniParser model download completed: {success}")
        
        # Send latest settings state to sync frontend with the new downloaded status
        from core.settings_manager import load_settings
        from vision.ui_detector import check_models_exist
        settings = load_settings()
        settings["models_downloaded"] = check_models_exist()
        await ws_manager.send_message({
            "type": "settings_data",
            "settings": settings
        }, client_id)
        
    except Exception as e:
        logger.error(f"Error executing download_models: {e}", exc_info=True)
        await ws_manager.send_error(f"Model download error: {str(e)}", client_id)


async def handle_cancel_download(message: dict, client_id: str):
    """Handle request from frontend to cancel an active model download"""
    global screen_parser
    try:
        if screen_parser and screen_parser.ui_detector:
            screen_parser.ui_detector.cancel_download()
            logger.info(f"Client '{client_id}' requested cancellation of model download.")
            await ws_manager.send_message({
                "type": "download_progress",
                "percentage": -1.0,
                "status": "Download cancelled by user."
            }, client_id)
        else:
            logger.warning("Cancel download requested but no active detector/parser found.")
            await ws_manager.send_message({
                "type": "download_progress",
                "percentage": -1.0,
                "status": "No active download running."
            }, client_id)
    except Exception as e:
        logger.error(f"Error executing cancel_download: {e}", exc_info=True)


async def handle_agent_start(message: dict, client_id: str):
    """Start the interactive agent loop"""
    global agent_executor, actuator, last_parsed_elements, last_screenshot_bytes
    global is_agent_running, current_task_query, agent_history, agent_mode
    
    try:
        query = message.get("query", "")
        mode = message.get("mode", "supervised").lower()
        
        logger.info(f"Agent starting task: '{query}' in mode={mode}")
        
        if agent_executor is None:
            from task.agent import Agent
            agent_executor = Agent()
        if actuator is None:
            from task.actuator import Actuator
            actuator = Actuator()
            
        is_agent_running = True
        current_task_query = query
        agent_mode = mode
        agent_history = []
        
        # Force a fresh capture and parse on start
        elements = await capture_and_parse_screen()
        
        if not is_agent_running:
            logger.info("Agent task start aborted by user.")
            return
            
        # Get first action
        next_action = await agent_executor.get_next_action(
            query=current_task_query,
            elements=elements,
            history=agent_history,
            image_bytes=last_screenshot_bytes
        )
        
        if not is_agent_running:
            logger.info("Agent task start aborted by user while querying LLM.")
            return
            
        await ws_manager.send_message({
            "type": "agent_action_proposed",
            "action": next_action,
            "history": agent_history
        }, client_id)
        
    except Exception as e:
        logger.error(f"Error starting agent task: {e}", exc_info=True)
        await ws_manager.send_error(f"Agent start error: {str(e)}", client_id)


async def handle_agent_step_execute(message: dict, client_id: str):
    """Execute the proposed agent action and query LLM for the next step"""
    global agent_executor, actuator, last_parsed_elements, last_screenshot_bytes
    global is_agent_running, current_task_query, agent_history, agent_mode
    
    if not is_agent_running:
        await ws_manager.send_error("Agent is not currently running a task.", client_id)
        return
        
    try:
        proposed_action = message.get("action", {})
        tool = proposed_action.get("tool")
        args = proposed_action.get("args", {})
        
        logger.info(f"Executing agent step: tool={tool}, args={args}")
        
        # ── Repeat-action guard ──
        # Detect when the LLM proposes the exact same action as the last one
        # (e.g. key_press("win") twice in a row). This prevents toggle loops
        # like repeatedly opening/closing the Start menu.
        if agent_history:
            last = agent_history[-1]
            if last.get("tool") == tool and last.get("args") == args and tool not in ("wait", "read_screen", "finish"):
                logger.warning(
                    f"BLOCKED repeat action: {tool}({args}) was already the last executed action. "
                    f"Forcing screen re-read instead to break the loop."
                )
                # Force a fresh screen capture so the LLM gets updated state
                screen_parser.cache_elements = None
                elements = await capture_and_parse_screen()
                
                agent_history.append({
                    "tool": "read_screen",
                    "args": {},
                    "result": f"auto-triggered: blocked repeat {tool}. Found {len(elements)} elements"
                })
                
                next_action = await agent_executor.get_next_action(
                    query=current_task_query,
                    elements=elements,
                    history=agent_history,
                    image_bytes=last_screenshot_bytes
                )
                
                await ws_manager.send_message({
                    "type": "agent_action_proposed",
                    "action": next_action,
                    "history": agent_history
                }, client_id)
                return
        
        if tool == "finish":
            is_agent_running = False
            result_str = "task completed"
            agent_history.append({
                "tool": tool,
                "args": args,
                "result": result_str
            })
            await ws_manager.send_message({
                "type": "agent_finished",
                "success": args.get("success", True),
                "message": args.get("message", "Task completed successfully."),
                "history": agent_history
            }, client_id)
            return
            
        result_str = "success"
        if agent_mode in ["supervised", "autonomous", "yolo"]:
            success = False
            if tool == "click":
                x = int(args.get("x", 0))
                y = int(args.get("y", 0))
                button = args.get("button", "left")
                if button == "double":
                    success = actuator.double_click(x, y)
                elif button == "right":
                    success = actuator.right_click(x, y)
                else:
                    success = actuator.click(x, y, button=button)
            elif tool == "type_text":
                text = args.get("text", "")
                success = actuator.type_text(text)
            elif tool == "key_press":
                keys = args.get("keys", "")
                success = actuator.key_press(keys)
            elif tool == "scroll":
                x = int(args.get("x", 0))
                y = int(args.get("y", 0))
                direction = args.get("direction", "down")
                amount = int(args.get("amount", 3))
                success = actuator.scroll(x, y, direction, amount)
            elif tool == "wait":
                seconds = float(args.get("seconds", 1.0))
                success = actuator.wait(seconds)
            elif tool == "read_screen":
                try:
                    logger.info("Executing read_screen tool: capturing fresh screenshot and parsing UIElements...")
                    elements = await capture_and_parse_screen()
                    success = True
                    result_str = f"screen updated: found {len(elements)} elements"
                except Exception as ex:
                    logger.error(f"Failed to read screen: {ex}")
                    success = False
                    result_str = f"failed to read screen: {str(ex)}"
                
            if tool != "read_screen":
                result_str = "success" if success else "failed"
        else:
            # Guided mode: User executed this step manually
            result_str = "completed by user"
            
        # Append execution result to history
        agent_history.append({
            "tool": tool,
            "args": args,
            "result": result_str
        })
        
        # Always re-read the screen after state-changing actions so the LLM
        # sees the current UI state. Without this, the agent reuses stale cached
        # elements and repeats actions (e.g. pressing Win key twice, typing text
        # twice) because it doesn't see the screen has already changed.
        if tool == "read_screen":
            # Screen was already captured during execution above
            pass
        elif tool in ("click", "type_text", "key_press", "scroll"):
            # Brief delay to let the OS render UI changes (Start menu appearing,
            # text being typed, window focus changing, etc.)
            import asyncio
            await asyncio.sleep(0.5)
            
            # Invalidate cache and capture fresh screen state
            screen_parser.cache_elements = None
            logger.info(f"Auto-refreshing screen after '{tool}' action...")
            elements = await capture_and_parse_screen()
            result_str += f" | screen refreshed: {len(elements)} elements"
        else:
            # For wait and other non-UI actions, use cached elements
            elements = last_parsed_elements
            
        if not is_agent_running:
            logger.info("Agent execution was aborted. Stopping step execution.")
            return

        # Get next action proposal from LLM
        next_action = await agent_executor.get_next_action(
            query=current_task_query,
            elements=elements,
            history=agent_history,
            image_bytes=last_screenshot_bytes
        )
        
        if not is_agent_running:
            logger.info("Agent execution was aborted. Suppressing next action proposal.")
            return
            
        # Send proposed action to frontend
        await ws_manager.send_message({
            "type": "agent_action_proposed",
            "action": next_action,
            "history": agent_history
        }, client_id)
        
    except Exception as e:
        logger.error(f"Error executing agent step: {e}", exc_info=True)
        await ws_manager.send_error(f"Agent execution error: {str(e)}", client_id)


async def handle_agent_abort(message: dict, client_id: str):
    """Abort the running agent loop"""
    global is_agent_running, agent_history
    is_agent_running = False
    logger.info("Agent task execution aborted by user.")
    await ws_manager.send_message({
        "type": "agent_aborted",
        "message": "Task aborted by user.",
        "history": agent_history
    }, client_id)


# Register message handlers
ws_manager.register_handler(MessageType.SCREENSHOT, handle_screenshot)
ws_manager.register_handler(MessageType.TASK_START, handle_task_start)
ws_manager.register_handler(MessageType.CURSOR_POS, handle_cursor_pos)
ws_manager.register_handler("get_settings", handle_get_settings)
ws_manager.register_handler("save_settings", handle_save_settings)
ws_manager.register_handler("step_result", handle_step_result)
ws_manager.register_handler("download_models", handle_download_models)
ws_manager.register_handler("cancel_download", handle_cancel_download)
ws_manager.register_handler("agent_start", handle_agent_start)
ws_manager.register_handler("agent_step_execute", handle_agent_step_execute)
ws_manager.register_handler("agent_abort", handle_agent_abort)


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
