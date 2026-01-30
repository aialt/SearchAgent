"""SearchExecutor - Pure LangChain executor for web search and crawling via MCP"""

from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncGenerator, Any, Mapping, Sequence

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_mcp_adapters.client import MultiServerMCPClient

import logging
logger = logging.getLogger(__name__)

# Compute firecrawl-mcp-server paths relative to this module
_MODULE_DIR = Path(__file__).parent
_FIRECRAWL_SERVER_DIR = _MODULE_DIR.parent / "infrastructure" / "firecrawl-mcp-server"
_FIRECRAWL_INDEX_JS = str(_FIRECRAWL_SERVER_DIR / "dist" / "index.js")

class SearchExecutor:
    """
    Pure LangChain executor for web search and crawling via Firecrawl MCP server.

    This executor connects to the Firecrawl MCP server to provide web search, 
    page crawling, and information retrieval capabilities.

    Architecture:
    - Uses LangChain BaseChatModel for LLM interactions
    - Uses MultiServerMCPClient to connect to Firecrawl MCP server
    - Uses create_agent() to build the agent graph
    - Supports both streaming and non-streaming execution
    - Stateless - each run is independent

    Usage:
        executor = SearchExecutor(model=ChatOpenAI(model="gpt-4"))
        await executor.start()
        result = await executor.run("What is LangChain?")
        await executor.close()
    """

    DEFAULT_DESCRIPTION = (
        "Performs web searches and crawls web pages using the Firecrawl MCP server. "
        "Can search for information, retrieve web content, and analyze search results."
    )

    DEFAULT_SYSTEM_MESSAGE = (
        "You are Search Agent, a specialist responsible for web searching and information retrieval. "
        "Use the Firecrawl MCP server to search the web, crawl pages, and extract relevant information "
        "on the user's behalf. Provide comprehensive and accurate search results. "
        "Don't use crawl unless necessary for deeper information retrieval. "
        "VERBOSITY & DATA FIDELITY: Your goal is to be a COMPREHENSIVE researcher.\n"
        "- **MAXIMIZE INFORMATION DENSITY**: When extracting attributes, prefer preserving the full richness of the source text over simplifying it into categories. "
        "Your job is to *transport* information, not *compress* it.\n"
        "- **PRESERVE NUANCE**: If a source provides a complex, multi-faceted description (e.g., mentioning specific influences, techniques, or fusion elements), "
        "you MUST include these details. Do not flatten complex descriptions into simple generic tags.\n"
        "- Do not simplify unless explicitly asked. Include 1-2 sentences of context to ensure the full meaning is retained.\n\n"
        "BROWSER ESCALATION: If you find relevant URLs but cannot extract the needed information "
        "(e.g., JavaScript-heavy pages, tables that didn't render, login walls, or content in images/PDFs), "
        "include in your response: '[BROWSER_RECOMMENDED] <url1>, <url2>, ...' "
        "to indicate these pages should be visited by a browser agent."
    )

    # Firecrawl MCP Server Configuration
    DEFAULT_COMMAND = "/usr/local/bin/node"
    DEFAULT_ARGS: Sequence[str] = (_FIRECRAWL_INDEX_JS,)
    DEFAULT_SERVER_NAME = "firecrawl"
    DEFAULT_ENV = {
        "FIRECRAWL_API_KEY": "fc-fdcd31ba1ca942308374d93c795dc98c"
    }

    def __init__(
        self,
        *,
        name: str = "search_agent",
        model: BaseChatModel,
        description: str | None = None,
        command: str | None = None,
        args: Sequence[str] | None = None,
        env: Mapping[str, str] | None = None,
        system_message: str | None = None,
    ) -> None:
        """
        Initialize SearchExecutor.

        Args:
            name: Executor name
            model: LangChain chat model (ChatOpenAI, ChatAnthropic, etc.)
            description: Agent description (for documentation)
            command: Command to start MCP server (default: "npx")
            args: Arguments for MCP server command (default: ["-y", "firecrawl-mcp"])
            env: Environment variables for MCP server
            system_message: Custom system message for the agent
        """
        self.name = name
        self.model = model
        self._description = description or self.DEFAULT_DESCRIPTION

        # Resolve MCP server configuration
        self._command = command or os.getenv("SEARCH_AGENT_COMMAND", self.DEFAULT_COMMAND)
        self._args = list(args) if args is not None else list(self.DEFAULT_ARGS)

        # Merge environment variables (custom + defaults)
        merged_env = dict(self.DEFAULT_ENV)
        if env:
            merged_env.update(env)
        self._env = merged_env

        # System message
        self._system_message = system_message or self.DEFAULT_SYSTEM_MESSAGE

        # MCP client and agent (initialized in start())
        self._mcp_client: MultiServerMCPClient | None = None
        self._agent_graph: Any = None

    async def start(self) -> None:
        """
        Initialize MCP connection and build the agent graph.
        
        This method:
        1. Connects to the Firecrawl MCP server
        2. Retrieves available tools from the server
        3. Builds the LangChain agent graph with the model and tools
        
        Must be called before run() or stream().
        """
        # Build MCP server configuration for Firecrawl
        mcp_servers = {
            "firecrawl": {
                "command": self._command,
                "args": self._args,
                "env": self._env,
                "transport": "stdio",
                "cwd": str(_FIRECRAWL_SERVER_DIR),  # Working directory for node_modules
            }
        }

        # Create MultiServerMCPClient
        self._mcp_client = MultiServerMCPClient(mcp_servers)

        # Get tools from the Firecrawl MCP server
        tools = await self._mcp_client.get_tools()

        # filter the useful tools only
        useful_tool_names = ["firecrawl_scrape", "firecrawl_search", "firecrawl_crawl", "firecrawl_extract"]
        tools = [tool for tool in tools if tool.name in useful_tool_names]
        logger.info(f"SearchExecutor: Loaded tools: {[tool.name for tool in tools]}")


        # Create the agent using LangChain's create_agent helper
        self._agent_graph = create_agent(
            model=self.model,
            tools=tools,
            system_prompt=self._system_message,
        )

    async def run(
        self,
        query: str | list[dict],
    ) -> dict[str, Any]:
        """
        Execute the agent workflow and return the complete result.

        Args:
            query: Either a string query or a list of message dicts
                  Examples:
                  - "What is LangChain?"
                  - [{"role": "user", "content": "What is LangChain?"}]

        Returns:
            Dictionary containing the agent's response with 'messages' key
            containing the full conversation history including tool calls

        Raises:
            RuntimeError: If start() has not been called first
        """
        if not self._agent_graph:
            raise RuntimeError("Agent not started. Call start() first.")

        # Convert string input to message format
        if isinstance(query, str):
            messages = [{"role": "user", "content": query}]
        else:
            messages = query

        # Execute agent
        # result = await self._agent_graph.ainvoke({"messages": messages})
        result = await self._agent_graph.ainvoke({"messages": messages}, config={"recursion_limit": 50}) # increase the recursion limit to 50
        return result

    async def stream(
        self,
        query: str | list[dict],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Execute the agent workflow and stream updates as they occur.

        Args:
            query: Either a string query or a list of message dicts
                  Examples:
                  - "What is LangChain?"
                  - [{"role": "user", "content": "What is LangChain?"}]

        Yields:
            Stream of update dictionaries containing intermediate steps
            (tool calls, agent reasoning, etc.)

        Raises:
            RuntimeError: If start() has not been called first
            
        Example:
            async for update in agent.stream("What is LangChain?"):
                print(update)
        """
        if not self._agent_graph:
            raise RuntimeError("Agent not started. Call start() first.")

        # Convert string input to message format
        if isinstance(query, str):
            messages = [{"role": "user", "content": query}]
        else:
            messages = query

        # Stream execution with updates
        async for chunk in self._agent_graph.astream(
            {"messages": messages}, 
            stream_mode="updates"
        ):
            yield chunk


    async def close(self) -> None:
        """
        Close MCP connections and cleanup resources.
        
        Note: MultiServerMCPClient will automatically clean up subprocesses
        when garbage collected. This method is provided for explicit cleanup
        if needed, but is optional.
        """
        # MultiServerMCPClient doesn't support manual __aexit__ when not used
        # as a context manager. The subprocess will be cleaned up automatically
        # when the object is garbage collected.
        self._mcp_client = None
        self._agent_graph = None

    # Properties
    @property
    def description(self) -> str:
        """Agent description string."""
        return self._description

    @property
    def system_message(self) -> str:
        """System prompt used by the agent."""
        return self._system_message