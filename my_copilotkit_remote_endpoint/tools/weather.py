# my_copilotkit_remote_endpoint/tools/weather.py

from langchain.tools import tool
import os
import requests
import logging

logger = logging.getLogger(__name__)


@tool
def get_current_weather(location: str) -> str:
    """Get the current weather for a location.

    Args:
        location: The city or location to get weather for

    Returns:
        A string describing the current weather
    """
    api_key = os.getenv("OPENWEATHERMAP_API_KEY")
    if not api_key:
        return "Weather service unavailable - missing API key"
    try:
        url = "http://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": location,
            "appid": api_key,
            "units": "metric"
        }

        response = requests.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        temp = data["main"]["temp"]
        desc = data["weather"][0]["description"]

        return f"The current weather in {location} is {desc} with a temperature of {temp}°C"

    except Exception as e:
        logger.error(f"Weather API error: {e}")
        return f"Unable to get weather for {location}"
