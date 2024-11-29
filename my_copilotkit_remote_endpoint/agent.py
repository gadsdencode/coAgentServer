# my_copilotkit_remote_endpoint/agent.py
from langgraph.graph import MessageGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, FunctionMessage
from langchain_core.tools import tool
from typing import Any, Dict, List
import logging
import os
import json
import re
import requests
from copilotkit import LangGraphAgent
from dotenv import load_dotenv

# Configure logging for the agent
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Load environment variables from .env file
load_dotenv()

# Initialize the ChatOpenAI model with the API key
model = ChatOpenAI(
    temperature=0,
    streaming=True,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)


# Define tools
@tool
def multiply(first_number: int, second_number: int) -> int:
    """Multiplies two numbers together."""
    return first_number * second_number


@tool
def get_current_weather(city: str) -> str:
    """Fetches current weather data for the specified city."""
    API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
    if not API_KEY:
        logger.error("OpenWeatherMap API key not set.")
        return "Weather service is currently unavailable."

    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        weather_description = data["weather"][0]["description"].capitalize()
        temperature = data["main"]["temp"]
        wind_speed = data["wind"]["speed"]
        wind_deg = data["wind"].get("deg", 0)
        wind_direction = degrees_to_cardinal(wind_deg)
        return (
            f"The current weather in {city} is {weather_description} with a temperature of {temperature}°C, "
            f"and wind speed of {wind_speed} km/h from {wind_direction}."
        )
    except requests.RequestException as e:
        logger.error(f"Failed to fetch weather data: {e}")
        return "Unable to retrieve weather data at the moment."


def degrees_to_cardinal(degrees: float) -> str:
    """
    Converts wind degrees to cardinal direction.
    """
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "N"]
    ix = int((degrees + 22.5) / 45.0)
    return dirs[ix % 8]


# Initialize the ChatOpenAI model
model = ChatOpenAI(temperature=0, streaming=True)

# Bind tools to the model
model_with_tools = model.bind_tools([multiply, get_current_weather])


def extract_city(user_input: str) -> str:
    """
    Extracts the city name from the user's input.
    Uses regex for simple extraction. For more robust extraction, integrate NLP libraries.
    """
    match = re.search(r'weather in ([A-Za-z\s]+)', user_input, re.IGNORECASE)
    if match:
        city = match.group(1).strip()
        logger.info(f"Extracted city: {city}")
        return city
    else:
        logger.info("No city mentioned. Using default city.")
        return "New York"  # Default city if none found


def call_oracle(state: List[Any]) -> List[Any]:
    """
    Oracle node handler.
    Invokes the chat model with the current messages.
    Appends the AI response to the messages.
    """
    if not state:
        logger.error("State has no messages to process.")
        return state

    latest_message = state[-1]
    if isinstance(latest_message, HumanMessage):
        user_input = latest_message.content
        city = extract_city(user_input)
        # Modify the message content if needed
        modified_message = HumanMessage(content=f"What's the weather in {city}?")
        logger.info(f"Invoking model with user input: {modified_message.content}")
        response = model_with_tools.invoke([modified_message])
        logger.info(f"Model response: {response.content}")
        return state + [response]
    elif isinstance(latest_message, FunctionMessage):
        # Execute the tool function
        tool_name = latest_message.additional_kwargs.get("function_call", {}).get("name", "")
        arguments = latest_message.additional_kwargs.get("function_call", {}).get("arguments", "{}")
        try:
            args = json.loads(arguments)
            if tool_name == "multiply":
                result = multiply(**args)
                tool_message = FunctionMessage(content=str(result), additional_kwargs={"tool_call_id": latest_message.id})
                logger.info(f"Tool '{tool_name}' executed with result: {result}")
                return state + [tool_message]
            else:
                logger.warning(f"Unknown tool '{tool_name}' requested.")
                return state
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode arguments: {arguments}. Error: {e}")
            return state
    else:
        logger.warning(f"Unhandled message type: {type(latest_message)}")
        return state


# Define LangGraph nodes and edges using MessageGraph
graph = MessageGraph()

# Add nodes and their handlers
graph.add_node("oracle", call_oracle)
graph.add_node("weather_tool", get_current_weather)

# Add edges between nodes
graph.add_edge("oracle", "weather_tool")  # Oracle queries weather_tool for weather info
graph.add_edge("weather_tool", END)      # Ends after retrieving weather info

# **Set Entry Point Properly**
graph.set_entry_point("oracle")

# Compile graph into a runnable object (required by LangGraph)
compiled_graph = graph.compile()

# Alias compiled graph for consistent import in main.py
the_langraph_graph = compiled_graph

# Wrap LangGraph in a CoAgent for CopilotKit integration
the_langraph_agent = LangGraphAgent(
    name="weather_oracle",
    description="An agent that answers questions about weather using tools.",
    graph=compiled_graph,
)
