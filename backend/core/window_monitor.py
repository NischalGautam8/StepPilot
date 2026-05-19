"""
Window focus monitor for detecting active window changes during guidance.
"""
import asyncio
import logging
from typing import Optional, Callable
import ctypes
from ctypes import wintypes

logger = logging.getLogger(__name__)

# Windows API functions
user32 = ctypes.windll.user32
GetForegroundWindow = user32.GetForegroundWindow
GetWindowTextW = user32.GetWindowTextW
GetWindowTextLengthW = user32.GetWindowTextLengthW


class WindowMonitor:
    """
    Monitors active window changes and triggers callbacks.
    """
    
    def __init__(self, check_interval: float = 1.0):
        self.check_interval = check_interval
        self._current_window_title: Optional[str] = None
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._on_window_change: Optional[Callable] = None
        
    def get_active_window_title(self) -> str:
        """Get the title of the currently active window"""
        try:
            hwnd = GetForegroundWindow()
            if hwnd == 0:
                return ""
                
            length = GetWindowTextLengthW(hwnd)
            if length == 0:
                return ""
                
            buffer = ctypes.create_unicode_buffer(length + 1)
            GetWindowTextW(hwnd, buffer, length + 1)
            return buffer.value
        except Exception as e:
            logger.error(f"Failed to get active window title: {e}")
            return ""
            
    def start_monitoring(self, on_window_change: Callable[[str, str], None]):
        """
        Start monitoring for window changes.
        
        Args:
            on_window_change: Callback function(old_title, new_title) called when window changes
        """
        if self._monitoring:
            logger.warning("Window monitoring already started")
            return
            
        self._on_window_change = on_window_change
        self._current_window_title = self.get_active_window_title()
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Window monitoring started. Current window: '{self._current_window_title}'")
        
    def stop_monitoring(self):
        """Stop monitoring for window changes"""
        if not self._monitoring:
            return
            
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
        logger.info("Window monitoring stopped")
        
    async def _monitor_loop(self):
        """Main monitoring loop"""
        try:
            while self._monitoring:
                await asyncio.sleep(self.check_interval)
                
                new_title = self.get_active_window_title()
                
                # Check if window changed
                if new_title != self._current_window_title:
                    old_title = self._current_window_title
                    self._current_window_title = new_title
                    
                    logger.info(
                        f"Window changed: '{old_title}' -> '{new_title}'"
                    )
                    
                    # Trigger callback
                    if self._on_window_change:
                        try:
                            if asyncio.iscoroutinefunction(self._on_window_change):
                                await self._on_window_change(old_title, new_title)
                            else:
                                self._on_window_change(old_title, new_title)
                        except Exception as e:
                            logger.error(f"Error in window change callback: {e}", exc_info=True)
                            
        except asyncio.CancelledError:
            logger.debug("Window monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Error in window monitoring loop: {e}", exc_info=True)
            
    @property
    def current_window(self) -> Optional[str]:
        """Get the current window title"""
        return self._current_window_title
        
    @property
    def is_monitoring(self) -> bool:
        """Check if monitoring is active"""
        return self._monitoring


# Global window monitor instance
window_monitor = WindowMonitor()
