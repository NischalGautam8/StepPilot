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
        Retrieves the UIA element tree for the target window on the primary screen.
        If the foreground window is on a secondary monitor (e.g., StepPilot on screen 2),
        it finds the topmost visible window on the primary screen instead.
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

        # Check if the foreground window is on the primary screen
        target_hwnd = hwnd
        try:
            rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bottom = rect
            win_center_x = (left + right) // 2
            
            # If foreground window's center is outside the primary screen bounds,
            # it's on a secondary monitor — find a better target on primary screen
            if win_center_x < 0 or win_center_x >= display_width:
                fg_title = win32gui.GetWindowText(hwnd)
                logger.info(
                    f"Foreground window '{fg_title}' (HWND {hwnd}) is on a secondary monitor "
                    f"(center_x={win_center_x}). Searching for target window on primary screen..."
                )
                
                # Enumerate visible top-level windows and find the topmost one on the primary screen
                # (excluding taskbar, desktop, and StepPilot itself)
                SKIP_CLASSES = {"Shell_TrayWnd", "Progman", "WorkerW", "Shell_SecondaryTrayWnd"}
                SKIP_TITLES = {"StepPilot", "StepPilot Overlay", "Program Manager"}
                
                candidates = []
                def enum_callback(candidate_hwnd, _):
                    try:
                        if not win32gui.IsWindowVisible(candidate_hwnd):
                            return True
                        if win32gui.IsIconic(candidate_hwnd):  # minimized
                            return True
                        
                        class_name = win32gui.GetClassName(candidate_hwnd)
                        if class_name in SKIP_CLASSES:
                            return True
                        
                        title = win32gui.GetWindowText(candidate_hwnd)
                        if not title or title in SKIP_TITLES:
                            return True
                        
                        crect = win32gui.GetWindowRect(candidate_hwnd)
                        cleft, ctop, cright, cbottom = crect
                        cw = cright - cleft
                        ch = cbottom - ctop
                        ccx = (cleft + cright) // 2
                        
                        # Must be on primary screen and have reasonable size
                        if 0 <= ccx < display_width and cw > 50 and ch > 50:
                            candidates.append((candidate_hwnd, title, cleft, ctop, cw, ch))
                    except Exception:
                        pass
                    return True
                
                win32gui.EnumWindows(enum_callback, None)
                
                if candidates:
                    # Use the first (topmost in Z-order) candidate
                    target_hwnd, target_title, _, _, _, _ = candidates[0]
                    logger.info(f"Using primary-screen window: '{target_title}' (HWND {target_hwnd})")
                else:
                    logger.warning("No suitable window found on primary screen. Using foreground window as fallback.")
        except Exception as e:
            logger.warning(f"Failed to check foreground window monitor: {e}. Using foreground window.")

        # Get window title for context logging
        window_title = win32gui.GetWindowText(target_hwnd)
        logger.info(f"Inspecting target window UIA tree: [HWND {target_hwnd}] '{window_title}'")

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

            # 1. Sweep target window UIA tree
            target_window = desktop.window(handle=target_hwnd)
            traverse(target_window.element_info)
            
            # 2. Sweep Windows Taskbar explicitly to extract running shortcuts & pinned icons
            if taskbar_hwnd and taskbar_hwnd != target_hwnd:
                logger.info(f"Inspecting taskbar UIA tree: [HWND {taskbar_hwnd}]")
                try:
                    taskbar_window = desktop.window(handle=taskbar_hwnd)
                    # Use a depth of 3 to traverse taskbar icons and pinned shortcuts safely
                    traverse(taskbar_window.element_info, max_depth_override=3)
                except Exception as te:
                    logger.debug(f"Taskbar UIA sweep skipped: {te}")

            logger.info(f"A11yReader extracted {len(elements)} elements from target window & taskbar.")
        except Exception as e:
            logger.error(f"Failed to extract elements from target window UIA tree: {e}", exc_info=True)
        finally:
            # Uninitialize COM for the thread
            pythoncom.CoUninitialize()

        return elements

