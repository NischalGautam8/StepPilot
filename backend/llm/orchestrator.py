import os
import logging
from typing import Optional, AsyncGenerator
from llm.llm_provider import LLMProvider
from llm.openai_provider import OpenAIProvider
from llm.copilot_provider import CopilotProvider

logger = logging.getLogger("cursor-king-backend.llm-orchestrator")

class LLMOrchestrator:
    """
    LLMOrchestrator serves as the primary system coordinator for LLM tasks.
    It reads config settings and manages dynamic fallback logic:
    If 'copilot' is requested but unavailable or errors, it transparently
    fails over to 'openai' to ensure 100% service availability.
    """
    def __init__(self, provider_preference: Optional[str] = None):
        # Read from environment, default to 'copilot'
        self.preference = provider_preference or os.getenv("LLM_PROVIDER", "copilot").lower()
        self.openai_provider = OpenAIProvider()
        self.copilot_provider = CopilotProvider()
        
        logger.info(f"LLMOrchestrator initialized. Preferred provider: {self.preference}")

    def _get_provider(self, force_provider: Optional[str] = None) -> tuple[LLMProvider, str]:
        prov = force_provider or self.preference
        
        if prov == "copilot":
            return self.copilot_provider, "copilot"
        else:
            return self.openai_provider, "openai"

    async def complete(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        json_mode: bool = False,
        temperature: float = 0.2
    ) -> str:
        provider, provider_name = self._get_provider()
        
        try:
            return await provider.complete(
                prompt=prompt,
                system_prompt=system_prompt,
                json_mode=json_mode,
                temperature=temperature
            )
        except Exception as e:
            if provider_name == "copilot":
                logger.warning(
                    f"Copilot complete request failed: {e}. "
                    f"Attempting automatic failover to OpenAIProvider..."
                )
                try:
                    return await self.openai_provider.complete(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        json_mode=json_mode,
                        temperature=temperature
                    )
                except Exception as oe:
                    logger.error(f"Failover to OpenAIProvider also failed: {oe}")
                    raise oe
            else:
                logger.error(f"OpenAI complete request failed: {e}")
                raise e

    async def complete_with_vision(
        self, 
        prompt: str, 
        image_bytes: bytes, 
        system_prompt: Optional[str] = None, 
        json_mode: bool = False,
        temperature: float = 0.2
    ) -> str:
        provider, provider_name = self._get_provider()
        
        try:
            return await provider.complete_with_vision(
                prompt=prompt,
                image_bytes=image_bytes,
                system_prompt=system_prompt,
                json_mode=json_mode,
                temperature=temperature
            )
        except Exception as e:
            if provider_name == "copilot":
                logger.warning(
                    f"Copilot vision request failed: {e}. "
                    f"Attempting automatic failover to OpenAIProvider..."
                )
                try:
                    return await self.openai_provider.complete_with_vision(
                        prompt=prompt,
                        image_bytes=image_bytes,
                        system_prompt=system_prompt,
                        json_mode=json_mode,
                        temperature=temperature
                    )
                except Exception as oe:
                    logger.error(f"Failover vision request to OpenAIProvider also failed: {oe}")
                    raise oe
            else:
                logger.error(f"OpenAI vision request failed: {e}")
                raise e

    async def stream(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.2
    ) -> AsyncGenerator[str, None]:
        provider, provider_name = self._get_provider()
        
        try:
            async for chunk in provider.stream(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature
            ):
                yield chunk
        except Exception as e:
            if provider_name == "copilot":
                logger.warning(
                    f"Copilot streaming request failed: {e}. "
                    f"Attempting automatic failover to OpenAIProvider..."
                )
                try:
                    async for chunk in self.openai_provider.stream(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature
                    ):
                        yield chunk
                except Exception as oe:
                    logger.error(f"Failover streaming to OpenAIProvider also failed: {oe}")
                    raise oe
            else:
                logger.error(f"OpenAI streaming request failed: {e}")
                raise e

