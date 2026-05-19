import logging
import win32gui
from typing import List, Dict, Any, Optional

logger = logging.getLogger("cursor-king-backend.context-manager")

class ContextManager:
    """
    ContextManager tracks step history and foreground window context.
    Implements token-minimization sliding window (summarizing older steps, keeping last 3 in full)
    and handles window-switch detection.
    """
    def __init__(self, max_full_steps: int = 3):
        self.max_full_steps = max_full_steps
        self.history_steps: List[Dict[str, Any]] = []
        self.last_window_title: str = ""

    def get_active_window_title(self) -> str:
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                return win32gui.GetWindowText(hwnd) or ""
        except Exception as e:
            logger.warning(f"Failed to get active window title: {e}")
        return ""

    def check_context_switch(self) -> bool:
        """
        Checks if the active foreground window title has changed.
        """
        current_title = self.get_active_window_title()
        if current_title != self.last_window_title:
            logger.info(f"Context switch detected: '{self.last_window_title}' -> '{current_title}'")
            self.last_window_title = current_title
            return True
        return False

    def add_step_result(self, step_number: int, description: str, action: str, status: str, details: Optional[str] = None):
        """
        Registers the result of a completed or cancelled step.
        """
        self.history_steps.append({
            "step_number": step_number,
            "description": description,
            "action": action,
            "status": status,
            "details": details or "",
            "window": self.get_active_window_title()
        })

    def get_compressed_context(self) -> Dict[str, Any]:
        """
        Compresses step history: summarizes older steps, retains the last N in full.
        """
        if not self.history_steps:
            return {
                "summary": "No steps executed yet.",
                "recent_steps": [],
                "current_window": self.get_active_window_title()
            }

        recent_steps = self.history_steps[-self.max_full_steps:]
        older_steps = self.history_steps[:-self.max_full_steps]

        summary_parts = []
        if older_steps:
            for step in older_steps:
                summary_parts.append(
                    f"Step {step['step_number']} ({step['action']}): {step['description']} -> {step['status']}"
                )
            summary = "; ".join(summary_parts)
        else:
            summary = "No older steps."

        return {
            "summary": summary,
            "recent_steps": recent_steps,
            "current_window": self.get_active_window_title()
        }

    def clear(self):
        """Clears context history."""
        self.history_steps.clear()
        self.last_window_title = ""
