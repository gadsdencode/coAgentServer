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
        # Create the initial graph
        graph = MessageGraph()
        tool_node = ToolNode(
            tools=tools,
            name=f"{name}_tools"
        )
        graph.add_node("tools", tool_node)
        graph.add_edge("tools", END)
        graph.set_entry_point("tools")

        if checkpointer:
            graph.checkpointer = checkpointer

        compiled_graph = graph.compile()

        # Initialize parent class with all required parameters
        super().__init__(
            name=name,
            description=description,
            graph=compiled_graph
        )

        self.tools = tools
        self.checkpointer = checkpointer
        self.graph = compiled_graph

        # Configure the agent
        self.langgraph_config = LangGraphConfig(
            name=name,
            description=description,
            tools=tools
        )

        logger.info(f"Initializing CustomLangGraphAgent: {name}")

    async def setup(self) -> None:
        """Initialize the agent if needed"""
        logger.info(f"Running agent setup for {self.name}...")
        # No need to recreate graph since it's already created in __init__
        pass

    async def _create_graph(self) -> Graph:
        """Create and configure the graph with proper async support"""
        graph = MessageGraph()

        # Create and add tool node
        tool_node = ToolNode(
            tools=self.tools,
            name=f"{self.name}_tools"
        )
        graph.add_node("tools", tool_node)
        graph.add_edge("tools", END)

        # Configure graph settings
        graph.set_entry_point("tools")
        if self.checkpointer:
            graph.checkpointer = self.checkpointer

        return graph.compile()

    async def execute(
        self,
        inputs: Dict[str, Any],
        thread_id: Optional[str] = None,
        node_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute the agent with the given inputs"""
        if not self.graph:
            try:
                await self.setup()
            except Exception as e:
                error_msg = f"Failed to initialize agent graph: {str(e)}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

        try:
            # Set thread_id if provided
            if self.checkpointer and thread_id:
                self.checkpointer.set_thread_id(thread_id)

            # Ensure inputs is a dictionary
            if not isinstance(inputs, dict):
                inputs = {"input": inputs}

            # Execute graph
            result = await self.graph.arun(inputs, **kwargs)
            return result
        except Exception as e:
            error_msg = f"Error executing agent: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    def get_config(self) -> Dict[str, Any]:
        """Return the agent configuration"""
        return self.langgraph_config.dict()

    async def cleanup(self) -> None:
        """Cleanup resources"""
        if self.checkpointer:
            try:
                await self.checkpointer.delete(f"{self.name}_state")
            except Exception as e:
                error_msg = f"Error cleaning up agent: {str(e)}"
                logger.error(error_msg)
