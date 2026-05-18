import json
import logging
from typing import Optional, List, Dict, Any
from llm.orchestrator import LLMOrchestrator

logger = logging.getLogger("cursor-king-backend.task-planner")

SYSTEM_PROMPT = """You are the cognitive planner for StepPilot, a production-grade local-first desktop guidance assistant.
Your task is to decompose a user computer task query into a structured, step-by-step guidance plan that links directly to the interactive elements visible on the screen.

You are given:
1. A user query describing the goal.
2. A serialized list of UI elements currently detected on the screen in the format: ID:ControlType"Text"(x,y,w,h)

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

Visible UI Elements:
{elements_str}

Please generate the step-by-step guidance plan in strict JSON.
"""

class TaskPlanner:
    """
    TaskPlanner manages token minimization, selects text-first or vision-based LLM,
    and decomposes natural language tasks into actionable, structured JSON plans.
    """
    def __init__(self):
        self.orchestrator = LLMOrchestrator()

    @staticmethod
    def serialize_elements(elements: List[Dict[str, Any]]) -> str:
        """
        Serializes UI elements into an ultra-compact format to minimize token costs.
        Format: ID:Type"Text"(x,y,w,h)
        Example: 1:Button"Connect WebSocket"(100,200,80,40)
        """
        serialized_lines = []
        for elem in elements:
            elem_id = elem.get("id", "elem_unknown")
            short_id = elem_id.replace("elem_", "")
            
            elem_type = elem.get("type", "Unknown")
            
            # Clean and escape text values, stripping non-ASCII control symbols (like LTR marks \u200e)
            text = elem.get("text", "") or ""
            clean_text = "".join(ch for ch in text if ord(ch) < 128 or ch.isalnum() or ch.isspace())
            clean_text = clean_text.replace("\n", " ").replace('"', '\\"')
            
            bbox = elem.get("bbox", [0, 0, 0, 0])
            x, y, w, h = bbox
            
            serialized_lines.append(f'{short_id}:{elem_type}"{clean_text}"({x},{y},{w},{h})')
            
        return "\n".join(serialized_lines)

    async def plan_task(
        self, 
        query: str, 
        elements: List[Dict[str, Any]], 
        image_bytes: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Decomposes a user query + elements list into ordered guidance steps.
        
        Applies a smart cost-minimization strategy:
        - If image_bytes are provided AND average OCR confidence is low (< 0.7), it runs in Vision mode.
        - Otherwise, it defaults to Text-First mode (no screenshot attachment) to save 90%+ in LLM costs.
        """
        # Serialize the elements registry into compact format
        elements_str = self.serialize_elements(elements)
        
        # Determine average OCR confidence
        ocr_elements = [e for e in elements if e.get("source") == "ocr"]
        avg_confidence = 1.0
        if ocr_elements:
            avg_confidence = sum(e.get("confidence", 1.0) for e in ocr_elements) / len(ocr_elements)
            
        # Decision: Use Vision mode only when average OCR confidence is poor OR user query demands visual reasoning
        use_vision = False
        if image_bytes:
            if avg_confidence < 0.7:
                logger.info(f"Low average OCR confidence ({avg_confidence:.2f} < 0.7). Using Vision-based planning.")
                use_vision = True
            elif any(word in query.lower() for word in ["icon", "image", "layout", "visual", "color"]):
                logger.info("User query requires visual reasoning. Using Vision-based planning.")
                use_vision = True
                
        prompt = PLANNER_PROMPT_TEMPLATE.format(query=query, elements_str=elements_str)
        
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
                
            # Clean up potential markdown code fences from the LLM response
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
