import time
import logging
import ctypes
import subprocess
import pyautogui
import math
import win32gui
import win32con

logger = logging.getLogger("cursor-king-backend.actuator")

# Set up process DPI awareness on Windows to match physical coordinates
try:
    ctypes.windll.user32.SetProcessDPIAware()
    logger.info("DPI awareness enabled for Python process.")
except Exception as e:
    logger.warning(f"Failed to enable process DPI awareness: {e}")

# Enable fail-safe: moving cursor to top-left corner aborts script execution
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1  # Add a tiny pause after pyautogui commands for safety

class Actuator:
    """
    Actuator executes OS-level actions (mouse click/movement, keyboard typing/hotkeys)
    using PyAutoGUI and handles smooth interpolation and coordinate mapping.
    """
    def __init__(self, move_duration: float = 0.3):
        self.move_duration = move_duration

    def smooth_move(self, target_x: int, target_y: int):
        """
        Moves the cursor smoothly from its current position to (target_x, target_y)
        over the configured move_duration using cosine ease-in-out interpolation.
        If the cursor starts on a secondary display, it is first moved to the primary display.
        """
        try:
            start_x, start_y = pyautogui.position()
            screen_w, screen_h = pyautogui.size()
            
            # Check if cursor is on secondary display (outside primary bounds 0..screen_w, 0..screen_h)
            is_on_secondary = (start_x < 0 or start_x >= screen_w or start_y < 0 or start_y >= screen_h)
            if is_on_secondary:
                logger.info(f"Cursor at ({start_x}, {start_y}) is on a secondary display. Warp moving to primary display first.")
                # Warp to the nearest boundary edge on the primary display
                near_x = max(0, min(start_x, screen_w - 1))
                near_y = max(0, min(start_y, screen_h - 1))
                pyautogui.moveTo(near_x, near_y)
                time.sleep(0.05)
                # Refresh starting point
                start_x, start_y = pyautogui.position()

            if start_x == target_x and start_y == target_y:
                return

            logger.debug(f"Smooth moving cursor: ({start_x}, {start_y}) -> ({target_x}, {target_y})")
            
            # Target 60 updates per second
            fps = 60
            steps = max(int(self.move_duration * fps), 10)
            
            for i in range(1, steps + 1):
                t = i / steps
                # Cosine ease-in-out formula
                ease_t = (1 - math.cos(t * math.pi)) / 2
                
                curr_x = int(start_x + (target_x - start_x) * ease_t)
                curr_y = int(start_y + (target_y - start_y) * ease_t)
                
                pyautogui.moveTo(curr_x, curr_y)
                time.sleep(self.move_duration / steps)
                
            # Ensure exact target coordinates at the end
            pyautogui.moveTo(target_x, target_y)
        except Exception as e:
            logger.error(f"Error during smooth_move to ({target_x}, {target_y}): {e}")
            # Fallback to direct moveTo
            pyautogui.moveTo(target_x, target_y)

    def click(self, x: int, y: int, button: str = "left") -> bool:
        """Moves cursor smoothly and performs a mouse click."""
        try:
            self.smooth_move(x, y)
            pyautogui.click(button=button.lower())
            logger.info(f"Executed click at ({x}, {y}) using button={button}")
            return True
        except Exception as e:
            logger.error(f"Failed to execute click at ({x}, {y}): {e}")
            return False

    def double_click(self, x: int, y: int) -> bool:
        """Moves cursor smoothly and performs a double-click."""
        try:
            self.smooth_move(x, y)
            pyautogui.doubleClick()
            logger.info(f"Executed double click at ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"Failed to execute double click at ({x}, {y}): {e}")
            return False

    def right_click(self, x: int, y: int) -> bool:
        """Moves cursor smoothly and performs a right-click."""
        try:
            self.smooth_move(x, y)
            pyautogui.rightClick()
            logger.info(f"Executed right click at ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"Failed to execute right click at ({x}, {y}): {e}")
            return False

    def type_text(self, text: str, interval: float = 0.05) -> bool:
        """Types the specified text with a human-like interval between keystrokes."""
        try:
            logger.info(f"Typing text: '{text}'")
            pyautogui.write(text, interval=interval)
            return True
        except Exception as e:
            logger.error(f"Failed to type text '{text}': {e}")
            return False

    def key_press(self, keys: str) -> bool:
        """
        Presses a single key or key combination (e.g. 'enter', 'ctrl+c', 'alt+tab').
        """
        try:
            parts = [p.strip().lower() for p in keys.split("+")]
            if len(parts) > 1:
                logger.info(f"Pressing hotkey: {parts}")
                pyautogui.hotkey(*parts)
            else:
                logger.info(f"Pressing single key: {parts[0]}")
                pyautogui.press(parts[0])
            return True
        except Exception as e:
            logger.error(f"Failed to press keys '{keys}': {e}")
            return False

    def scroll(self, x: int, y: int, direction: str, amount: int) -> bool:
        """
        Moves cursor to (x, y) and scrolls.
        direction: 'up' or 'down' (or positive/negative clicks).
        """
        try:
            self.smooth_move(x, y)
            clicks = amount
            if direction.lower() == "down":
                clicks = -amount
            logger.info(f"Scrolling {direction} by {amount} at ({x}, {y})")
            pyautogui.scroll(clicks)
            return True
        except Exception as e:
            logger.error(f"Failed to scroll at ({x}, {y}): {e}")
            return False

    def wait(self, seconds: float) -> bool:
        """Pauses execution."""
        try:
            logger.info(f"Waiting for {seconds} seconds...")
            time.sleep(seconds)
            return True
        except Exception as e:
            logger.error(f"Failed during wait: {e}")
            return False

    def focus_app(self, title: str) -> bool:
        """
        Finds a window whose title contains the given substring (case-insensitive)
        and brings it to the foreground using Win32 SetForegroundWindow.
        Returns True if a matching window was found and focused.
        """
        try:
            title_lower = title.lower()
            found_hwnd = None

            def enum_callback(hwnd, _):
                nonlocal found_hwnd
                if found_hwnd:
                    return True
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                if win32gui.IsIconic(hwnd):
                    # Window is minimized — restore it
                    window_title = win32gui.GetWindowText(hwnd)
                    if title_lower in window_title.lower():
                        found_hwnd = hwnd
                    return True
                window_title = win32gui.GetWindowText(hwnd)
                if title_lower in window_title.lower():
                    found_hwnd = hwnd
                    return False  # Stop enumeration
                return True

            win32gui.EnumWindows(enum_callback, None)

            if not found_hwnd:
                logger.warning(f"focus_app: No window found matching title '{title}'")
                return False

            window_title = win32gui.GetWindowText(found_hwnd)
            logger.info(f"focus_app: Found window '{window_title}' (HWND {found_hwnd}). Bringing to foreground...")

            # If minimized, restore it first
            if win32gui.IsIconic(found_hwnd):
                win32gui.ShowWindow(found_hwnd, win32con.SW_RESTORE)
                time.sleep(0.3)

            # SetForegroundWindow often fails if the calling process isn't the foreground.
            # Workaround: simulate a keypress to make the OS allow focus changes.
            try:
                # Send a harmless Alt key to bypass Windows foreground lock
                ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)  # Alt down
                ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)  # Alt up
                time.sleep(0.05)
            except Exception:
                pass

            result = win32gui.SetForegroundWindow(found_hwnd)
            time.sleep(0.5)  # Let Windows process the focus change

            logger.info(f"focus_app: SetForegroundWindow returned {result} for '{window_title}'")
            return True
        except Exception as e:
            logger.error(f"Failed to focus app with title '{title}': {e}")
            return False

    def open_app(self, app_name: str) -> bool:
        """
        Opens an application by name using the Windows Start menu search.
        Uses Win key + type + enter, then waits for the app window to appear.
        More reliable than manual key sequences because it includes retry logic.
        """
        try:
            logger.info(f"open_app: Opening '{app_name}' via Start menu search...")

            # Press Win key to open Start menu
            pyautogui.hotkey('win')
            time.sleep(0.8)

            # Type the app name to search
            pyautogui.write(app_name, interval=0.05)
            time.sleep(0.5)

            # Press Enter to launch the top result
            pyautogui.press('enter')

            # Wait for the app to launch and come to focus (up to 5 seconds)
            app_lower = app_name.lower()
            for attempt in range(10):
                time.sleep(0.5)
                try:
                    hwnd = win32gui.GetForegroundWindow()
                    if hwnd:
                        fg_title = win32gui.GetWindowText(hwnd)
                        if app_lower in fg_title.lower():
                            logger.info(f"open_app: '{app_name}' is now in foreground ('{fg_title}') after {(attempt+1)*0.5:.1f}s")
                            return True
                except Exception:
                    pass

            # If the app didn't come to focus automatically, try focus_app as fallback
            logger.info(f"open_app: '{app_name}' didn't auto-focus. Trying focus_app fallback...")
            return self.focus_app(app_name)

        except Exception as e:
            logger.error(f"Failed to open app '{app_name}': {e}")
            return False
