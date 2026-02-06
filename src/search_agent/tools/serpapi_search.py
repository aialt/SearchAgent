"""SerpAPI search integration for web search results."""

import os
import asyncio
import aiohttp
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SerpAPISearchResults:
    """Results from a SerpAPI search query."""

    search_results: str  # Formatted search results text
    links: list[dict[str, str]]  # List of organic search result links
    organic_results: list[dict]  # Raw organic results from SerpAPI
    knowledge_graph: Optional[dict] = None  # Knowledge graph if available
    answer_box: Optional[dict] = None  # Answer box if available


async def get_serpapi_search_results(
    query: str,
    api_key: Optional[str] = None,
    engine: str = "google",
    num_results: int = 10,
    location: Optional[str] = None,
    start: int = 0,
) -> SerpAPISearchResults:
    """Get search results from SerpAPI."""

    api_key = api_key or os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        logger.error("SERPAPI_API_KEY not found in environment variables")
        return SerpAPISearchResults("", [], [], None, None)

    params = {
        "q": query,
        "api_key": api_key,
        "engine": engine,
        "num": num_results,
    }

    if location:
        params["location"] = location

    if start > 0:
        params["start"] = start

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://serpapi.com/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(
                        f"SerpAPI request failed with status {response.status}: {error_text}"
                    )
                    return SerpAPISearchResults("", [], [], None, None)

                data = await response.json()

        organic_results = data.get("organic_results", [])
        knowledge_graph = data.get("knowledge_graph")
        answer_box = data.get("answer_box")

        search_results_text = f"Search Results for: {query}\n\n"

        if answer_box:
            search_results_text += "## Answer Box\n"
            if "answer" in answer_box:
                search_results_text += f"{answer_box['answer']}\n\n"
            if "snippet" in answer_box:
                search_results_text += f"{answer_box['snippet']}\n\n"

        if knowledge_graph:
            search_results_text += "## Knowledge Graph\n"
            if "title" in knowledge_graph:
                search_results_text += f"**{knowledge_graph['title']}**\n"
            if "description" in knowledge_graph:
                search_results_text += f"{knowledge_graph['description']}\n"
            if "type" in knowledge_graph:
                search_results_text += f"Type: {knowledge_graph['type']}\n"
            search_results_text += "\n"

        search_results_text += "## Organic Results\n\n"
        links: list[dict[str, str]] = []

        for idx, result in enumerate(organic_results, 1):
            title = result.get("title", "No title")
            link = result.get("link", "")
            snippet = result.get("snippet", "")

            search_results_text += f"{idx}. **{title}**\n"
            search_results_text += f"   URL: {link}\n"
            if snippet:
                search_results_text += f"   {snippet}\n"
            search_results_text += "\n"

            links.append(
                {
                    "display_text": title,
                    "url": link,
                    "snippet": snippet,
                }
            )

        return SerpAPISearchResults(
            search_results=search_results_text,
            links=links,
            organic_results=organic_results,
            knowledge_graph=knowledge_graph,
            answer_box=answer_box,
        )

    except asyncio.TimeoutError:
        logger.error("SerpAPI request timed out")
        return SerpAPISearchResults("", [], [], None, None)
    except Exception as exc:
        logger.error(f"Error getting SerpAPI search results: {exc}")
        return SerpAPISearchResults("", [], [], None, None)


async def get_serpapi_with_page_contents(
    query: str,
    api_key: Optional[str] = None,
    max_pages: int = 3,
    engine: str = "google",
) -> SerpAPISearchResults:
    """Get SerpAPI search results with page content extraction."""

    results = await get_serpapi_search_results(
        query=query,
        api_key=api_key,
        engine=engine,
        num_results=max(10, max_pages),
    )

    return results
