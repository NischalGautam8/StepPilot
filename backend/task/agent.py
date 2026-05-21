import json
import logging
import os
from typing import List, Dict, Any, Optional
from llm.orchestrator import LLMOrchestrator

logger = logging.getLogger("cursor-king-backend.agent")

SYSTEM_PROMPT = """You are the AI Agent executor for StepPilot, a production-grade local-first desktop automation assistant.
Your goal is to complete the user's task on their Windows PC by generating a single next action using one of the available tools.

You are given:
1. The overall user task query.
2. The history of actions executed so far, including tool calls and their results.
3. A serialized list of UI elements currently visible on the screen in the format: ID:ControlType"Text"(x,y,w,h) where (x,y) is the top-left and (w,h) is the width and height of the bounding box.

You have access to the following tools:
- click(x, y, button): Click at coordinates (x, y). button is "left", "right" or "double" (for double click).
- type_text(text): Type the specified text at the current cursor position.
- key_press(keys): Press a key or key combination (e.g. 'enter', 'tab', 'ctrl+c', 'alt+f4').
- scroll(x, y, direction, amount): Move cursor to (x, y) and scroll in 'direction' ('up' or 'down') by 'amount' clicks.
- wait(seconds): Pause execution for a few seconds to let the UI update.
- read_screen(): Take a fresh screenshot and parse the visible UI elements to update the screen state. Use this tool when you expect the screen content has changed (e.g. after opening a new window, typing a search query, clicking a button that navigates, etc.) to see the new layout.
- finish(success, message): End the execution when the task is fully complete. success is a boolean, and message is a summary of the outcome.

To make progress:
- Analyze the current screen elements and matching text/controls.
- Compare them against the history of steps taken.
- Identify the coordinates of the target element. To click an element, click at its center: (x_center = x + w/2, y_center = y + h/2).
- Propose exactly one tool call at a time.

You must output a strict JSON object with:
- thought: A brief explanation of your reasoning (what you see, what you want to achieve).
- tool: The name of the tool to call ("click", "type_text", "key_press", "scroll", "wait", "read_screen", or "finish").
- args: A dictionary of arguments matching the tool definition (empty dictionary for read_screen).

Examples of Tool Calls:
1. Click at center of element "22:Button"Submit"(100,200,80,30)":
{"thought": "I need to submit the form, so I will click the 'Submit' button.", "tool": "click", "args": {"x": 140, "y": 215, "button": "left"}}

2. Type text:
{"thought": "Typing the text 'Hello World' in the active text field.", "tool": "type_text", "args": {"text": "Hello World"}}

3. Press Enter key:
{"thought": "Pressing enter to execute the command.", "tool": "key_press", "args": {"keys": "enter"}}

4. Scroll down at center of window:
{"thought": "Scrolling down to reveal more items.", "tool": "scroll", "args": {"x": 960, "y": 540, "direction": "down", "amount": 3}}

5. Read screen to update layout:
{"thought": "Since I just typed a search query, the screen layout has changed. I will read the screen to find the search results.", "tool": "read_screen", "args": {}}

6. Conclude task:
{"thought": "The Notepad file is saved. Task is complete.", "tool": "finish", "args": {"success": true, "message": "Successfully typed Hello World in Notepad."}}

Important Rules:
- Return ONLY the raw JSON object, without conversational text or explanation.
- Ensure the coordinates are valid numbers and inside the bounding boxes of the visible UI elements.
- Only propose one tool call at a time.
- CRITICAL: Do NOT write Python code, scripts, selenium automation, or write programming tutorial explanations. You are not a coding assistant. You are an executor acting on the screen. Propose ONLY the next direct UI action to execute in JSON format.
"""

AGENT_PROMPT_TEMPLATE = """Task Query: "{query}"

Action Execution History:
{history_str}

Currently Visible UI Elements:
{elements_str}

Analyze the state, determine the next correct action, and output it in strict JSON.
CRITICAL: Do NOT write Python scripts, Selenium code, or explain how to write program code. You must output ONLY a valid tool call JSON matching the requested action schema (with "thought", "tool", and "args" keys).
"""

