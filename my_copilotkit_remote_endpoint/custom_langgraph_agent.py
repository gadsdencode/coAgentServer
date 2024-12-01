# my_copilotkit_remote_endpoint/custom_langgraph_agent.py

from copilotkit import LangGraphAgent
from typing import Any
from langgraph.graph import MessageGraph, END
from langgraph.prebuilt import ToolNode
import logging
from langchain.tools import BaseTool

logger = logging.getLogger(__name__)


class CustomLangGraphAgent(LangGraphAgent):
    """
    A custom LangGraph agent that integrates with CopilotKit.
    Provides a simple graph structure for tool execution.
    """

    def __init__(
        self,
        name: str,
        description: str,
        tools: list[BaseTool],
        checkpointer: Any = None
    ):
        # Create graph structure
        graph = MessageGraph()

        # Add tool node
        tool_node = ToolNode(
            tools=tools,
            name=f"{name}_tools"
        )
        graph.add_node("tools", tool_node)
        graph.add_edge("tools", END)
        graph.set_entry_point("tools")

        # Set checkpointer if provided
        if checkpointer:
            # Ensure checkpointer is set on the graph itself
            graph.checkpointer = checkpointer
            logger.info(f"Set checkpointer on graph for agent {name}")

        # Compile graph
        compiled_graph = graph.compile()

        # Initialize with compiled graph
        super().__init__(
            name=name,
            description=description,
            graph=compiled_graph,
            checkpointer=checkpointer  # Explicitly pass checkpointer to parent
        )

        self.tools = tools
        self.checkpointer = checkpointer
        logger.info(f"Initialized agent {name} with checkpointer")
