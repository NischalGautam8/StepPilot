import json
import logging
from typing import Optional, List, Dict, Any
from llm.orchestrator import LLMOrchestrator
from task.context_manager import ContextManager

logger = logging.getLogger("cursor-king-backend.task-planner")

SYSTEM_PROMPT = """You are the cognitive planner for StepPilot, a production-grade local-first desktop guidance assistant.
Your task is to decompose a user computer task query into a structured, step-by-step guidance plan that links directly to the interactive elements visible on the screen.

You are given:
1. A user query describing the goal.
2. Context & execution history detailing previous steps.
3. A serialized list of UI elements currently detected on the screen (or delta updates since last step) in the format: ID:ControlType"Text"(x,y,w,h)

You must output a strict JSON object containing:
- task: A concise summary of what the user wants to accomplish.
- steps: An ordered list of steps to guide the user. Each step MUST contain:
  - step_number: Integer index.
  - description: Human-friendly instruction of what to do (e.g. "Click the 'Minimize' button at the top right").
  - target_element_id: The element ID (e.g. "elem_7") if a specific element matches the action; otherwise null.
  - action: One of: "click", "type", "hover", "wait", "done".
  - bbox: The absolute screen coordinates [x, y, w, h] of the target element, or null if no target element exists.

Remember:
- Keep the number of steps minimal and highly accurate.
- Link each action to the exact element ID and bounding box coordinate.
- Do not make up elements or coordinates. Only use elements present in the list.
- Return ONLY the raw JSON object, without markdown formatting blocks.
"""

PLANNER_PROMPT_TEMPLATE = """User Query: "{query}"

Context & History:
{context_str}

Visible UI Elements:
{elements_str}

Please generate the step-by-step guidance plan in strict JSON.
"""

class TaskPlanner:
    """
    TaskPlanner manages token minimization, selects text-first or vision-based LLM,
    calculates UI changes (deltas), and decomposes natural language tasks.
    """
    def __init__(self):
        self.orchestrator = LLMOrchestrator()
        self.context_manager = ContextManager()
        self.prev_elements: List[Dict[str, Any]] = []

    @staticmethod
    def serialize_elements(elements: List[Dict[str, Any]]) -> str:
        """
        Serializes UI elements into a compact format to minimize token costs.
        Format: ID:Type"Text"@(cx,cy)
        where cx,cy is the pre-computed center of the bounding box.
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
            cx = x + w // 2
            cy = y + h // 2
            
            serialized_lines.append(f'{short_id}:{elem_type}"{clean_text}"@({cx},{cy})')
            
        return "\n".join(serialized_lines)

    def compute_element_delta(self, prev_elements: List[Dict[str, Any]], curr_elements: List[Dict[str, Any]]) -> str:
        """
        Computes the delta between two element lists to reduce prompt size.
        """
        prev_map = {e.get("id"): e for e in prev_elements if e.get("id")}
        curr_map = {e.get("id"): e for e in curr_elements if e.get("id")}
        
        added = []
        removed = []
        updated = []
        
        for cid, curr_elem in curr_map.items():
            if cid not in prev_map:
                added.append(curr_elem)
            else:
                prev_elem = prev_map[cid]
                # If text or bounding box coordinates changed
                if curr_elem.get("text") != prev_elem.get("text") or curr_elem.get("bbox") != prev_elem.get("bbox"):
                    updated.append(curr_elem)
                    
        for pid, prev_elem in prev_map.items():
            if pid not in curr_map:
                removed.append(prev_elem)
                
        delta_parts = []
        if added:
            delta_parts.append("Added elements:\n" + self.serialize_elements(added))
        if removed:
            delta_parts.append("Removed elements:\n" + self.serialize_elements(removed))
        if updated:
            delta_parts.append("Updated elements:\n" + self.serialize_elements(updated))
            
        if not delta_parts:
            return "No changes in UI elements from previous state."
            
        return "\n\n".join(delta_parts)

    async def plan_task(
        self, 
        query: str, 
        elements: List[Dict[str, Any]], 
        image_bytes: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Decomposes a user query + elements list into ordered guidance steps.
        """
        window_changed = self.context_manager.check_context_switch()
        
        # Determine average OCR confidence
        ocr_elements = [e for e in elements if e.get("source") == "ocr"]
        avg_confidence = 1.0
        if ocr_elements:
            avg_confidence = sum(e.get("confidence", 1.0) for e in ocr_elements) / len(ocr_elements)
            
        # Smart Vision Toggle decision logic
        use_vision = False
        if image_bytes:
            if window_changed or not self.context_manager.history_steps:
                logger.info("New active window or fresh task session detected. Forcing Vision mode.")
                use_vision = True
            elif avg_confidence < 0.85:
                logger.info(f"Low average OCR confidence ({avg_confidence:.2f} < 0.85). Using Vision mode.")
                use_vision = True
            elif len(elements) <= 5:
                logger.info(f"Sparse element registry ({len(elements)} <= 5). Using Vision mode.")
                use_vision = True
            elif any(word in query.lower() for word in ["icon", "image", "layout", "visual", "color"]):
                logger.info("User query requires visual reasoning. Using Vision mode.")
                use_vision = True

        # Fetch sliding-window compressed context
        context = self.context_manager.get_compressed_context()
        context_str = f"Active window title: '{context['current_window']}'\n"
        context_str += f"Execution history summary: {context['summary']}\n"
        if context['recent_steps']:
            context_str += "Recent completed steps (detailed):\n"
            for step in context['recent_steps']:
                context_str += f"- Step {step['step_number']} ({step['action']}): '{step['description']}' -> {step['status']}\n"

        # Apply Element delta caching to reduce tokens
        if window_changed or not self.prev_elements or not self.context_manager.history_steps:
            elements_str = self.serialize_elements(elements)
            logger.info(f"Context reset/start: sending full elements list ({len(elements)} elements).")
        else:
            elements_str = self.compute_element_delta(self.prev_elements, elements)
            logger.info("Sending elements delta updates to optimize tokens.")

        # Update cache for next iteration
        self.prev_elements = elements

        # Format prompt template
        prompt = PLANNER_PROMPT_TEMPLATE.format(
            query=query,
            context_str=context_str,
            elements_str=elements_str
        )
        
        raw_response = ""
        try:
            if use_vision and image_bytes:
                logger.info("Executing task planner in Vision mode...")
                raw_response = await self.orchestrator.complete_with_vision(
                    prompt=prompt,
                    image_bytes=image_bytes,
                    system_prompt=SYSTEM_PROMPT,
                    json_mode=True
                )
            else:
                logger.info("Executing task planner in Text-First mode (network/token optimized)...")
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
            
            plan = json.loads(cleaned_response)
            
            # Map simplified serialized short IDs in steps back to absolute 'elem_X' format
            if "steps" in plan:
                for step in plan["steps"]:
                    tid = step.get("target_element_id")
                    if tid and not str(tid).startswith("elem_"):
                        step["target_element_id"] = f"elem_{tid}"
                        
            return plan
            
        except json.JSONDecodeError as je:
            logger.error(f"Failed to parse LLM planning JSON response: {je}. Raw: {raw_response}")
            return {
                "task": query,
                "error": "Failed to parse planning response into structured steps.",
                "steps": []
            }
        except Exception as e:
            logger.error(f"Task planning pipeline execution failed: {e}", exc_info=True)
            return {
                "task": query,
                "error": f"Task decomposition pipeline error: {str(e)}",
                "steps": []
            }
