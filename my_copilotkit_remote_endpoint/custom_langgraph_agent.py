# my_copilotkit_remote_endpoint/custom_langgraph_agent.py

from copilotkit import LangGraphAgent
from typing import Any, List, Dict, Optional
from langgraph.graph import MessageGraph, END
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

    async def execute(
        self,
        inputs: Dict[str, Any],
        thread_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute the agent with the given inputs.

        Args:
            inputs: Dictionary containing the input parameters
            thread_id: Optional thread identifier for conversation context
            **kwargs: Additional keyword arguments passed by CopilotKit

        Returns:
            Dict containing the execution results
        """
        try:
            # Extract the actual input from the inputs dictionary
            input_str = inputs.get("inputs", "")
            if not input_str:
                raise ValueError("No input provided")

            # Set thread_id in checkpointer if provided
            if thread_id and self.checkpointer:
                self.checkpointer.set_thread_id(thread_id)

            # Convert to the format expected by the graph
            input_dict = {"input": input_str}

            # Execute the graph with the inputs
            result = await self.graph.arun(input_dict)

            # Format the result
            if isinstance(result, dict):
                return result
            return {"output": str(result)}

        except Exception as e:
            error_msg = f"Error executing agent: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    async def process_message(self, message: str) -> Dict[str, Any]:
        """Process a single message through the agent.

        This is a convenience method for handling simple string inputs.
        """
        return await self.execute({"inputs": message})

    async def setup(self) -> None:
        """Initialize the agent if needed"""
        logger.info(f"Running agent setup for {self.name}...")
        pass  # Graph is already created in __init__

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
