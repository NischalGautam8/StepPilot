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
    "hotkey": "Ctrl+Alt+K"
}

def load_settings() -> Dict[str, Any]:
    """Loads settings from config.json and fetches API key from keyring."""
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

    # Load OpenAI API Key from Windows Credential Manager via keyring
    try:
        api_key = keyring.get_password("cursor-king", "openai_api_key")
        settings["openai_api_key"] = api_key or ""
    except Exception as e:
        logger.error(f"Failed to fetch API key from keyring: {e}", exc_info=True)
        settings["openai_api_key"] = ""
        
    return settings

def save_settings(settings: Dict[str, Any]) -> None:
    """Saves settings to config.json and updates keyring/environment variables."""
    # Ensure config directory exists
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create config directory {CONFIG_DIR}: {e}")
        return

    # Extract API key to save separately via keyring
    api_key = settings.get("openai_api_key", "")
    
    # Save password to keyring
    try:
        if api_key:
            keyring.set_password("cursor-king", "openai_api_key", api_key)
            logger.info("OpenAI API key saved securely via keyring")
        else:
            # Delete if exists
            try:
                keyring.delete_password("cursor-king", "openai_api_key")
                logger.info("OpenAI API key removed from keyring")
            except keyring.errors.PasswordDeleteError:
                pass
    except Exception as e:
        logger.error(f"Failed to save API key to keyring: {e}", exc_info=True)

    # Filter out api key and build config to write to file
    config_to_save = {k: v for k, v in settings.items() if k != "openai_api_key"}
    
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
    
    os.environ["LLM_PROVIDER"] = provider
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
    elif "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]
        
    logger.info(f"Applied settings: LLM_PROVIDER={provider}, OPENAI_API_KEY={'***' if api_key else 'None'}")
