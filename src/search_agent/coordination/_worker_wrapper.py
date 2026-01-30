"""Worker wrapper for SearchExecutor instances"""

from typing import Any
from datetime import datetime


class WorkerAgentWrapper:
    """Wrapper for SearchExecutor instances with state tracking"""

    def __init__(self, agent: Any, agent_id: str):
        """
        Initialize wrapper.

        Args:
            agent: SearchExecutor instance
            agent_id: Unique identifier for this executor
        """
        self.agent = agent  # SearchExecutor
        self.agent_id = agent_id
        self.created_at = datetime.now()
        self.last_used = datetime.now()
        self.is_busy = False
        self.task_count = 0

    async def execute(self, subtask: str) -> Any:
        """
        Execute a search subtask using the wrapped SearchExecutor.

        Args:
            subtask: Search query string

        Returns:
            Result from SearchExecutor.run()
        """
        self.is_busy = True
        self.task_count += 1
        self.last_used = datetime.now()

        try:
            # SearchExecutor.run() returns a dict with 'messages' key
            result = await self.agent.run(subtask)
            return result
        finally:
            self.is_busy = False

    async def cleanup(self) -> None:
        """Cleanup executor resources"""
        if hasattr(self.agent, 'close'):
            await self.agent.close()
