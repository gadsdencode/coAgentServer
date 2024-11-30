# custom_langgraph_agent.py

from copilotkit import LangGraphAgent
from typing import Any, List
from langgraph.graph import Graph, MessageGraph, END
from langgraph.prebuilt import ToolNode
import logging

logger = logging.getLogger(__name__)


class CustomLangGraphAgent(LangGraphAgent):
    def __init__(
        self,
        name: str,
        description: str,
        tools: List[Any],
        checkpointer: Any = None,
    ):
        self.tools = tools
        self.checkpointer = checkpointer
        # Create the graph with tools and pass the checkpointer
        graph = self.create_graph_with_tools()
        # Initialize the base agent with the created graph
        super().__init__(name=name, description=description, graph=graph)
        logger.info("Agent initialized.")

    def create_graph_with_tools(self) -> Graph:
        """Create a new graph with tools properly integrated."""
        graph = MessageGraph()

        # Add tool node with the tools
        tool_node = ToolNode(tools=self.tools)
        graph.add_node("tool_executor", tool_node)

        # Add edges
        graph.add_edge("tool_executor", END)

        # Set entry point
        graph.set_entry_point("tool_executor")

        logger.info("Graph with tools has been created.")
        # Compile the graph with the checkpointer
        compiled_graph = graph.compile(checkpointer=self.checkpointer)
        logger.info("Graph has been compiled.")
        return compiled_graph
