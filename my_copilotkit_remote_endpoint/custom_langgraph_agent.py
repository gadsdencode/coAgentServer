# my_copilotkit_remote_endpoint/custom_langgraph_agent.py

from copilotkit import LangGraphAgent
from typing import Any, List, Dict, Optional
from langgraph.graph import MessageGraph, END
from langgraph.prebuilt import ToolNode
import logging
from langchain.tools import BaseTool
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
import uuid
from typing import Tuple
logger = logging.getLogger(__name__)


class LangGraphConfig(BaseModel):
    """Configuration for LangGraph"""
    name: str
    description: str
    tools: List[BaseTool]
    checkpoint_interval: Optional[int] = 5
    max_steps: Optional[int] = 10


class CustomLangGraphAgent(LangGraphAgent):
    """
    A custom LangGraph agent implementation that handles tool execution and state management.
    """

    def __init__(
        self,
        name: str,
        description: str,
        tools: List[BaseTool],
        checkpointer: Optional[Any] = None
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

    async def execute(self, inputs: Dict[str, Any]) -> Tuple[Dict[str, Any], str, str]:
        """
        Execute the agent with provided inputs and state management
        """
        try:
            # Generate session ID for state tracking
            session_id = str(uuid.uuid4())

            # Format messages
            if isinstance(inputs, str):
                messages = [HumanMessage(content=inputs)]
            elif isinstance(inputs, dict):
                messages = inputs.get("messages", [HumanMessage(content=str(inputs))])
            else:
                messages = [HumanMessage(content=str(inputs))]

            # Execute graph with state management
            result = await self.graph.arun({
                "messages": messages,
                "session_id": session_id
            })

            # Extract and format response
            if isinstance(result, dict) and "messages" in result:
                final_message = result["messages"][-1]
                if isinstance(final_message, AIMessage):
                    return {
                        "output": final_message.content,
                        "session_id": session_id
                    }

            return {
                "output": str(result),
                "session_id": session_id
            }

        except Exception as e:
            logger.error(f"Error executing agent: {e}")
            return {"error": str(e)}

    async def setup(self) -> None:
        """Initialize any required resources"""
        logger.info(f"Setting up agent: {self.name}")
        if self.checkpointer:
            await self.checkpointer.setup()
