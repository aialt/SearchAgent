"""Factory for creating Orchestrator with initialized coordinators and worker pools"""

import logging
import os
from typing import Dict, Any

from langchain_core.language_models import BaseChatModel

from ..configuration.settings import SearchAgentConfig, ModelClientConfigs
from ..shared.types import RunPaths
from ..orchestration.orchestrator import Orchestrator

# NOTE: In the current search-only architecture:
# - Orchestrator connects to search_worker_pool (MCP) which manages SearchAgent workers

logger = logging.getLogger(__name__)


def create_langchain_model(
    model_client_config: Dict[str, Any] | None
) -> BaseChatModel:
    """
    Convert Autogen model client configuration to LangChain model instance.

    Args:
        model_client_config: Autogen model client configuration

    Returns:
        LangChain BaseChatModel instance
    """
    # Load config if needed
    if model_client_config is None:
        model_client_config = ModelClientConfigs.get_default_client_config()

    config = model_client_config

    provider = config.get("provider", "")
    model_config = config.get("config", {})
    model_name = model_config.get("model", "gpt-4o")

    # gpt-5 and gpt-5-mini only support temperature=1.0 (default), so skip temperature parameter entirely
    is_gpt5 = "gpt-5" in model_name.lower()
    is_gpt5_mini = "gpt-5-mini" in model_name.lower()
    temperature = None if is_gpt5 or is_gpt5_mini else model_config.get("temperature", 0)

    # Determine provider and create appropriate LangChain model
    if "Anthropic" in provider or "anthropic" in model_name.lower():
        from langchain_anthropic import ChatAnthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        kwargs = {"model": model_name, "api_key": api_key}
        if temperature is not None:
            kwargs["temperature"] = temperature
        return ChatAnthropic(**kwargs)
    elif "OpenAI" in provider or "gpt" in model_name.lower():
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        kwargs = {"model": model_name, "api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        if temperature is not None:
            kwargs["temperature"] = temperature
        return ChatOpenAI(**kwargs)
    elif "google" in provider.lower() or "gemini" in model_name.lower():
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = os.getenv("GOOGLE_API_KEY")
        kwargs = {"model": model_name, "google_api_key": api_key}
        if temperature is not None:
            kwargs["temperature"] = temperature
        return ChatGoogleGenerativeAI(**kwargs)
    else:
        # Default to OpenAI
        logger.warning(f"Unknown provider '{provider}', defaulting to OpenAI")
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        kwargs = {"model": model_name, "api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        if temperature is not None:
            kwargs["temperature"] = temperature
        return ChatOpenAI(**kwargs)


async def create_orchestrator(
    config: SearchAgentConfig,
    paths: RunPaths,
) -> Orchestrator:
    """
    Create and initialize Orchestrator connected to search_worker_pool (MCP).

    Args:
        config: Search Agent Framework configuration
        paths: Run paths for workspaces

    Returns:
        Initialized Orchestrator connected to search_worker_pool
    """

    # ===== Get Model Clients =====

    # Orchestrator uses LangChain model
    langchain_model_orchestrator = create_langchain_model(config.model_client_configs.orchestrator)

    # ===== Create Orchestrator =====

    logger.info("Creating Orchestrator with search_worker_pool MCP connection...")

    orchestrator = Orchestrator(
        name="orchestrator",
        model=langchain_model_orchestrator,  # LangChain model for Orchestrator
        sequential_thinking_command="npx",
        sequential_thinking_args=["-y", "@modelcontextprotocol/server-sequential-thinking"],
        enable_sequential_thinking=False,  # Match old SearchManager + SearchWorker flow
    )

    # Start the MCP connections
    await orchestrator.start()

    logger.info("Orchestrator initialized successfully!")

    return orchestrator