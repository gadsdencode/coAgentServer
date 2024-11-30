# my_copilotkit_remote_endpoint/custom_langgraph_agent.py

from copilotkit import LangGraphAgent
from typing import Any, List
from langgraph.graph import Graph, MessageGraph, END
from langgraph.prebuilt import ToolNode
import logging
from langchain.tools import BaseTool

logger = logging.getLogger(__name__)


class CustomLangGraphAgent(LangGraphAgent):
    def __init__(
        self,
        name: str,
        description: str,
        tools: List[BaseTool],
        checkpointer: Any,
    ):
        self.name = name
        self.description = description
        self.tools = tools
        self.checkpointer = checkpointer
        self.graph = None
        logger.info(f"Initializing CustomLangGraphAgent: {name}")

    async def setup(self):
        """Async setup method to initialize the graph"""
        try:
            self.graph = await self._create_graph()
            logger.info(f"Graph created successfully for agent: {self.name}")
        except Exception as e:
            logger.error(f"Failed to create graph: {str(e)}")
            raise

    async def _create_graph(self) -> Graph:
        """Create and configure the graph with proper async support"""
        graph = MessageGraph()

        # Configure tool node
        tool_node = ToolNode(tools=self.tools)
        graph.add_node("tools", tool_node)

        # Add edges
        graph.add_edge("tools", END)

        # Set entry point and checkpointer
        graph.set_entry_point("tools")
        graph.checkpointer = self.checkpointer

        return graph.compile()

    async def process(self, messages: List[Any]) -> Any:
        """Process messages through the graph"""
        if not self.graph:
            await self.setup()

        try:
            result = await self.graph.arun(messages)
            return result
        except Exception as e:
            logger.error(f"Error processing messages: {str(e)}")
            raise
