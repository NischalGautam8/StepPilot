import logging
import win32gui

logger = logging.getLogger("cursor-king-backend.a11y-reader")

class A11yReader:
    """
    A11yReader uses pywinauto to inspect the active window's UIA element tree,
    extracting semantic control types, automation IDs, titles, and coordinates.
    """
    def __init__(self, max_depth: int = 6):
        self.max_depth = max_depth

    def get_active_window_elements(self, display_width: int = 1920, display_height: int = 1080) -> list[dict]:
        """
        Retrieves the UIA element tree for the current active foreground window.
        Returns a list of dicts: [{"type": str, "name": str, "bbox": [x, y, w, h], "enabled": bool, "automation_id": str}]
        """
        try:
            from pywinauto import Desktop
        except ImportError as e:
            logger.error(f"Failed to import pywinauto: {e}")
            return []

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            logger.warning("No active foreground window found.")
            return []

        # Get window title for context logging
        window_title = win32gui.GetWindowText(hwnd)
        logger.info(f"Inspecting active window UIA tree: [HWND {hwnd}] '{window_title}'")

        # Locate Windows Shell Taskbar handle to explicitly extract taskbar icons/shortcuts
        taskbar_hwnd = win32gui.FindWindow("Shell_TrayWnd", None)

        # Initialize COM for the current thread to support background execution via asyncio.to_thread
        import pythoncom
        pythoncom.CoInitialize()

        elements = []
        try:
            desktop = Desktop(backend="uia")
            
            def traverse(info, depth=0, max_depth_override=None):
                limit = max_depth_override if max_depth_override is not None else self.max_depth
                if depth > limit:
                    return
                
                try:
                    rect = info.rectangle
                    if rect:
                        x = rect.left
                        y = rect.top
                        w = rect.width()
                        h = rect.height()
                        
                        # Prune search early if the element is completely off-screen.
                        if x >= display_width or y >= display_height or (x + w) <= 0 or (y + h) <= 0:
                            return
                        
                        # Ensure element has non-zero size
                        if w > 0 and h > 0:
                            control_type = info.control_type or "Unknown"
                            name = info.name or ""
                            automation_id = info.automation_id or ""
                            
                            # Skip slow COM call for is_enabled() since it is not used for agent serialization
                            enabled = True
                                
                            elements.append({
                                "type": control_type,
                                "name": name,
                                "bbox": [x, y, w, h],
                                "enabled": enabled,
                                "automation_id": automation_id
                            })
                except Exception:
                    pass
                    
                try:
                    for child in info.children():
                        traverse(child, depth + 1, max_depth_override)
                except Exception:
                    pass

            # 1. Sweep active foreground window UIA tree using element_info directly
            active_window = desktop.window(handle=hwnd)
            traverse(active_window.element_info)
            
            # 2. Sweep Windows Taskbar explicitly to extract running shortcuts & pinned icons
            if taskbar_hwnd and taskbar_hwnd != hwnd:
                logger.info(f"Inspecting taskbar UIA tree: [HWND {taskbar_hwnd}]")
                try:
                    taskbar_window = desktop.window(handle=taskbar_hwnd)
                    # Use a depth of 3 to traverse taskbar icons and pinned shortcuts safely
                    traverse(taskbar_window.element_info, max_depth_override=3)
                except Exception as te:
                    logger.debug(f"Taskbar UIA sweep skipped: {te}")

            logger.info(f"A11yReader extracted {len(elements)} elements from active window & taskbar.")
        except Exception as e:
            logger.error(f"Failed to extract elements from active window UIA tree: {e}", exc_info=True)
        finally:
            # Uninitialize COM for the thread
            pythoncom.CoUninitialize()

        return elements

