# my_copilotkit_remote_endpoint/custom_langgraph_agent.py

from copilotkit import LangGraphAgent
from typing import Any
from langgraph.graph import MessageGraph, END
from langgraph.prebuilt import ToolNode
import logging
from langchain.tools import BaseTool
from my_copilotkit_remote_endpoint.checkpointer import RedisCheckpointer

logger = logging.getLogger(__name__)

checkpointer = RedisCheckpointer()


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
        model: Any,
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

        # Compile graph
        compiled_graph = graph.compile()

        # Set checkpointer on compiled graph
        if checkpointer:
            compiled_graph.checkpointer = checkpointer
            logger.info(f"Set checkpointer on compiled graph for agent {name}")

        # Initialize parent with compiled graph
        super().__init__(
            name=name,
            description=description,
            graph=compiled_graph,
            model=model
        )

        # Store tools for reference
        self.tools = tools
        logger.info(f"Initialized agent {name} with {len(tools)} tools and model {model}.")
