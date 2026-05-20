import os
import base64
import logging
from typing import Optional, AsyncGenerator
from llm.llm_provider import LLMProvider

logger = logging.getLogger("cursor-king-backend.copilot-provider")

class CopilotProvider(LLMProvider):
    """
    GitHub Copilot SDK LLM provider implementing the LLMProvider contract.
    Utilizes the official local copilot-sdk agent runtime.
    """
    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token or os.getenv("GITHUB_TOKEN") or os.getenv("COPILOT_TOKEN")
        self.client = None
        self._initialized = False

    async def _ensure_client(self):
        if self._initialized:
            return
        
        try:
            from copilot import CopilotClient
            logger.info("Initializing CopilotClient via GitHub Copilot SDK...")
            self.client = CopilotClient(auto_start=True)
            await self.client.start()
            self._initialized = True
            logger.info("CopilotClient started successfully.")
        except Exception as e:
            logger.error(f"Failed to start CopilotClient: {e}", exc_info=True)
            self._initialized = False
            raise RuntimeError(f"GitHub Copilot SDK initialization failed: {e}")

    async def complete(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        json_mode: bool = False,
        temperature: float = 0.2
    ) -> str:
        await self._ensure_client()
        session = None
        try:
            from copilot.session import PermissionHandler
            
            # Start a new conversation session
            session = await self.client.create_session(
                on_permission_request=PermissionHandler.approve_all,
                github_token=self.github_token
            )
            
            # Standardize system prompt insertion
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"System Instructions:\n{system_prompt}\n\nUser Request:\n{prompt}"
                if json_mode:
                    full_prompt += "\n\nIMPORTANT: Return ONLY a valid JSON object matching the requested schema."
            
            logger.info("Sending prompt to Copilot session...")
            response = await session.send_and_wait(full_prompt, timeout=60.0)
            
            if response and hasattr(response, 'data'):
                from copilot.generated.session_events import AssistantMessageData
                if isinstance(response.data, AssistantMessageData):
                    return response.data.content or ""
            
            # Fallback: scan session message logs
            messages = await session.get_messages()
            for msg in reversed(messages):
                from copilot.generated.session_events import AssistantMessageData
                if isinstance(msg.data, AssistantMessageData):
                    return msg.data.content or ""
                    
            return ""
        except Exception as e:
            logger.error(f"Copilot complete call failed: {e}", exc_info=True)
            raise RuntimeError(f"Copilot complete failed: {e}")
        finally:
            if session:
                try:
                    await session.destroy()
                except Exception:
                    pass

    async def complete_with_vision(
        self, 
        prompt: str, 
        image_bytes: bytes, 
        system_prompt: Optional[str] = None, 
        json_mode: bool = False,
        temperature: float = 0.2
    ) -> str:
        logger.warning("Copilot SDK does not support vision natively. Falling back to text-first mode.")
        return await self.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            json_mode=json_mode,
            temperature=temperature
        )

    async def stream(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.2
    ) -> AsyncGenerator[str, None]:
        """
        Stream completion chunks. Falls back to whole-response yielding for session boundaries.
        """
        content = await self.complete(prompt, system_prompt, False, temperature)
        yield content

