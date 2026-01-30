"""Orchestrator - Top-level LangChain-based orchestrator coordinating search_worker_pool."""

import os
import sys
import logging
from typing import AsyncGenerator, Any, List, Dict, Mapping, Sequence
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)

DEFAULT_COMMAND = sys.executable
DEFAULT_ARGS: Sequence[str] = ("-m", "search_agent.mcp_servers.search_worker_pool")


class Orchestrator:
    """
    Orchestrator using LangChain's create_agent for task orchestration.

    The Orchestrator connects to the search_worker_pool MCP server and exposes
    the `execute_subtasks` tool to the LLM for parallel task execution.

    Architecture:
    - Connects to search_worker_pool MCP server for parallel execution
    - Optional Sequential Thinking MCP Server for planning complex tasks

    Key advantages:
    - No max_turns limit - LangChain agent loops until task complete
    - Simple implementation using create_agent + MCP worker pool
    - Built-in streaming support
    - Automatic tool calling and result synthesis
    - Manager/Worker architecture: Orchestrator → SearchWorkerPool → SearchAgent
    """

    def __init__(
        self,
        name: str,
        model: BaseChatModel,
        sequential_thinking_command: str = "npx",
        sequential_thinking_args: list[str] | None = None,
        enable_sequential_thinking: bool = False,
        command: str | None = None,
        args: Sequence[str] | None = None,
        env: Mapping[str, str] | None = None,
        system_message: str | None = None,
    ):
        """
        Initialize Orchestrator.

        Args:
            name: Agent name
            model: LangChain chat model for Orchestrator (ChatOpenAI, ChatAnthropic, etc.)
            sequential_thinking_command: Command for Sequential Thinking MCP
            sequential_thinking_args: Arguments for Sequential Thinking
            enable_sequential_thinking: Whether to enable Sequential Thinking MCP
        """
        self.name = name
        self.model = model
        self._sequential_thinking_command = sequential_thinking_command
        self._sequential_thinking_args = sequential_thinking_args or [
            "@modelcontextprotocol/server-sequential-thinking"
        ]
        self._enable_sequential_thinking = enable_sequential_thinking
        self._command = command or DEFAULT_COMMAND
        self._args = list(args) if args is not None else list(DEFAULT_ARGS)
        self._env = dict(os.environ if env is None else env)

        # MCP client for Sequential Thinking (optional)
        self._mcp_client: MultiServerMCPClient | None = None
        self._agent_graph: Any = None

        # System prompt for the agent
        self._system_prompt = system_message or self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        return"""You are the Search Manager. You coordinate a pool of workers to retrieve information.

    ## CORE STRATEGY: ANCHOR & EXPAND
    1. **IDENTIFY ANCHORS**: For complex queries (riddles, multi-constraint questions), do NOT search the whole description at once.
    - Isolate 1–2 **most distinctive** constraints (the "anchors": e.g., a specific voice actor, platform, series name).
    - Search the anchor first to get candidate people/works, then combine with other constraints to refine.

    ## KEYWORD STRATEGY (CRITICAL)
    - **Keyword Reduction**: If a long query is noisy or yields no good results, DRASTICALLY reduce keywords. Keep only proper nouns and unique events.
    - **Concept Abstraction**: If concrete details fail, search for the underlying story/anecdote instead of copying the whole riddle.
    - **Language Agnostic**: If the context is tied to a region (e.g., clearly Chinese/Japanese works), also try queries in the **native language**.

    ## STRATEGY: DISCOVERY FIRST
    1. **FIND THE LIST**: If the user asks for "Top 5 X" or "List of Y", first find an existing list or ranking. Do NOT guess members.
    2. **GET DETAILS**: Once you have candidates, generate subtasks to verify the remaining constraints for each candidate entity.

    ## STATE MANAGEMENT & DEPENDENCY
    - **DEPENDENCY CHECK**: Before generating subtasks, ask: "Do I already have specific names/dates/entities to query?"
    - If **NO**: run a single broad discovery search subtask first.
    - If **YES**: verify attributes for **each named candidate** in parallel.
    - **DEDUPLICATE** entities before querying to avoid repeated work.

    ## PROMPT ENGINEERING FOR WORKERS
    - Workers are STATELESS. Each subtask must be **SELF-CONTAINED**.
    - **NEVER** write "find details for the above".
    - **ALWAYS** include the explicit entity name (game/anime/person/etc.) and key constraints in each subtask.
    - Use search operators when helpful: quotes "" for exact phrases (titles, names), OR for synonyms.

    ## OUTPUT TO HOST
    1. **CANDIDATE LIST (REQUIRED when relevant)**  
    For each plausible candidate entity you find:
    - name  
    - type (e.g., game, anime, person)  
    - match_score: 0–100 (your subjective fit to all constraints)  
    - evidence_for: 1–3 short bullets with key facts + URLs  
    - evidence_missing_or_against: 1–3 short bullets

    2. **UNCERTAINTY RULES**
    - If web search cannot uniquely identify a single entity, you MUST say:
        - that the answer is **not uniquely determined from web data**, and
        - which candidates are most plausible and why.
    - You **MUST NOT** claim that the game/person "does not exist" or that the question is "unanswerable".  
        Your role is to surface and rank candidates; the Host will decide the final answer using model knowledge if needed.

    3. **FAILURE ANALYSIS**
    - If a search path fails (no useful results), briefly state **what you tried** and **why it may have failed** (e.g., wrong year, too specific, only spam pages).
    - Always keep the summary concise and focused on helping the Host choose among candidates.
    """

    async def start(self):
        """
        Initialize MCP connection to search_worker_pool and build the agent graph.

        This method:
        1. Sets up PYTHONPATH for the subprocess
        2. Connects to the search_worker_pool MCP server
        3. Retrieves available tools (execute_subtasks)
        4. Builds the LangChain agent graph with the model and tools
        """
        env = dict(self._env)
        if "PYTHONPATH" not in env:
            src_path = Path(__file__).parent.parent.parent.absolute()
            env["PYTHONPATH"] = str(src_path)

        mcp_servers: dict[str, dict[str, Any]] = {
            "search_worker_pool": {
                "command": self._command,
                "args": self._args,
                "env": env,
                "transport": "stdio",
            }
        }

        if self._enable_sequential_thinking:
            mcp_servers["sequential_thinking"] = {
                "command": self._sequential_thinking_command,
                "args": self._sequential_thinking_args,
                "transport": "stdio",
            }

        self._mcp_client = MultiServerMCPClient(mcp_servers)
        tools = await self._mcp_client.get_tools()

        self._agent_graph = create_agent(
            model=self.model,
            tools=tools,
            system_prompt=self._system_prompt,
        )

    async def run(
        self,
        messages: list[dict] | str,
    ) -> dict[str, Any]:
        """
        Execute the agent workflow (non-streaming).

        Args:
            messages: Input messages (list of dicts) or string query

        Returns:
            Final result
        """
        if not self._agent_graph:
            raise RuntimeError("Agent not started. Call start() first.")

        # Convert string input to message format
        if isinstance(messages, str):
            query_preview = messages[:200] + "..." if len(messages) > 200 else messages
            logger.info(f"[Orchestrator] Query: {query_preview}")
            messages = [{"role": "user", "content": messages}]
        else:
            # Log the last user message
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    query_preview = content[:200] + "..." if len(content) > 200 else content
                    logger.info(f"[Orchestrator] Query: {query_preview}")
                    break

        # Prepare inputs
        inputs = {"messages": messages}

        # Non-streaming execution
        result = await self._agent_graph.ainvoke(inputs)

        # Log final response
        if result and 'messages' in result:
            last_msg = result['messages'][-1] if result['messages'] else None
            if last_msg and hasattr(last_msg, 'content'):
                content = last_msg.content
                response_preview = content[:300] + "..." if len(content) > 300 else content
                logger.info(f"[Orchestrator] Final response: {response_preview}")

        return result

    async def stream(
        self,
        messages: list[dict] | str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Execute the agent workflow (streaming).

        Args:
            messages: Input messages (list of dicts) or string query

        Yields:
            Stream of updates
        """
        if not self._agent_graph:
            raise RuntimeError("Agent not started. Call start() first.")

        # Convert string input to message format
        if isinstance(messages, str):
            query_preview = messages[:200] + "..." if len(messages) > 200 else messages
            logger.info(f"[Orchestrator] Query: {query_preview}")
            messages = [{"role": "user", "content": messages}]
        else:
            # Log the last user message
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    query_preview = content[:200] + "..." if len(content) > 200 else content
                    logger.info(f"[Orchestrator] Query: {query_preview}")
                    break

        # Prepare inputs
        inputs = {"messages": messages}

        # Stream execution with updates
        async for chunk in self._agent_graph.astream(
            inputs, 
            stream_mode="updates",
            config={"recursion_limit": 50}  # increase the recursion limit to 50
        ):
            # Log tool calls and responses
            if 'agent' in chunk:
                for msg in chunk['agent'].get('messages', []):
                    # Log tool calls
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tc in msg.tool_calls:
                            tool_name = tc.get('name', 'unknown')
                            tool_args = tc.get('args', {})
                            # Truncate long args for readability
                            args_str = str(tool_args)
                            if len(args_str) > 500:
                                args_str = args_str[:500] + "..."
                            logger.info(f"[Orchestrator] Tool call: {tool_name}")
                            logger.info(f"[Orchestrator]   Args: {args_str}")
                    # Log AI responses (not tool results)
                    elif hasattr(msg, 'content') and msg.content and not hasattr(msg, 'tool_call_id'):
                        content = msg.content
                        if len(content) > 300:
                            content = content[:300] + "..."
                        logger.info(f"[Orchestrator] Response: {content}")
            # Log tool results
            if 'tools' in chunk:
                for msg in chunk['tools'].get('messages', []):
                    if hasattr(msg, 'content'):
                        content = msg.content if isinstance(msg.content, str) else str(msg.content)
                        if len(content) > 500:
                            content = content[:500] + "..."
                        tool_name = getattr(msg, 'name', 'unknown')
                        logger.info(f"[Orchestrator] Tool result ({tool_name}): {content}")
            yield chunk


    async def close(self):
        """
        Close connections and cleanup resources.
        """
        # MultiServerMCPClient will clean up subprocesses automatically
        self._mcp_client = None
        self._agent_graph = None
