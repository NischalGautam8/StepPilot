import os
import asyncio
import logging
import unittest
from unittest.mock import MagicMock, patch

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test-sprint13")

# Set fake env vars
os.environ["LLM_PROVIDER"] = "openai"
os.environ["MODEL_NAME"] = "gpt-4o-mini"
os.environ["OPENAI_API_KEY"] = "mock-key"
os.environ["EXECUTION_MODE"] = "supervised"

from task.actuator import Actuator
from task.agent import Agent

class TestSprint13Agent(unittest.TestCase):
    
    def test_element_serialization(self):
        """Test compact element serialization for LLM prompts"""
        elements = [
            {"id": "elem_1", "type": "Button", "text": "Submit", "bbox": [10, 20, 80, 30]},
            {"id": "elem_2", "type": "Edit", "text": "Username\nField", "bbox": [100, 200, 200, 40]}
        ]
        
        serialized = Agent.serialize_elements(elements)
        logger.info(f"Serialized output:\n{serialized}")
        
        # Verify format matches ID:Type"Text"@(cx,cy)
        self.assertIn('1:Button"Submit"@(50,35)', serialized)
        self.assertIn('2:Edit"Username Field"@(200,220)', serialized)

    @patch("pyautogui.moveTo")
    @patch("pyautogui.click")
    @patch("pyautogui.doubleClick")
    @patch("pyautogui.rightClick")
    @patch("pyautogui.write")
    @patch("pyautogui.press")
    @patch("pyautogui.hotkey")
    @patch("pyautogui.scroll")
    @patch("pyautogui.position", return_value=(0, 0))
    def test_actuator_commands(self, mock_pos, mock_scroll, mock_hotkey, mock_press, mock_write, mock_right_click, mock_double_click, mock_click, mock_move):
        """Test Actuator mapping coordinates and translating commands to PyAutoGUI calls"""
        current_pos = [0, 0]
        def mock_move_to(x, y=None):
            if y is not None:
                current_pos[0] = x
                current_pos[1] = y
            else:
                current_pos[0] = x[0]
                current_pos[1] = x[1]
        mock_move.side_effect = mock_move_to
        mock_pos.side_effect = lambda: (current_pos[0], current_pos[1])

        actuator = Actuator(move_duration=0.01) # Set short move duration for testing speed
        
        # 1. Click
        success = actuator.click(100, 200)
        self.assertTrue(success)
        mock_move.assert_called()
        mock_click.assert_called_with(button="left")
        
        # 2. Double Click
        success = actuator.double_click(300, 400)
        self.assertTrue(success)
        mock_double_click.assert_called()
        
        # 3. Right Click
        success = actuator.right_click(150, 250)
        self.assertTrue(success)
        mock_right_click.assert_called()
        
        # 4. Type text (uses clipboard paste)
        with patch("pyperclip.copy") as mock_copy, patch("pyperclip.paste", return_value="Hello Test") as mock_paste:
            success = actuator.type_text("Hello Test")
            self.assertTrue(success)
            mock_copy.assert_called_with("Hello Test")
            mock_hotkey.assert_called_with("ctrl", "v")
        
        # 5. Hotkey press
        success = actuator.key_press("ctrl+shift+p")
        self.assertTrue(success)
        mock_hotkey.assert_called_with("ctrl", "shift", "p")
        
        # 6. Single key press
        success = actuator.key_press("enter")
        self.assertTrue(success)
        mock_press.assert_called_with("enter")
        
        # 7. Scroll down
        success = actuator.scroll(500, 500, "down", 3)
        self.assertTrue(success)
        mock_scroll.assert_called_with(-3)

    @patch("llm.orchestrator.LLMOrchestrator.complete")
    def test_agent_get_next_action(self, mock_complete):
        """Test agent parses LLM JSON outputs into correct action schemas"""
        # Set up mock response
        mock_complete.return_value = '{"thought": "I will click the search button.", "tool": "click", "args": {"x": 500, "y": 600, "button": "left"}}'
        
        agent = Agent()
        
        loop = asyncio.get_event_loop()
        action = loop.run_until_complete(agent.get_next_action(
            query="Click the search button",
            elements=[{"id": "elem_3", "type": "Button", "text": "Search", "bbox": [480, 580, 40, 40]}],
            history=[]
        ))
        
        logger.info(f"Agent proposed action: {action}")
        
        self.assertEqual(action["tool"], "click")
        self.assertEqual(action["args"]["x"], 500)
        self.assertEqual(action["args"]["y"], 600)
        self.assertEqual(action["args"]["button"], "left")

if __name__ == "__main__":
    unittest.main()
