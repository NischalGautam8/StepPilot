from abc import ABC, abstractmethod
from typing import Optional

class LLMProvider(ABC):
    """
    Abstract base class defining the contract for all LLM service providers.
    Ensures absolute uniformity for text and visual analysis across providers.
    """

    @abstractmethod
    async def complete(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        json_mode: bool = False,
        temperature: float = 0.2
    ) -> str:
        """
        Perform a standard text-based chat/instruct completion.
        
        Args:
            prompt: User message prompt.
            system_prompt: System context guidelines.
            json_mode: Enforce structural JSON output if supported.
            temperature: Sampling randomness.
        """
        pass

    @abstractmethod
    async def complete_with_vision(
        self, 
        prompt: str, 
        image_bytes: bytes, 
        system_prompt: Optional[str] = None, 
        json_mode: bool = False,
        temperature: float = 0.2
    ) -> str:
        """
        Perform a vision-based completion, attaching the visual display buffer.
        
        Args:
            prompt: Text prompt accompanying the image.
            image_bytes: Raw JPEG/PNG image binary.
            system_prompt: System context guidelines.
            json_mode: Enforce structural JSON output.
            temperature: Sampling randomness.
        """
        pass

    @abstractmethod
    async def stream(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.2
    ):
        """
        Stream the completion response token-by-token.
        """
        pass

