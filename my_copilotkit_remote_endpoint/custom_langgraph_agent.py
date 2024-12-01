# my_copilotkit_remote_endpoint/custom_langgraph_agent.py

from copilotkit import LangGraphAgent
from typing import Any, Dict
from langgraph.graph import MessageGraph, END
from langgraph.prebuilt import ToolNode
import logging
from langchain.tools import BaseTool
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
import uuid

logger = logging.getLogger(__name__)


class CustomLangGraphAgent(LangGraphAgent):
    """
    A custom LangGraph agent implementation that handles tool execution and state management.
    """

    def __init__(
        self,
        name: str,
        description: str,
        tools: list[BaseTool],
        checkpointer: Any = None
    ):
        # Create the graph with proper message handling
        graph = MessageGraph()

        # Configure tool node with provided tools
        tool_node = ToolNode(
            tools=tools,
            name=f"{name}_tools"
        )

        # Add nodes and configure graph flow
        graph.add_node("tools", tool_node)
        graph.add_edge("tools", END)
        graph.set_entry_point("tools")

        if checkpointer:
            graph.checkpointer = checkpointer

        # Initialize base class with compiled graph
        super().__init__(
            name=name,
            description=description,
            graph=graph.compile()
        )

        self.tools = tools
        self.checkpointer = checkpointer

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent with provided inputs.

        Args:
            inputs: Dictionary containing the input parameters

        Returns:
            Dict containing the execution results
        """
        try:
            # Format messages based on input type
            if isinstance(inputs, str):
                messages = [HumanMessage(content=inputs)]
            elif isinstance(inputs, dict):
                # Handle both "inputs" and "messages" keys
                if "inputs" in inputs:
                    messages = [HumanMessage(content=inputs["inputs"])]
                else:
                    messages = inputs.get("messages", [
                        HumanMessage(content=str(inputs))
                    ])
            else:
                messages = [HumanMessage(content=str(inputs))]

            # Execute graph with state management
            result = await self.graph.arun({
                "messages": messages
            })

            # Extract and format response
            if isinstance(result, dict) and "messages" in result:
                final_message = result["messages"][-1]
                if isinstance(final_message, AIMessage):
                    return {
                        "output": final_message.content
                    }

            return {
                "output": str(result)
            }

        except Exception as e:
            logger.error(f"Error executing agent: {e}")
            return {"error": str(e)}

    async def setup(self) -> None:
        """Initialize any required resources"""
        logger.info(f"Setting up agent: {self.name}")
        if self.checkpointer:
            await self.checkpointer.setup()

    async def cleanup(self) -> None:
        """Cleanup any resources"""
        if self.checkpointer:
            try:
                await self.checkpointer.delete(f"{self.name}_state")
            except Exception as e:
                logger.error(f"Error cleaning up agent: {e}")
