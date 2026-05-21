import os
import base64
import logging
from typing import Optional, AsyncGenerator
import google.generativeai as genai
from llm.llm_provider import LLMProvider

logger = logging.getLogger("cursor-king-backend.gemini-provider")


class GeminiProvider(LLMProvider):
    """
    Google Gemini LLM provider implementing the standard LLMProvider contract.
    Uses 'gemini-1.5-flash' for fast, budget-friendly text-only reasoning.
    Uses 'gemini-1.5-pro' for advanced multimodal visual processing.
    """
    def __init__(self, api_key: Optional[str] = None):
        # Dynamically fetch API key from environment if not explicitly passed
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("No GEMINI_API_KEY found. GeminiProvider calls will fail until configured.")
        else:
            genai.configure(api_key=self.api_key)
            logger.info("Gemini API configured successfully")

    def _ensure_configured(self):
        if not self.api_key:
            # Re-read environment in case it was set after instantiation
            self.api_key = os.getenv("GEMINI_API_KEY")
            if not self.api_key:
                raise ValueError("Gemini API key is missing. Please set GEMINI_API_KEY in your environment.")
            genai.configure(api_key=self.api_key)

    async def complete(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        json_mode: bool = False,
        temperature: float = 0.2
    ) -> str:
        self._ensure_configured()
        try:
            # Resolve model name dynamically from env
            model_name = os.getenv("MODEL_NAME", "gemini-3.5-flash")
            if not model_name.startswith("gemini-"):
                model_name = "gemini-3.5-flash"
                
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_prompt
            )
            
            full_prompt = prompt
            # Add JSON instruction if needed
            if json_mode:
                full_prompt += "\n\nRespond with valid JSON only."
            
            logger.info(f"Executing Gemini text completion request using {model_name}...")
            
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=8192,
                response_mime_type="application/json" if json_mode else None
            )
            
            response = model.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            
            return response.text or ""
            
        except Exception as e:
            logger.error(f"Gemini complete call failed: {e}", exc_info=True)
            raise RuntimeError(f"Gemini text completion failed: {e}")

    async def complete_with_vision(
        self, 
        prompt: str, 
        image_bytes: bytes, 
        system_prompt: Optional[str] = None, 
        json_mode: bool = False,
        temperature: float = 0.2
    ) -> str:
        self._ensure_configured()
        try:
            # Resolve model name dynamically from env
            model_name = os.getenv("MODEL_NAME", "gemini-3.5-flash")
            if not model_name.startswith("gemini-"):
                model_name = "gemini-3.5-flash"
                
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_prompt
            )
            
            full_prompt = prompt
            # Add JSON instruction if needed
            if json_mode:
                full_prompt += "\n\nRespond with valid JSON only."
            
            logger.info(f"Executing Gemini vision request using {model_name}...")
            
            # Convert image bytes to PIL Image for Gemini
            from PIL import Image
            from io import BytesIO
            image = Image.open(BytesIO(image_bytes))
            
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=8192,
                response_mime_type="application/json" if json_mode else None
            )
            
            response = model.generate_content(
                [full_prompt, image],
                generation_config=generation_config
            )
            
            return response.text or ""
            
        except Exception as e:
            logger.error(f"Gemini vision complete call failed: {e}", exc_info=True)
            raise RuntimeError(f"Gemini vision completion failed: {e}")

    async def stream(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.2
    ) -> AsyncGenerator[str, None]:
        self._ensure_configured()
        try:
            # Resolve model name dynamically from env
            model_name = os.getenv("MODEL_NAME", "gemini-3.5-flash")
            if not model_name.startswith("gemini-"):
                model_name = "gemini-3.5-flash"
                
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_prompt
            )
            
            full_prompt = prompt
            logger.info(f"Executing Gemini streaming chat request using {model_name}...")
            
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=8192,
            )
            
            response = model.generate_content(
                full_prompt,
                generation_config=generation_config,
                stream=True
            )
            
            for chunk in response:
                if chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            logger.error(f"Gemini stream failed: {e}", exc_info=True)
            raise RuntimeError(f"Gemini streaming failed: {e}")
