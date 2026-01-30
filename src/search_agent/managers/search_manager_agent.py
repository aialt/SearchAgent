"""SearchManagerAgent - Pure LangChain manager for coordinating SearchAgent worker pool."""

from __future__ import annotations

import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Any, AsyncGenerator, Mapping, Sequence

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_mcp_adapters.client import MultiServerMCPClient

from ..configuration.pools import get_pool_size

logger = logging.getLogger(__name__)


class SearchManagerAgent:
    """
    Pure LangChain manager agent that coordinates SearchAgent workers via search worker pool.

    This agent decomposes complex research queries into focused subtasks and executes
    them in parallel across a pool of SearchAgent workers via the FastMCP worker pool.
    """

    DEFAULT_COMMAND = sys.executable
    DEFAULT_ARGS: Sequence[str] = ("-m", "search_agent.mcp_servers.search_worker_pool")

    def __init__(
        self,
        *,
        name: str = "search_manager",
        model: BaseChatModel,
        description: str | None = None,
        command: str | None = None,
        args: Sequence[str] | None = None,
        env: Mapping[str, str] | None = None,
        system_message: str | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self._pool_size = get_pool_size("search")
        self._description = description or (
            "Coordinates SearchAgent workers via the search worker MCP pool, "
            "decomposing research tasks into parallel subtasks."
        )

        self._command = command or self.DEFAULT_COMMAND
        self._args = list(args) if args is not None else list(self.DEFAULT_ARGS)
        self._env = dict(os.environ if env is None else env)

        self._system_message = system_message or self._build_default_system_message()
        self._mcp_client: MultiServerMCPClient | None = None
        self._agent_graph: Any = None

    def _build_default_system_message(self) -> str:
        return """You are the Search Manager. You coordinate a pool of workers to retrieve information.

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

    async def start(self) -> None:
        """Initialize MCP connection to worker pool and build the agent graph."""
        env = dict(self._env)
        if "PYTHONPATH" not in env:
            src_path = Path(__file__).parent.parent.parent.absolute()
            env["PYTHONPATH"] = str(src_path)

        mcp_servers = {
            "search_worker_pool": {
                "command": self._command,
                "args": self._args,
                "env": env,
                "transport": "stdio",
            }
        }

        self._mcp_client = MultiServerMCPClient(mcp_servers)
        tools = await self._mcp_client.get_tools()

        self._agent_graph = create_agent(
            model=self.model,
            tools=tools,
            system_prompt=self._system_message,
        )

    async def run(self, query: str | list[dict]) -> dict[str, Any]:
        """Execute the manager agent and return the complete result."""
        if not self._agent_graph:
            raise RuntimeError("Agent not started. Call start() first.")

        if isinstance(query, str):
            query_preview = query[:200] + "..." if len(query) > 200 else query
            logger.info(f"[SearchManager] Query: {query_preview}")
            messages = [{"role": "user", "content": query}]
        else:
            messages = query
            for msg in messages:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    query_preview = content[:200] + "..." if len(content) > 200 else content
                    logger.info(f"[SearchManager] Query: {query_preview}")
                    break

        try:
            result = await self._agent_graph.ainvoke({"messages": messages})
            return {
                "output": _extract_output(result),
                "raw": result,
            }
        except Exception as exc:
            logger.error(f"[SearchManager] Error: {exc}\n{traceback.format_exc()}")
            raise

    async def stream(self, query: str | list[dict]) -> AsyncGenerator[dict[str, Any], None]:
        """Execute the manager agent and stream updates as they occur."""
        if not self._agent_graph:
            raise RuntimeError("Agent not started. Call start() first.")

        if isinstance(query, str):
            query_preview = query[:200] + "..." if len(query) > 200 else query
            logger.info(f"[SearchManager] Query: {query_preview}")
            messages = [{"role": "user", "content": query}]
        else:
            messages = query
            for msg in messages:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    query_preview = content[:200] + "..." if len(content) > 200 else content
                    logger.info(f"[SearchManager] Query: {query_preview}")
                    break

        async for chunk in self._agent_graph.astream(
            {"messages": messages},
            stream_mode="updates",
            config={"recursion_limit": 50},
        ):
            yield chunk

    async def close(self) -> None:
        """Close MCP connections and cleanup resources."""
        self._mcp_client = None
        self._agent_graph = None


def _extract_output(result: dict[str, Any]) -> str:
    if "output" in result:
        return str(result["output"])
    messages = result.get("messages", [])
    if messages:
        last = messages[-1]
        if hasattr(last, "content"):
            return last.content
        if isinstance(last, dict) and "content" in last:
            return last["content"]
    return str(result)
