import json
import logging
import os
from typing import List, Dict, Any, Optional
from llm.orchestrator import LLMOrchestrator

logger = logging.getLogger("cursor-king-backend.agent")

SYSTEM_PROMPT = """You are a desktop automation agent. You control a Windows PC by outputting ONE JSON tool call at a time.

Available tools:
- click(x, y, button): Click at (x,y). button: "left", "right", "double".
- type_text(text): Type text at cursor position.
- key_press(keys): Press key combo, e.g. "enter", "ctrl+c", "win".
- scroll(x, y, direction, amount): Scroll at (x,y). direction: "up"/"down".
- wait(seconds): Wait for UI to update.
- finish(success, message): Task is done.

Output format - ONLY output this JSON, nothing else:
{"thought": "brief reason", "tool": "tool_name", "args": {"key": "value"}}

Example for opening Notepad:
Step 1: {"thought": "Press Win to open Start menu", "tool": "key_press", "args": {"keys": "win"}}
Step 2: {"thought": "Start menu is open. Type notepad to search", "tool": "type_text", "args": {"text": "notepad"}}
Step 3: {"thought": "Notepad app appeared in search results. Click it.", "tool": "click", "args": {"x": 200, "y": 300, "button": "left"}}
Step 4: {"thought": "Notepad is now open. Type the text.", "tool": "type_text", "args": {"text": "Hello World"}}
Step 5: {"thought": "Task complete.", "tool": "finish", "args": {"success": true, "message": "Typed Hello World in Notepad"}}

CRITICAL RULES:
- Output ONLY the JSON object. No explanation, no code, no markdown.
- NEVER repeat the same action twice. Check history first.
- To click an element at (x,y,w,h), click its center: (x+w/2, y+h/2).
- The screen elements update after each action. Use CURRENT elements only.
"""

AGENT_PROMPT_TEMPLATE = """Task: "{query}"

History:
{history_str}

Current UI Elements:
{elements_str}

Output the next action as a single JSON object. ONLY JSON, nothing else."""

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

        # Smart Vision Toggle — only use vision if the model supports it.
        # Text-only models (llama-3.3-70b, deepseek-v3, etc.) will error
        # if sent image data. The A11y tree provides all necessary UI info.
        model_name = os.getenv("MODEL_NAME", "")
        is_vision_model = "vision" in model_name.lower()
        
        use_vision = False
        if image_bytes and is_vision_model:
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

            # Attempt to extract JSON using brace-matching parser for maximum robustness
            def extract_json_objects(text: str) -> list[dict]:
                results = []
                n = len(text)
                for i in range(n):
                    if text[i] == '{':
                        brace_count = 0
                        for j in range(i, n):
                            if text[j] == '{':
                                brace_count += 1
                            elif text[j] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    candidate = text[i:j+1]
                                    try:
                                        obj = json.loads(candidate)
                                        if isinstance(obj, dict):
                                            results.append(obj)
                                    except json.JSONDecodeError:
                                        pass
                                    break
                return results

            action_data = None
            try:
                action_data = json.loads(cleaned_response)
            except json.JSONDecodeError:
                pass

            if action_data is None or not isinstance(action_data, dict):
                candidates = extract_json_objects(raw_response)
                # Prioritize candidates starting from the end of response
                for cand in reversed(candidates):
                    if "tool" in cand:
                        action_data = cand
                        break
                if action_data is None and candidates:
                    action_data = candidates[-1]

            if action_data is None:
                # Fallback to simple scan
                start_idx = raw_response.find("{")
                end_idx = raw_response.rfind("}")
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    action_data = json.loads(raw_response[start_idx:end_idx + 1])
                else:
                    raise ValueError("No valid JSON object found in response")
            
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
