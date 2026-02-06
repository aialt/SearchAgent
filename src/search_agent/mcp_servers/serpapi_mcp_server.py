"""SerpAPI MCP Server - FastMCP server for SerpAPI search."""

import os
import sys
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

import importlib.util

tools_path = Path(__file__).resolve().parent.parent / "tools" / "serpapi_search.py"
spec = importlib.util.spec_from_file_location("serpapi_search", tools_path)
serpapi_search = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serpapi_search)
get_serpapi_search_results = serpapi_search.get_serpapi_search_results

mcp = FastMCP("SerpAPI")


async def _search_internal(
    query: str,
    num_results: int = 20,
    location: Optional[str] = None,
    start: Optional[int] = None,
) -> str:
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        return "Error: SERPAPI_API_KEY environment variable not set"

    if start is None:
        start = int(os.environ.get("SERPAPI_START_OFFSET", "0"))

    results = await get_serpapi_search_results(
        query=query,
        api_key=api_key,
        num_results=num_results,
        location=location,
        start=start,
    )

    return results.search_results


@mcp.tool()
async def search(
    query: str,
    num_results: int = 10,
    location: Optional[str] = None,
    start: Optional[int] = None,
) -> str:
    """Search the web using SerpAPI."""

    return await _search_internal(
        query=query,
        num_results=num_results,
        location=location,
        start=start,
    )


@mcp.tool()
async def search_google(
    query: str,
    num_results: int = 10,
    start: Optional[int] = None,
) -> str:
    """Search Google using SerpAPI."""

    return await _search_internal(
        query=query,
        num_results=num_results,
        start=start,
    )


@mcp.tool()
async def search_with_location(
    query: str,
    location: str,
    num_results: int = 10,
    start: Optional[int] = None,
) -> str:
    """Search with a specific location using SerpAPI."""

    return await _search_internal(
        query=query,
        num_results=num_results,
        location=location,
        start=start,
    )


if __name__ == "__main__":
    if str(Path(__file__).resolve().parent.parent.parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    mcp.run()
