import json
import logging
import os
import re
from typing import List, Dict, Any, Optional
from llm.orchestrator import LLMOrchestrator

logger = logging.getLogger("cursor-king-backend.agent")

SYSTEM_PROMPT = """You are a desktop automation agent. You control a Windows PC by outputting ONE JSON tool call at a time.

Available tools:
- click(x, y, button): Click at (x,y). button: "left", "right", "double".
- type_text(text): Type text at the CURRENT cursor/focus position. The text field MUST be focused first.
- search_text(text): Types text into the currently focused search field and presses Enter to submit. This is a composite tool that combines typing and Enter into one atomic step. The search field MUST be focused first. Use this instead of type_text when you want to search or submit a query.
- key_press(keys): Press key combo, e.g. "enter", "ctrl+c", "win".
- scroll(x, y, direction, amount): Scroll at (x,y). direction: "up"/"down".
- wait(seconds): Wait for UI to update.
- read_screen(): Re-read the screen to get updated UI elements.
- open_app(app_name): Open an application by name. Handles Start menu search, launching, and waiting for the app window to appear. USE THIS instead of manually pressing Win+typing+Enter.
- focus_app(title): Bring an already-open window to the foreground by title substring match. Use this if an app is open but not focused.
- navigate_url(url): Navigate the current browser to a URL. Handles address bar focus, typing, and Enter. USE THIS instead of manually pressing Ctrl+L+typing+Enter.
- finish(success, message): Task is done. ONLY use after verifying the result with read_screen().

Output format - ONLY output this JSON, nothing else:
{"thought": "brief reason", "tool": "tool_name", "args": {"key": "value"}}

UI Element format: ID:Type"Text"@(cx,cy) where cx,cy is the PRE-COMPUTED click center.
To click an element, use its cx,cy values DIRECTLY as the x,y arguments. Do NOT modify them.

Example for opening Notepad and typing:
Step 1: {"thought": "Open Notepad app", "tool": "open_app", "args": {"app_name": "notepad"}}
Step 2: {"thought": "Notepad is now open. Type the text.", "tool": "type_text", "args": {"text": "Hello World"}}
Step 3: {"thought": "Verify text was typed. Read screen.", "tool": "read_screen", "args": {}}
Step 4: {"thought": "Screen shows 'Hello World' in the editor. Task complete.", "tool": "finish", "args": {"success": true, "message": "Typed Hello World in Notepad"}}

Example for opening YouTube and playing a video:
Step 1: {"thought": "Open Chrome browser", "tool": "open_app", "args": {"app_name": "chrome"}}
Step 2: {"thought": "Chrome is open. Navigate to YouTube.", "tool": "navigate_url", "args": {"url": "https://www.youtube.com"}}
Step 3: {"thought": "YouTube loaded. Press / to focus the search bar.", "tool": "key_press", "args": {"keys": "/"}}
Step 4: {"thought": "Search bar focused. Search for 'dog videos' and submit.", "tool": "search_text", "args": {"text": "dog videos"}}
Step 5: {"thought": "Search results loaded. Click the first video title.", "tool": "click", "args": {"x": 500, "y": 400, "button": "left"}}
Step 6: {"thought": "Clicked a video. Read screen to verify it is actually playing.", "tool": "read_screen", "args": {}}
Step 7: {"thought": "Screen shows a video player with the video title. Video is playing. Task complete.", "tool": "finish", "args": {"success": true, "message": "Playing dog videos on YouTube"}}

CRITICAL RULES:
- Output ONLY the JSON object. No explanation, no code, no markdown.
- NEVER repeat the same action on the same target. Check history first.
- If your last action did not change the screen state, do NOT repeat it. Try a DIFFERENT approach.
- If you have clicked the same area 2+ times without progress, try: key_press, type_text, scroll, or read_screen instead.
- Use the cx,cy coordinates from the element list DIRECTLY. Do NOT add, subtract, or calculate anything.
- The screen elements update after each action. Use CURRENT elements only.
- If the task seems impossible with current UI state, use finish with success=false.
- PREFER keyboard shortcuts over clicking small UI buttons. Shortcuts are faster and more reliable.
- After opening a NEW TAB or document, the text area is already focused. Just use type_text() directly.
- Elements showing "[empty text field]" are text areas ready for typing — use type_text() or search_text() to input text there.
- To OPEN an application, ALWAYS use open_app(app_name) instead of manually pressing Win key and typing.
- To SWITCH to an already-open window, use focus_app(title) instead of alt+tab.
- To GO TO a URL, ALWAYS use navigate_url(url) instead of manually pressing Ctrl+L and typing.
- BEFORE using type_text() or search_text(), the target text field MUST be focused first. Use click() or a keyboard shortcut to focus it.
- On YouTube, do NOT use spacebar (e.g. key_press("space")) to play/pause videos unless you have verified a video is actually loaded and focused. On the home page or search results pages, pressing space does not select or play videos — click a video title or thumbnail instead.
- Do NOT press Enter to "play" or "select" something unless you have first typed text into a focused search field. Enter submits forms, it does not select visible items — use click() instead.

VERIFICATION RULES (VERY IMPORTANT):
- BEFORE calling finish(), you MUST call read_screen() to verify the task actually succeeded.
- After clicking something important (a video, a search result, a button), ALWAYS read_screen() to confirm the UI changed as expected.
- Do NOT assume an action worked just because it was executed. Check the screen state.
- If verification shows the wrong state (e.g., you clicked a video but the home page is showing), try again with a different element.
- A task is only "complete" when you can SEE evidence of completion on screen (video playing, text typed, app open, etc.).

CLICKING RULES FOR WEB PAGES:
- On YouTube/web pages, be careful to click VIDEO CONTENT (titles, thumbnails) not NAVIGATION elements.
- AVOID clicking these navigation elements: "Home", "Shorts", "Subscriptions", "Library", "History", menu icons, sidebar items.
- NEVER click on elements that look like advertisements, sponsored search results, or promoted content. Check for small text like "Ad", "Sponsored", "Promoted", or "Advertisement" next to or inside the element before clicking. Only click organic results.
- Video results typically have: a title with descriptive text, a channel name, view count, and duration.
- Look for elements with text that matches what you searched for — those are the actual results.
- If you can't identify a clear video result, use scroll(direction="down") to see more results, then read_screen().

WEB NAVIGATION RULES:
- To search on a website (YouTube, Google, etc.), you MUST first focus the search bar, THEN use search_text(text) to type and submit.
- On YouTube: press "/" to focus the search bar before typing.
- On Google: the search box is usually auto-focused after navigating to google.com.
- NEVER press Enter repeatedly hoping something will happen. If Enter didn't work, try a different approach.
- After navigate_url(), wait for the page to load, then look at the UI elements to find interactive elements like search bars, buttons, and links.
- If you click something and it unexpectedly opens a new tab or window containing an advertisement, spam, or irrelevant content, immediately close the tab using key_press("ctrl+w") to return to the original page.

USEFUL KEYBOARD SHORTCUTS:
- New tab (browser): key_press("ctrl+t")
- New window: key_press("ctrl+n")
- Save: key_press("ctrl+s")
- Close current tab: key_press("ctrl+w")
- Undo: key_press("ctrl+z")
- Select all: key_press("ctrl+a")
- Copy/Paste: key_press("ctrl+c") / key_press("ctrl+v")
- Switch window: key_press("alt+tab")
- Address bar (browser): key_press("ctrl+l") or key_press("f6")
- YouTube search bar: key_press("/")
"""

