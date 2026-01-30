"""
Centralized model configuration for Search Agent Framework
This module provides a single source of truth for all available models across the application.
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

import logging
logger = logging.getLogger(__name__)

@dataclass
class ModelPreset:
    """Configuration for a model preset"""
    key: str
    label: str
    provider: str
    model: str
    config: Dict[str, Any]

# Load configuration from JSON file
def load_models_config() -> Dict[str, Any]:
    """Load models configuration from JSON file"""
    # Look for models-config.json in the project root
    current_file = Path(__file__).resolve()
    project_root = current_file.parents[3]  # Go up 3 levels from src/search_agent/config/models.py
    config_file = project_root / "models-config.json"
    
    if config_file.exists():
        with open(config_file, 'r') as f:
            return json.load(f)
    else:
        # Fallback to default configuration if file doesn't exist
        logger.warning(f"Warning: {config_file} not found, using fallback configuration")
        return {
            "models": {
                "gpt-4.1-2025-04-14": {
                    "label": "GPT-4.1 (Default)",
                    "provider": "OpenAIChatCompletionClient",
                    "config": {"model": "gpt-4.1-2025-04-14", "max_retries": 5}
                },
                "gpt-4o-2024-08-06": {
                    "label": "GPT-4o (2024-08-06)",
                    "provider": "OpenAIChatCompletionClient",
                    "config": {"model": "gpt-4o-2024-08-06", "max_retries": 5}
                }
            },
            "defaults": {
                "default_model": "gpt-4.1-2025-04-14",
                "action_guard_model": "gpt-4.1-nano-2025-04-14"
            }
        }

# Load the configuration
_CONFIG = load_models_config()

# Convert to ModelPreset objects
MODEL_PRESETS: Dict[str, ModelPreset] = {
    key: ModelPreset(
        key=key,
        label=model_data["label"],
        provider=model_data["provider"],
        model=model_data["config"]["model"],
        config=model_data["config"]
    )
    for key, model_data in _CONFIG["models"].items()
}

# Default model keys from config
DEFAULT_MODEL_KEY = _CONFIG["defaults"]["default_model"]
DEFAULT_ACTION_GUARD_MODEL_KEY = _CONFIG["defaults"]["action_guard_model"]

def get_model_preset(key: str) -> Optional[ModelPreset]:
    """Get a model preset by key"""
    return MODEL_PRESETS.get(key)

def get_model_config_dict(key: str) -> Optional[Dict[str, Any]]:
    """Get a model configuration dictionary for model clients"""
    preset = get_model_preset(key)
    if not preset:
        return None
    
    # Convert provider to simplified identifier for runtime selection
    provider = preset.provider
    if provider == "OpenAIChatCompletionClient":
        provider = "OpenAI"
    elif provider == "AzureOpenAIChatCompletionClient":
        provider = "AzureOpenAI"
    
    return {
        "provider": provider,
        "config": preset.config.copy()
    }

def get_openai_models() -> List[Dict[str, str]]:
    """Get list of OpenAI models for frontend dropdown"""
    return [
        {"label": preset.label, "value": preset.model, "key": key}
        for key, preset in MODEL_PRESETS.items()
        if preset.provider == "OpenAIChatCompletionClient"
    ]

def get_all_models() -> List[Dict[str, str]]:
    """Get list of all models for frontend dropdown"""
    return [
        {"label": preset.label, "value": preset.model, "key": key}
        for key, preset in MODEL_PRESETS.items()
    ]

def get_default_client_config() -> Dict[str, Any]:
    """Get default client configuration"""
    config = get_model_config_dict(DEFAULT_MODEL_KEY)
    if not config:
        raise ValueError(f"Default model key '{DEFAULT_MODEL_KEY}' not found in presets")
    return config

def get_default_action_guard_config() -> Dict[str, Any]:
    """Get default action guard configuration"""
    config = get_model_config_dict(DEFAULT_ACTION_GUARD_MODEL_KEY)
    if not config:
        raise ValueError(f"Default action guard model key '{DEFAULT_ACTION_GUARD_MODEL_KEY}' not found in presets")
    return config
