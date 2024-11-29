# /my_copilotkit_remote_endpoint/custom_langgraph_agent.py

from copilotkit import LangGraphAgent
from typing import Any
# from .checkpointer import RedisCheckpointer
from langgraph.graph import Graph, MessageGraph
from my_copilotkit_remote_endpoint.agent import the_langraph_graph
from my_copilotkit_remote_endpoint.agent import get_current_weather
from my_copilotkit_remote_endpoint.checkpointer import checkpointer


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


graph_with_tools = the_langraph_graph.with_tools([get_current_weather])

message_graph_with_tools = MessageGraph.with_tools([get_current_weather])

# Then, create the agent without the tools argument
agent = CustomLangGraphAgent(
    name="basic_agent",
    description="A basic agent for handling requests",
    graph=graph_with_tools,
    checkpointer=checkpointer,
)
