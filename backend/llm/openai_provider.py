import os
import base64
import logging
from typing import Optional, AsyncGenerator
from openai import AsyncOpenAI
from llm.llm_provider import LLMProvider

logger = logging.getLogger("cursor-king-backend.openai-provider")

class OpenAIProvider(LLMProvider):
    """
    OpenAI LLM provider implementing the standard LLMProvider contract.
    Uses 'gpt-4o-mini' for fast, budget-friendly text-only reasoning.
    Uses 'gpt-4o' for advanced multimodal visual processing.
    """
    def __init__(self, api_key: Optional[str] = None):
        # Dynamically fetch API key from environment if not explicitly passed
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("No OPENAI_API_KEY found. OpenAIProvider calls will fail until configured.")
        
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None

    def _ensure_client(self):
        if not self.client:
            # Re-read environment in case it was set after instantiation
            self.api_key = os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OpenAI API key is missing. Please set OPENAI_API_KEY in your environment.")
            self.client = AsyncOpenAI(api_key=self.api_key)

    async def complete(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        json_mode: bool = False,
        temperature: float = 0.2
    ) -> str:
        self._ensure_client()
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            logger.info("Executing OpenAI text completion request using gpt-4o-mini...")
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"} if json_mode else None
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"OpenAI complete call failed: {e}", exc_info=True)
            raise RuntimeError(f"OpenAI text completion failed: {e}")

    async def complete_with_vision(
        self, 
        prompt: str, 
        image_bytes: bytes, 
        system_prompt: Optional[str] = None, 
        json_mode: bool = False,
        temperature: float = 0.2
    ) -> str:
        self._ensure_client()
        try:
            # Encode image bytes to base64
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
                
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            })

            logger.info("Executing OpenAI vision request using gpt-4o...")
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"} if json_mode else None
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"OpenAI vision complete call failed: {e}", exc_info=True)
            raise RuntimeError(f"OpenAI vision completion failed: {e}")

    async def stream(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.2
    ) -> AsyncGenerator[str, None]:
        self._ensure_client()
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            logger.info("Executing OpenAI streaming chat request...")
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=temperature,
                stream=True
            )
            async for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            logger.error(f"OpenAI stream failed: {e}", exc_info=True)
            raise RuntimeError(f"OpenAI streaming failed: {e}")

