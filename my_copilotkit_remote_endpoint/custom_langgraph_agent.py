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
        model: Any,
        checkpointer: Any = None
    ):
        # Create the message graph
        graph = MessageGraph()

        # Add a tool node with the provided tools
        tool_node = ToolNode(
            tools=tools,
            name=f"{name}_tools"
        )
        graph.add_node("tools", tool_node)
        graph.add_edge("tools", END)  # Define the flow of the graph
        graph.set_entry_point("tools")

        # Compile the graph into an executable form
        compiled_graph = graph.compile()

        # **Set the language model on the compiled graph**
        compiled_graph.provider = model
        logger.info(f"Set language model on compiled graph for agent {name}")

        # **Assign the checkpointer to the compiled graph if provided**
        if checkpointer:
            compiled_graph.checkpointer = checkpointer
            logger.info(f"Set checkpointer on compiled graph for agent {name}")

        # Initialize the LangGraphAgent with the compiled graph
        super().__init__(
            name=name,
            description=description,
            graph=compiled_graph
        )

        # Store the tools for future reference
        self.tools = tools
        logger.info(f"Initialized agent {name} with {len(tools)} tools.")
