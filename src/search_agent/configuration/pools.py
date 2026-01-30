"""Pool size configuration loader"""

import yaml
from pathlib import Path
from typing import Dict, Any

import logging
logger = logging.getLogger(__name__)

def load_pool_config() -> Dict[str, Any]:
    """Load pool configuration from YAML file.

    Returns:
        Dictionary containing pool configuration.
        Falls back to defaults if pool_config.yaml not found.
    """
    current_file = Path(__file__).resolve()
    project_root = current_file.parents[3]  # Up 3 levels from src/search_agent/config/pools.py
    config_file = project_root / "pool_config.yaml"

    if config_file.exists():
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)
    else:
        # Fallback defaults if YAML file not found
        logger.warning(f"Warning: {config_file} not found, using default pool sizes")
        return {
            "pools": {
                "search": {"max_pool_size": 5},
                "browser": {"max_pool_size": 5},
                "code": {"max_pool_size": 2},
                "filesystem": {"max_pool_size": 2},
                "media": {"max_pool_size": 1}
            }
        }


# Load configuration at module import
_CONFIG = load_pool_config()


def get_pool_size(pool_name: str) -> int:
    """Get pool size for a specific pool type.

    Args:
        pool_name: Pool identifier ('search', 'browser', 'code', 'filesystem', 'media')

    Returns:
        Pool size as integer, defaults to 1 if not configured.
    """
    return _CONFIG.get("pools", {}).get(pool_name, {}).get("max_pool_size", 1)