AGENT_PROMPT_TEMPLATE = """Task: "{query}"

History (do NOT repeat any action from this list):
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
        Format: ID:Type"Text"@(cx,cy)
        where cx,cy is the pre-computed center of the bounding box.
        This eliminates the need for the LLM to compute coordinates.
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
            # Pre-compute center so the LLM uses exact coordinates
            cx = x + w // 2
            cy = y + h // 2
            
            # Label empty interactive elements so the LLM recognizes them as typeable
            INTERACTIVE_TYPES = {"Edit", "Document", "TextBox", "RichEdit", "ComboBox"}
            if not clean_text.strip() and elem_type in INTERACTIVE_TYPES:
                clean_text = "[empty text field]"
            
            serialized_lines.append(f'{short_id}:{elem_type}"{clean_text}"@({cx},{cy})')
            
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

            # Strip <think>...</think> blocks from thinking models (e.g. Qwen)
            cleaned_response = re.sub(r'<think>.*?</think>', '', cleaned_response, flags=re.DOTALL).strip()

            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

            # Evaluate inline arithmetic expressions in JSON values.
            # Models sometimes output "x": 516 + 888/2 instead of "x": 960.
            def _eval_inline_math(text: str) -> str:
                """Replace simple arithmetic expressions (e.g. 516 + 888/2) with their computed integer result."""
                def _safe_eval(match):
                    expr = match.group(0)
                    try:
                        result = eval(expr, {"__builtins__": {}}, {})
                        return str(int(result))
                    except Exception:
                        return expr
                # Match patterns like: 516 + 888/2, 118 + 40/2, 100 * 2 + 50
                # Only inside JSON value positions (after : and before , or })
                return re.sub(r'(?<=[:,\s])\s*(\d+(?:\s*[+\-*/]\s*\d+)+)', _safe_eval, text)

            cleaned_response = _eval_inline_math(cleaned_response)

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
