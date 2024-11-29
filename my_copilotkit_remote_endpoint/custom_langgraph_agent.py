# /my_copilotkit_remote_endpoint/custom_langgraph_agent.py

from copilotkit import LangGraphAgent
from typing import Any
from .checkpointer import RedisCheckpointer


class CustomLangGraphAgent(LangGraphAgent):
    def __init__(self, name: str, description: str, graph: Any, checkpointer: RedisCheckpointer, **kwargs):
        super().__init__(name=name, description=description, graph=graph, **kwargs)
        self.checkpointer = checkpointer

    def execute(self, *args, **kwargs):
        # Ensure checkpointer is properly set before execution
        if not hasattr(self, 'checkpointer'):
            raise ValueError("Checkpointer not properly configured")
        return super().execute(*args, **kwargs)
