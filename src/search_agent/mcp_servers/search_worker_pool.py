"""SearchWorkerPool MCP Server - Manages SearchAgent worker pool."""

from __future__ import annotations

import asyncio
import os
import time
import traceback
from typing import Any, Dict, List

from fastmcp import FastMCP
from langchain_openai import ChatOpenAI
import logging

from ..configuration.pools import get_pool_size
from ..agents.search_agent import SearchAgent
from ..coordination._worker_wrapper import WorkerAgentWrapper

logger = logging.getLogger(__name__)

# Configuration: Read from YAML config
MAX_POOL_SIZE = get_pool_size("search")

# FastMCP server instance
mcp = FastMCP("SearchWorkerPool")

EXECUTE_SUBTASKS_DESCRIPTION = f"""
Execute 1–{MAX_POOL_SIZE} independent web search subtasks in parallel using a pool of Search Agents.

CRITICAL LIMIT:
- This tool accepts AT MOST {MAX_POOL_SIZE} subtasks per call.
- If you have more than {MAX_POOL_SIZE} subtasks, you MUST split them into multiple calls.
- Each call must contain between 1 and {MAX_POOL_SIZE} subtasks (inclusive).

CAPABILITY:
- **Web Search**: Can perform broad searches (Google/Firecrawl) to find relevant URLs.
- **Deep Retrieval**: Can open identifiers/URLs and read specific page content.
- **Extraction**: Can summarize information from search results or page content.
- **Constraints**: Agents are STATELESS and ISOLATED. They cannot see other agents' results.

WHEN TO USE:
- Use this tool when:
  - You have one or more clear, factual, or retrieval-style queries.
  - Multiple queries can be answered independently.
  - You want to batch these lookups for efficiency.

SUBTASK DESIGN (STRICT RULES):
1. **SELF-CONTAINED**:
   - Each subtask string must be fully independent.
   - **NEVER** write "For the same universities..." or "For the list found above...". The worker DOES NOT KNOW what list you are talking about.
   - **ALWAYS** explicitly repeat the full entity names (e.g. "Find the fees for Harvard, MIT, and Oxford...").
2. **NATURAL LANGUAGE**:
   - Write full questions or directives (e.g. "Find the release date of Black Myth Wukong").
   - Do NOT send keyword blobs.
3. **DISTINCT**:
   - Do NOT generate multiple near-identical queries.
4. **ATOMIC SCOPE**:
   - Do NOT ask for "all items in range X to Y" in one subtask.
   - Workers perform better on specific targets rather than broad scraping.
5. **CONSTRAINT VERIFICATION**:
   - If a subtask asks to verify multiple constraints for an entity, check ALL constraints in the query.
   - Example: "For sulfur: verify if commonly used in daily life AND find first purification date"
   - **DO NOT** return partial results (e.g., only answering one of the two questions).
   - If information for a constraint is not found, explicitly state "Not found" for that constraint.

OUTPUT STYLE:
- Each result should be concise, factual, and directly responsive.
- Optionally include 1–3 key source URLs.

Args:
  subtasks: List[str]
    A list of 1 to {MAX_POOL_SIZE} fully self-contained search queries.
    MUST NOT exceed {MAX_POOL_SIZE} items. Split larger lists into multiple calls.
"""

worker_pool: List[WorkerAgentWrapper] = []
pool_lock = asyncio.Lock()
pool_config: Dict[str, Any] = {}
_pool_initialized = False


async def initialize_pool(config: Dict[str, Any] | None = None, model=None):
    """Initialize SearchAgent worker pool (called by backend on startup or auto-initialized)."""
    global pool_config, worker_pool, _pool_initialized

    if _pool_initialized:
        return

    if config is None:
        config = {
            "max_pool_size": MAX_POOL_SIZE,
            "agent_config": {},
        }

    pool_config = config

    max_pool_size = config.get("max_pool_size", MAX_POOL_SIZE)

    if model is None:
        model_kwargs = {
            "model": os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            "api_key": os.getenv("OPENAI_API_KEY"),
            "reasoning_effort": "low",
        }
        base_url = os.getenv("OPENAI_BASE_URL")
        if base_url:
            model_kwargs["base_url"] = base_url
        model = ChatOpenAI(**model_kwargs)

    agents = []
    for i in range(max_pool_size):
        agent = SearchAgent(
            name=f"search_agent_{i}",
            model=model,
            **config.get("agent_config", {}),
        )
        agents.append(agent)

    start_tasks = [agent.start() for agent in agents if hasattr(agent, "start")]
    if start_tasks:
        await asyncio.gather(*start_tasks)

    for i, agent in enumerate(agents):
        wrapper = WorkerAgentWrapper(agent, f"search_agent_{i}")
        worker_pool.append(wrapper)

    _pool_initialized = True
    logger.info(f"[SearchWorkerPool] Initialized with {len(worker_pool)} workers")


