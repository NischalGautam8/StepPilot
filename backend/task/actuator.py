import time
import logging
import ctypes
import pyautogui
import math

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
