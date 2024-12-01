# my_copilotkit_remote_endpoint/agent.py

from fastapi import FastAPI, Request, HTTPException
from langgraph.graph import MessageGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from typing import Any, Dict, List, Optional
import logging
import os
import re
import requests
import uuid
from copilotkit import LangGraphAgent
from dotenv import load_dotenv
from langgraph.prebuilt import ToolNode
from my_copilotkit_remote_endpoint.checkpointer import RedisCheckpointer
from my_copilotkit_remote_endpoint.utils.redis_utils import safe_redis_operation
from my_copilotkit_remote_endpoint.utils.redis_client import redis_client, check_connection, close
# from my_copilotkit_remote_endpoint.tools.weather import get_current_weather
# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize OpenAI model
model = ChatOpenAI(
    temperature=0,
    streaming=True,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)


def extract_city(user_input: str) -> str:
    """
    Extract city name from user input using regex patterns.
    Falls back to default if no city is found.

    Args:
        user_input: The user's input text

    Returns:
        str: Extracted city name or default city
    """
    # Common patterns for city extraction
    patterns = [
        r'weather (?:in|at|for) ([A-Za-z\s]+)(?:\?|\.|\s|$)',  # "weather in City"
        r'(?:what\'s|what is|how\'s) (?:the weather|it) (?:like )?(?:in|at) ([A-Za-z\s]+)(?:\?|\.|\s|$)',  # "what's the weather in City"
        r'([A-Za-z\s]+)(?:\s+weather\b)',  # "City weather"
    ]

    for pattern in patterns:
        match = re.search(pattern, user_input.lower(), re.IGNORECASE)
        if match:
            city = match.group(1).strip()
            logger.info(f"Extracted city: {city}")
            return city.title()  # Capitalize first letter of each word

    # Default city if no match found
    logger.info("No city found in input, using default")
    return "London"


@tool
async def get_current_weather(city: str) -> str:
    """Fetches current weather data for the specified city with Redis caching."""
    cache_key = f"weather:{city.lower()}"

    # Try to get cached weather data
    try:
        cached_data = await safe_redis_operation(
            redis_client.get(cache_key)
        )
        if cached_data:
            return cached_data
    except Exception as e:
        logger.warning(f"Redis cache read failed: {e}")

    # If no cache, fetch from API
    API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
    if not API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Weather service configuration missing"
        )

    url = (f"http://api.openweathermap.org/data/2.5/weather"
           f"?q={city}&appid={API_KEY}&units=metric")
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        weather_description = data["weather"][0]["description"].capitalize()
        temperature = data["main"]["temp"]
        wind_speed = data["wind"]["speed"]
        wind_deg = data["wind"].get("deg", 0)
        wind_direction = degrees_to_cardinal(wind_deg)

        weather_info = (
            f"The current weather in {city} is {weather_description} with a "
            f"temperature of {temperature}°C, and wind speed of {wind_speed} "
            f"km/h from {wind_direction}."
        )

        # Cache the result for 5 minutes
        try:
            await safe_redis_operation(
                redis_client.setex(cache_key, 300, weather_info)
            )
        except Exception as e:
            logger.warning(f"Redis cache write failed: {e}")

        return weather_info
    except requests.RequestException as e:
        logger.error(f"Weather API request failed: {e}")
        raise HTTPException(status_code=503, detail="Weather service unavailable")


def degrees_to_cardinal(degrees: float) -> str:
    """Converts wind degrees to cardinal direction."""
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "N"]
    ix = int((degrees + 22.5) / 45.0)
    return dirs[ix % 8]


# Bind tools to model
model_with_tools = model.bind_tools([get_current_weather])


async def call_oracle(state: Dict[str, Any]) -> Dict[str, Any]:
    """Oracle node handler with state management."""
    messages = state.get("messages", [])
    session_id = state.get("session_id")

    if not messages:
        logger.error("No messages in state")
        return state

    latest_message = messages[-1]
    if isinstance(latest_message, HumanMessage):
        user_input = latest_message.content
        city = extract_city(user_input)

        # Track user query in Redis
        if session_id:
            try:
                await safe_redis_operation(
                    redis_client.lpush(f"session:{session_id}:queries", user_input)
                )
            except Exception as e:
                logger.warning(f"Failed to track query: {e}")

        modified_message = HumanMessage(content=f"What's the weather in {city}?")
        response = await model_with_tools.ainvoke([modified_message])

        return {
            "messages": messages + [response],
            "session_id": session_id
        }

    return state


def create_graph():
    """Creates a LangGraph with integrated tools and Redis state management."""
    graph = MessageGraph()

    tools = [get_current_weather]
    tool_node = ToolNode(
        tools=tools,
        return_messages=True
    )

    graph.add_node("oracle", call_oracle)
    graph.add_node("tools", tool_node)

    graph.add_edge("oracle", "tools")
    graph.add_edge("tools", END)

    graph.set_entry_point("oracle")

    return graph.compile()


class WeatherAgent(LangGraphAgent):
    def __init__(self):
        super().__init__(
            name="weather_oracle",
            description="An agent that provides weather information with state management",
            graph=create_graph(),
            checkpointer=RedisCheckpointer(ttl=3600),
            tools=[get_current_weather]
        )

    async def process_message(self, message: str) -> Dict[str, Any]:
        """Process messages with session management and error handling."""
        session_id = str(uuid.uuid4())

        try:
            result = await self.graph.arun({
                "messages": [HumanMessage(content=message)],
                "session_id": session_id
            })

            # Extract the final message
            if isinstance(result, dict) and "messages" in result:
                final_message = result["messages"][-1]
                if isinstance(final_message, AIMessage):
                    return {
                        "response": final_message.content,
                        "session_id": session_id
                    }

            return {
                "response": str(result),
                "session_id": session_id
            }

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {"error": str(e), "session_id": session_id}


# Initialize FastAPI app
app = FastAPI()

# Create agent instance
weather_agent = WeatherAgent()


@app.on_event("startup")
async def startup_event():
    """Initialize Redis connection on startup"""
    await check_connection()


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up Redis connection on shutdown"""
    await close()


@app.post("/process")
async def process(request: Request):
    """Process weather requests with Redis integration"""
    try:
        data = await request.json()
        inputs = data.get("inputs")
        if not inputs:
            raise HTTPException(status_code=400, detail="Missing 'inputs' in request")

        result = await weather_agent.process_message(inputs)
        return result
    except Exception as e:
        logger.error(f"Request processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint with Redis status"""
    try:
        await safe_redis_operation(redis_client.ping())
        return {"status": "healthy", "redis": "connected"}
    except Exception:
        return {"status": "degraded", "redis": "disconnected"}
