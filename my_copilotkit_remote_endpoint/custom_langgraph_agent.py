# /my_copilotkit_remote_endpoint/custom_langgraph_agent.py

from copilotkit import LangGraphAgent
from typing import Any
# from .checkpointer import RedisCheckpointer
from langgraph.graph import Graph


class CustomLangGraphAgent(LangGraphAgent):
    def __init__(
        self,
        name: str,
        description: str,
        graph: Graph,
        checkpointer: Any,
    ):
        super().__init__(name=name, description=description, graph=graph)
        # Explicitly set the checkpointer on the graph
        self.graph.checkpointer = checkpointer

    def execute(self, *args, **kwargs):
        # Ensure checkpointer is properly set before execution
        if not hasattr(self, 'checkpointer'):
            raise ValueError("Checkpointer not properly configured")
        return super().execute(*args, **kwargs)
