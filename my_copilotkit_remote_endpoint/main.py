# my_copilotkit_remote_endpoint/main.py
from fastapi import FastAPI
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from fastapi.responses import JSONResponse
from copilotkit import CopilotKitSDK
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
import logging
import os
from dotenv import load_dotenv
from datetime import datetime
from my_copilotkit_remote_endpoint.utils.redis_utils import safe_redis_operation
from my_copilotkit_remote_endpoint.utils.redis_client import redis_client
from my_copilotkit_remote_endpoint.checkpointer import RedisCheckpointer
from my_copilotkit_remote_endpoint.custom_langgraph_agent import (
    CustomLangGraphAgent
)
import httpx
import sentry_sdk
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

# Sentry DSN configuration for error tracking and monitoring
SENTRY_DSN = os.getenv(
    "SENTRY_DSN",
    "https://fde9c73970d2156b60353a776ebaa698@o4508369368514560.ingest.us.sentry.io/4508369376706560",
)
sentry_sdk.init(
    dsn=SENTRY_DSN,
    traces_sample_rate=1.0,
    _experiments={
        "continuous_profiling_auto_start": True,
    },
)

# Initialize FastAPI app
app = FastAPI()
app.add_middleware(SentryAsgiMiddleware)

# Configure CORS settings based on environment variables or defaults
allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
if not allowed_origins or allowed_origins == [""]:
    allowed_origins = (
        ["*"]
        if os.getenv("ENV") == "development"
        else [
            "http://localhost:3000",
            "https://ai-customer-support-nine-eta.vercel.app",
            "https://coagentserver-production.up.railway.app",
        ]
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI model
model = ChatOpenAI(
    temperature=0,
    streaming=True,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)


@tool
async def get_current_weather(city: str) -> str:
    """Fetches current weather data for the specified city."""
    API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
    if not API_KEY:
        raise ValueError("Weather service configuration missing")

    cache_key = f"weather:{city.lower()}"

    # Try cache first
    try:
        cached = await safe_redis_operation(redis_client.get(cache_key))
        if cached:
            return cached
    except Exception as e:
        logger.warning(f"Cache read failed: {e}")

    # Fetch from API if not cached
    url = (
        "http://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={API_KEY}&units=metric"
    )

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            weather = data["weather"][0]["description"].capitalize()
            temp = data["main"]["temp"]
            result = f"The weather in {city} is {weather} with {temp}°C"

            # Cache for 5 minutes
            await safe_redis_operation(
                redis_client.setex(cache_key, 300, result)
            )
            return result

        except Exception as e:
            logger.error(f"Weather API error: {e}")
            raise ValueError("Weather service unavailable")


# Initialize checkpointer
checkpointer = RedisCheckpointer()

# Create the agent
agent = CustomLangGraphAgent(
    name="weather_agent",
    description="An agent that provides weather information",
    tools=[get_current_weather],
    checkpointer=checkpointer
)

# Initialize SDK with the agent
sdk = CopilotKitSDK(agents=[agent])

# Add the CopilotKit endpoint
add_fastapi_endpoint(app, sdk, "/copilotkit_remote")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Credentials": "true",
    }
    redis_status = "up"
    try:
        await safe_redis_operation(redis_client.ping())
    except Exception as e:
        redis_status = "down"
        logger.error(f"Redis health check failed: {e}")

    return JSONResponse(
        content={
            "status": "healthy" if redis_status == "up" else "degraded",
            "redis": redis_status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
        headers=headers
    )

if __name__ == "__main__":
    # Update port to match deployment requirements (e.g., Railway)
    port = int(os.environ.get("PORT", 8080))

    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info", access_log=True)
