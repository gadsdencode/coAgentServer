# my_copilotkit_remote_endpoint/custom_langgraph_agent.py

from copilotkit import LangGraphAgent
from typing import Any, List, Dict, Optional
from langgraph.graph import Graph, MessageGraph, END
from langgraph.prebuilt import ToolNode
import logging
from langchain.tools import BaseTool
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LangGraphConfig(BaseModel):
    """Configuration for LangGraph"""
    name: str
    description: str
    tools: List[BaseTool]
    checkpoint_interval: Optional[int] = 5
    max_steps: Optional[int] = 10


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

        # Add the required langgraph_config attribute
        self.langgraph_config = LangGraphConfig(
            name=name,
            description=description,
            tools=tools
        )

        logger.info(f"Initializing CustomLangGraphAgent: {name}")

    async def setup(self) -> None:
        """Initialize the agent and create the graph"""
        try:
            self.graph = await self._create_graph()
            logger.info(f"Graph created successfully for agent: {self.name}")
        except Exception as e:
            logger.error(f"Failed to create graph: {str(e)}")
            raise

    async def _create_graph(self) -> Graph:
        """Create and configure the graph with proper async support"""
        graph = MessageGraph()

        # Create nodes
        tool_node = ToolNode(
            tools=self.tools,
            name=f"{self.name}_tools"
        )

        # Add nodes
        graph.add_node("tools", tool_node)

        # Add edges
        graph.add_edge("tools", END)

        # Configure graph
        graph.set_entry_point("tools")
        if self.checkpointer:
            graph.checkpointer = self.checkpointer

        compiled = graph.compile()
        return compiled

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent with the given inputs"""
        if not self.graph:
            await self.setup()

        try:
            result = await self.graph.arun(inputs)
            return {"result": result}
        except Exception as e:
            logger.error(f"Error executing agent: {str(e)}")
            raise

    def get_config(self) -> Dict[str, Any]:
        """Return the agent configuration"""
        return self.langgraph_config.dict()

    async def cleanup(self) -> None:
        """Cleanup resources"""
        if self.checkpointer:
            try:
                await self.checkpointer.delete(f"{self.name}_state")
            except Exception as e:
                logger.error(f"Error cleaning up agent: {str(e)}")