class Agent:
    """
    Agent coordinates the cognitive loop for desktop automation. It builds prompts,
    serializes visible screen elements, and parses LLM tool calls.
    """
    def __init__(self):
        self.orchestrator = LLMOrchestrator()

    @staticmethod
    def serialize_elements(elements: List[Dict[str, Any]]) -> str:
        """
        Serializes UI elements into a compact format to minimize token costs.
        Format: ID:Type"Text"(x,y,w,h)
        """
        serialized_lines = []
        for elem in elements:
            elem_id = elem.get("id", "elem_unknown")
            short_id = elem_id.replace("elem_", "")
            
            elem_type = elem.get("type", "Unknown")
            
            text = elem.get("text", "") or ""
            clean_text = "".join(ch for ch in text if ord(ch) < 128 or ch.isalnum() or ch.isspace())
            clean_text = clean_text.replace("\n", " ").replace('"', '\\"')
            
            bbox = elem.get("bbox", [0, 0, 0, 0])
            x, y, w, h = bbox
            
            serialized_lines.append(f'{short_id}:{elem_type}"{clean_text}"({x},{y},{w},{h})')
            
        return "\n".join(serialized_lines)

    async def get_next_action(
        self,
        query: str,
        elements: List[Dict[str, Any]],
        history: List[Dict[str, Any]],
        image_bytes: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Calls the LLM to get the next step/action as a structured tool call.
        """
        # Format history string
        if not history:
            history_str = "No actions executed yet."
        else:
            history_parts = []
            for idx, action in enumerate(history):
                tool = action.get("tool")
                args = action.get("args", {})
                result = action.get("result", "success")
                history_parts.append(f"{idx+1}. {tool}({args}) -> {result}")
            history_str = "\n".join(history_parts)

        # Format elements string
        elements_str = self.serialize_elements(elements)

        prompt = AGENT_PROMPT_TEMPLATE.format(
            query=query,
            history_str=history_str,
            elements_str=elements_str
        )

        # Smart Vision Toggle decision logic
        use_vision = False
        if image_bytes:
            # Force vision on start, or if history is sparse, or if average OCR confidence is low
            ocr_elements = [e for e in elements if e.get("source") == "ocr"]
            avg_confidence = 1.0
            if ocr_elements:
                avg_confidence = sum(e.get("confidence", 1.0) for e in ocr_elements) / len(ocr_elements)

            if not history:
                use_vision = True
            elif avg_confidence < 0.85:
                use_vision = True
            elif len(elements) <= 5:
                use_vision = True

        raw_response = ""
        try:
            if use_vision and image_bytes:
                logger.info("Querying LLM agent in Vision mode...")
                raw_response = await self.orchestrator.complete_with_vision(
                    prompt=prompt,
                    image_bytes=image_bytes,
                    system_prompt=SYSTEM_PROMPT,
                    json_mode=True
                )
            else:
                logger.info("Querying LLM agent in Text-First mode...")
                raw_response = await self.orchestrator.complete(
                    prompt=prompt,
                    system_prompt=SYSTEM_PROMPT,
                    json_mode=True
                )

            cleaned_response = raw_response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

            # Attempt to extract JSON if it is wrapped in conversational text
            if not (cleaned_response.startswith("{") and cleaned_response.endswith("}")):
                start_idx = cleaned_response.find("{")
                end_idx = cleaned_response.rfind("}")
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    cleaned_response = cleaned_response[start_idx:end_idx + 1]

            # Try parsing direct block first, then fallback to structural scanning
            try:
                action_data = json.loads(cleaned_response)
            except json.JSONDecodeError:
                # Secondary scan: find first '{' and last '}' inside raw_response
                start_idx = raw_response.find("{")
                end_idx = raw_response.rfind("}")
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    action_data = json.loads(raw_response[start_idx:end_idx + 1])
                else:
                    raise
            
            # Basic validation
            if "tool" not in action_data:
                raise ValueError("Missing 'tool' field in LLM response")
            if "args" not in action_data:
                action_data["args"] = {}
                
            return action_data

        except Exception as e:
            logger.error(f"Failed to generate next agent action: {e}. Raw response: {raw_response}", exc_info=True)
            return {
                "thought": "I encountered an error trying to process the screen. I will wait for a bit.",
                "tool": "wait",
                "args": {"seconds": 2}
            }
