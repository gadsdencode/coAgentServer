# my_copilotkit_remote_endpoint/agent.py

from fastapi import FastAPI, HTTPException
from langgraph.graph import MessageGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
import logging
import os
import re
import requests
from copilotkit import LangGraphAgent
from dotenv import load_dotenv
from langgraph.prebuilt import ToolNode
from my_copilotkit_remote_endpoint.utils.redis_utils import (
    safe_redis_operation
)
from my_copilotkit_remote_endpoint.utils.redis_client import (
    redis_client, check_connection, close
)
from my_copilotkit_remote_endpoint.checkpointer import RedisCheckpointer

# Configure logging
logger = logging.getLogger(__name__)

checkpointer = RedisCheckpointer()

# Load environment variables
load_dotenv()

# Initialize OpenAI model
model = ChatOpenAI(
    temperature=0,
    streaming=True,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)


def extract_city(user_input: str) -> str:
    """Extract city name from user input using regex patterns."""
    patterns = [
        r'weather (?:in|at|for) ([A-Za-z\s]+)(?:\?|\.|\s|$)',
        r'(?:what\'s|what is|how\'s) (?:the weather|it) (?:like )?'
        r'(?:in|at) ([A-Za-z\s]+)(?:\?|\.|\s|$)',
        r'([A-Za-z\s]+)(?:\s+weather\b)',
    ]

    for pattern in patterns:
        match = re.search(pattern, user_input.lower(), re.IGNORECASE)
        if match:
            city = match.group(1).strip()
            logger.info(f"Extracted city: {city}")
            return city.title()

    logger.info("No city found in input, using default")
    return "London"


@tool
async def get_current_weather(city: str) -> str:
    """Fetches current weather data for the specified city."""
    cache_key = f"weather:{city.lower()}"

    try:
        cached_data = await safe_redis_operation(
            redis_client.get(cache_key)
        )
        if cached_data:
            return cached_data
    except Exception as e:
        logger.warning(f"Redis cache read failed: {e}")

    API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
    if not API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Weather service configuration missing"
        )

    url = (
        "http://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={API_KEY}&units=metric"
    )

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

        try:
            await safe_redis_operation(
                redis_client.setex(cache_key, 300, weather_info)
            )
        except Exception as e:
            logger.warning(f"Redis cache write failed: {e}")

        return weather_info

    except requests.RequestException as e:
        logger.error(f"Weather API request failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Weather service unavailable"
        )


def degrees_to_cardinal(degrees: float) -> str:
    """Converts wind degrees to cardinal direction."""
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "N"]
    ix = int((degrees + 22.5) / 45.0)
    return dirs[ix % 8]


def create_graph():
    """Creates a LangGraph with integrated tools."""
    graph = MessageGraph()

    tool_node = ToolNode(
        tools=[get_current_weather]
    )

    graph.add_node("tools", tool_node)
    graph.add_edge("tools", END)
    graph.set_entry_point("tools")

    return graph.compile()


# Initialize FastAPI app
app = FastAPI()

# Create agent instance with Redis checkpointer
weather_agent = LangGraphAgent(
    name="weather_agent",
    description="An agent that provides weather information",
    graph=create_graph()
)


@app.on_event("startup")
async def startup_event():
    """Initialize Redis connection on startup"""
    await check_connection()


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up Redis connection on shutdown"""
    await close()


@app.get("/health")
async def health_check():
    """Health check endpoint with Redis status"""
    try:
        await safe_redis_operation(redis_client.ping())
        return {"status": "healthy", "redis": "connected"}
    except Exception:
        return {"status": "degraded", "redis": "disconnected"}
