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
        checkpointer: Any,
    ):
        self.tools = tools
        self.checkpointer = checkpointer
        logger.info(f"Checkpointer in __init__: {self.checkpointer}")
        # Create the graph with tools
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
        # Compile the graph without passing the checkpointer
        compiled_graph = graph.compile()
        # Set the checkpointer directly on the compiled graph
        compiled_graph.checkpointer = self.checkpointer
        logger.info(f"Graph has been compiled and checkpointer set: {compiled_graph.checkpointer}")
        return compiled_graph

    async def execute(self, inputs: Any, **kwargs):
        thread_id = kwargs.get('thread_id', 'default_thread')
        # Ensure the checkpointer is set on the graph
        if self.graph.checkpointer is None:
            self.graph.checkpointer = self.checkpointer
            logger.info("Checkpointer set on the graph in execute method.")
        logger.info(f"Checkpointer in execute method: {self.graph.checkpointer}")
        config = {"configurable": {"thread_id": thread_id}}
        result = await self.graph.invoke(inputs, config=config)
        return result
