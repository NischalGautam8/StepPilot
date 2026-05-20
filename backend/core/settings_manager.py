import os
import json
import logging
import keyring
from typing import Dict, Any

logger = logging.getLogger("cursor-king-backend.settings-manager")

CONFIG_DIR = os.path.expanduser("~/.cursor-king")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_SETTINGS = {
    "llm_provider": "copilot",
    "model_name": "gpt-4o-mini",
    "show_debug_overlay": False,
    "auto_advance": True,
    "hotkey": "Ctrl+Alt+K",
    "use_omniparser": False,
    "use_gpu": False,
    "execution_mode": "supervised",
    "openai_base_url": ""
}

def load_settings() -> Dict[str, Any]:
    """Loads settings from config.json and fetches API keys from keyring."""
    settings = DEFAULT_SETTINGS.copy()
    
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
                settings.update(saved)
            logger.info(f"Loaded configuration settings from {CONFIG_FILE}")
        else:
            logger.info("Config file not found, using default settings")
    except Exception as e:
        logger.error(f"Failed to load config file: {e}", exc_info=True)

    # Load OpenAI API Key from keyring
    try:
        api_key = keyring.get_password("cursor-king", "openai_api_key")
        settings["openai_api_key"] = api_key or ""
    except Exception as e:
        logger.error(f"Failed to fetch OpenAI API key from keyring: {e}", exc_info=True)
        settings["openai_api_key"] = ""

    # Load Gemini API Key from keyring
    try:
        gemini_key = keyring.get_password("cursor-king", "gemini_api_key")
        settings["gemini_api_key"] = gemini_key or ""
    except Exception as e:
        logger.error(f"Failed to fetch Gemini API key from keyring: {e}", exc_info=True)
        settings["gemini_api_key"] = ""
        
    return settings
 
def save_settings(settings: Dict[str, Any]) -> None:
    """Saves settings to config.json and updates keyring/environment variables."""
    # Ensure config directory exists
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create config directory {CONFIG_DIR}: {e}")
        return

    # Extract API keys to save separately via keyring
    api_key = settings.get("openai_api_key", "")
    gemini_key = settings.get("gemini_api_key", "")
    
    # Save OpenAI API key to keyring
    try:
        if api_key:
            keyring.set_password("cursor-king", "openai_api_key", api_key)
            logger.info("OpenAI API key saved securely via keyring")
        else:
            try:
                keyring.delete_password("cursor-king", "openai_api_key")
                logger.info("OpenAI API key removed from keyring")
            except keyring.errors.PasswordDeleteError:
                pass
    except Exception as e:
        logger.error(f"Failed to save OpenAI API key to keyring: {e}", exc_info=True)

    # Save Gemini API key to keyring
    try:
        if gemini_key:
            keyring.set_password("cursor-king", "gemini_api_key", gemini_key)
            logger.info("Gemini API key saved securely via keyring")
        else:
            try:
                keyring.delete_password("cursor-king", "gemini_api_key")
                logger.info("Gemini API key removed from keyring")
            except keyring.errors.PasswordDeleteError:
                pass
    except Exception as e:
        logger.error(f"Failed to save Gemini API key to keyring: {e}", exc_info=True)

    # Filter out api keys and build config to write to file
    config_to_save = {k: v for k, v in settings.items() if k not in ["openai_api_key", "gemini_api_key"]}
    
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_to_save, f, indent=2)
        logger.info(f"Saved configuration to {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Failed to write config file: {e}", exc_info=True)

    # Update environment variables immediately
    apply_settings(settings)

def apply_settings(settings: Dict[str, Any] = None) -> None:
    """Applies settings to the current process environment."""
    if settings is None:
        settings = load_settings()
        
    provider = settings.get("llm_provider", "copilot").lower()
    api_key = settings.get("openai_api_key", "")
    gemini_key = settings.get("gemini_api_key", "")
    base_url = settings.get("openai_base_url", "")
    
    os.environ["LLM_PROVIDER"] = provider
    os.environ["MODEL_NAME"] = settings.get("model_name", "gpt-4o-mini")
    os.environ["USE_OMNIPARSER"] = str(settings.get("use_omniparser", False)).lower()
    os.environ["USE_GPU"] = str(settings.get("use_gpu", False)).lower()
    os.environ["EXECUTION_MODE"] = settings.get("execution_mode", "supervised").lower()
    
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
    elif "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]

    if base_url:
        os.environ["OPENAI_BASE_URL"] = base_url
    elif "OPENAI_BASE_URL" in os.environ:
        del os.environ["OPENAI_BASE_URL"]

    if gemini_key:
        os.environ["GEMINI_API_KEY"] = gemini_key
    elif "GEMINI_API_KEY" in os.environ:
        del os.environ["GEMINI_API_KEY"]
    
    logger.info(
        f"Applied settings: LLM_PROVIDER={provider}, MODEL_NAME={os.environ['MODEL_NAME']}, "
        f"EXECUTION_MODE={os.environ['EXECUTION_MODE']}, "
        f"OPENAI_BASE_URL={base_url or 'Default'}, "
        f"OPENAI_API_KEY={'***' if api_key else 'None'}, "
        f"GEMINI_API_KEY={'***' if gemini_key else 'None'}"
    )