@mcp.tool(description=EXECUTE_SUBTASKS_DESCRIPTION.format(max_pool_size=MAX_POOL_SIZE))
async def execute_subtasks(subtasks: List[str]) -> dict:
    """Execute search subtasks in parallel across SearchAgent pool."""
    for i, subtask in enumerate(subtasks):
        logger.info(f"Subtask {i}: {subtask}")

    if not _pool_initialized:
        await initialize_pool()

    if not subtasks or len(subtasks) < 1:
        raise ValueError("Must provide at least 1 subtask")

    max_pool_size = pool_config.get("max_pool_size", MAX_POOL_SIZE)
    if len(subtasks) > max_pool_size:
        raise ValueError(
            f"Too many subtasks ({len(subtasks)}) for pool size ({max_pool_size})"
        )

    async with pool_lock:
        available = [w for w in worker_pool if not w.is_busy][: len(subtasks)]

        if len(available) < len(subtasks):
            raise RuntimeError(
                f"Not enough agents. Requested: {len(subtasks)}, Available: {len(available)}"
            )

        for agent in available:
            agent.is_busy = True

    try:
        async def execute_on_agent(agent: WorkerAgentWrapper, subtask: str, idx: int):
            max_retrys = 5
            start_time = time.perf_counter()

            logger.info(
                f"[SearchWorkerPool] Agent {agent.agent_id} starting subtask [{idx}]: {subtask[:100]}..."
            )

            for attempt in range(max_retrys):
                try:
                    response = await agent.agent.run(subtask)
                    final_text = _extract_output_from_dict(response)
                    elapsed_time = time.perf_counter() - start_time

                    logger.info(
                        f"[SearchWorkerPool] Agent {agent.agent_id} completed subtask [{idx}] "
                        f"in {round(elapsed_time, 2)}s"
                    )

                    return {
                        "subtask_index": idx,
                        "subtask": subtask,
                        "result": final_text,
                        "agent_id": agent.agent_id,
                        "time_taken_seconds": round(elapsed_time, 2),
                    }
                except Exception as exc:
                    elapsed_time = time.perf_counter() - start_time

                    if attempt < max_retrys - 1:
                        logger.info(
                            f"[SearchWorkerPool] Agent {agent.agent_id} attempt {attempt + 1}/{max_retrys} failed "
                            f"for subtask [{idx}] after {round(elapsed_time, 2)}s: {type(exc).__name__}: {str(exc)[:200]}"
                        )
                        await asyncio.sleep(1)
                    else:
                        error_details = traceback.format_exc()
                        error_message = (
                            f"Agent {agent.agent_id} failed after {max_retrys} attempts (took {round(elapsed_time, 2)}s)\n"
                            f"Subtask [{idx}]: {subtask}\n"
                            f"Error type: {type(exc).__name__}\n"
                            f"Error message: {str(exc)}\n"
                            f"Full traceback:\n{error_details}"
                        )
                        logger.info(f"[SearchWorkerPool] FATAL: {error_message}")
                        raise RuntimeError(error_message) from exc

        tasks = [
            execute_on_agent(a, st, i)
            for i, (a, st) in enumerate(zip(available, subtasks))
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = []
        failed = []
        for result in results:
            if isinstance(result, Exception):
                failed.append({"error": str(result)})
            else:
                successful.append(result)

        return {
            "results": successful,
            "failed": failed,
            "subtasks_count": len(subtasks),
            "agents_used": len(available),
            "pool_size": max_pool_size,
        }
    finally:
        async with pool_lock:
            for agent in available:
                agent.is_busy = False


def _extract_output_from_dict(result: Dict[str, Any]) -> str:
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


if __name__ == "__main__":
    mcp.run()
