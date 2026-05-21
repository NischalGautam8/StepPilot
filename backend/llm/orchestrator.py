import os
import logging
import asyncio
from typing import Optional, AsyncGenerator
from llm.llm_provider import LLMProvider
from llm.openai_provider import OpenAIProvider
from llm.copilot_provider import CopilotProvider
from llm.gemini_provider import GeminiProvider

logger = logging.getLogger("cursor-king-backend.llm-orchestrator")

# Timeout and retry configuration
LLM_TIMEOUT_SECONDS = 45
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # Exponential backoff: 1s, 2s, 4s


class LLMOrchestrator:
    """
    LLMOrchestrator serves as the primary system coordinator for LLM tasks.
    It reads config settings and manages dynamic fallback logic:
    If 'copilot' is requested but unavailable or errors, it transparently
    fails over to 'openai' or 'gemini' to ensure 100% service availability.
    """
    def __init__(self, provider_preference: Optional[str] = None):
        # Allow passing an explicit preference, otherwise resolve dynamically from env
        self.preference = provider_preference
        self.openai_provider = OpenAIProvider()
        self.copilot_provider = CopilotProvider()
        self.gemini_provider = GeminiProvider()
        
        logger.info(f"LLMOrchestrator initialized. Preferred provider preference: {self.preference or 'dynamic'}")

    def _get_provider(self, force_provider: Optional[str] = None) -> tuple[LLMProvider, str]:
        prov = force_provider or self.preference or os.getenv("LLM_PROVIDER", "copilot")
        prov = prov.lower()
        
        if prov == "copilot":
            return self.copilot_provider, "copilot"
        elif prov == "gemini":
            return self.gemini_provider, "gemini"
        else:
            return self.openai_provider, "openai"

    async def _call_with_timeout_and_retry(self, func, *args, **kwargs):
        """
        Call an async function with timeout and retry logic.
        
        Args:
            func: Async function to call
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            Result from the function
            
        Raises:
            Exception: If all retries fail
        """
        last_exception = None
        
        for attempt in range(MAX_RETRIES):
            try:
                # Apply timeout
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=LLM_TIMEOUT_SECONDS
                )
                return result
                
            except asyncio.TimeoutError as e:
                last_exception = e
                logger.warning(
                    f"LLM call timeout (attempt {attempt + 1}/{MAX_RETRIES}). "
                    f"Timeout: {LLM_TIMEOUT_SECONDS}s"
                )
                
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"LLM call failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}"
                )
                
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    
        # All retries failed
        raise last_exception

    async def complete(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        json_mode: bool = False,
        temperature: float = 0.2
    ) -> str:
        provider, provider_name = self._get_provider()
        
        try:
            return await self._call_with_timeout_and_retry(
                provider.complete,
                prompt=prompt,
                system_prompt=system_prompt,
                json_mode=json_mode,
                temperature=temperature
            )
        except Exception as e:
            if provider_name == "copilot":
                logger.warning(
                    f"Copilot complete request failed after {MAX_RETRIES} retries: {e}. "
                    f"Attempting automatic failover to OpenAIProvider..."
                )
                try:
                    return await self._call_with_timeout_and_retry(
                        self.openai_provider.complete,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        json_mode=json_mode,
                        temperature=temperature
                    )
                except Exception as oe:
                    logger.error(f"Failover to OpenAIProvider also failed: {oe}")
                    raise oe
            else:
                logger.error(f"OpenAI complete request failed after {MAX_RETRIES} retries: {e}")
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
            return await self._call_with_timeout_and_retry(
                provider.complete_with_vision,
                prompt=prompt,
                image_bytes=image_bytes,
                system_prompt=system_prompt,
                json_mode=json_mode,
                temperature=temperature
            )
        except Exception as e:
            if provider_name == "copilot":
                logger.warning(
                    f"Copilot vision request failed after {MAX_RETRIES} retries: {e}. "
                    f"Attempting automatic failover to OpenAIProvider..."
                )
                try:
                    return await self._call_with_timeout_and_retry(
                        self.openai_provider.complete_with_vision,
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

