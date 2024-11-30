# my_copilotkit_remote_endpoint/main.py
from fastapi import FastAPI, Request, HTTPException
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from copilotkit import CopilotKitSDK
from fastapi.responses import JSONResponse
# import asyncio
# import json
import logging
import uvicorn
import os
import datetime
from typing import Optional
# import uuid
import time
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import sentry_sdk
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from my_copilotkit_remote_endpoint.utils.redis_client import redis_client
from my_copilotkit_remote_endpoint.utils.redis_utils import safe_redis_operation
# import redis.asyncio as redis
from my_copilotkit_remote_endpoint.custom_langgraph_agent import CustomLangGraphAgent
from my_copilotkit_remote_endpoint.agent import the_langraph_graph
from dotenv import load_dotenv
from my_copilotkit_remote_endpoint.checkpointer import checkpointer
from langchain.tools import tool
import requests

# Load environment variables from .env file
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

# Initialize FastAPI app with Sentry middleware for error tracking
app = FastAPI(redirect_slashes=True)
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

# Configure logging for the application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Pydantic models for request validation and data handling
class CopilotActionRequest(BaseModel):
    action_name: str
    parameters: Optional[dict] = None


class ApprovalUpdate(BaseModel):
    request_id: str
    approved: bool


@app.get("/sentry-debug")
async def trigger_error():
    """Trigger an error to test Sentry integration."""
    1 / 0


@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
            headers={"Access-Control-Allow-Origin": "*"}
        )


@app.get("/health")
async def health_check():
    """Health check endpoint to verify service status."""
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Credentials": "true",
    }
    redis_status = "up"
    try:
        # Use safe_redis_operation for reliable connection checking
        result = await safe_redis_operation(redis_client.ping())
        logger.info(f"Redis ping result: {result}")
    except Exception as e:
        redis_status = "down"
        logger.error(f"Redis ping failed with error: {str(e)}")

    return JSONResponse(
        content={
            "status": "healthy" if redis_status == "up" else "error",
            "redis": redis_status,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "version": "1.0.0",
        },
        headers=headers,
    )


@app.post("/update_approval_status")
async def update_approval_status(update: ApprovalUpdate):
    """Endpoint to update human approval status."""
    try:
        approval_key = f"approval_request:{update.request_id}"
        request_data = await safe_redis_operation(redis_client.hgetall(approval_key))
        if not request_data:
            raise HTTPException(status_code=404, detail="Approval request not found")

        timestamp = float(request_data.get("timestamp", 0))
        if time.time() - timestamp > 3600:
            await safe_redis_operation(redis_client.delete(approval_key))
            raise HTTPException(status_code=410, detail="Approval request has expired")

        await safe_redis_operation(
            redis_client.hset(approval_key, mapping={"status": "approved" if update.approved else "rejected"})
        )
        return {"status": "success", "request_id": update.request_id}

    except HTTPException as he:
        raise he

    except Exception as e:
        logger.error(f"Error updating approval status: {str(e)}")
        sentry_sdk.capture_exception(e)
        raise HTTPException(status_code=500, detail="Internal server error")


@tool
def get_current_weather(city: str) -> str:
    """Fetches real-time weather for a city."""
    API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
    if not API_KEY:
        logger.error("Missing OpenWeatherMap API key.")
        return "Weather service unavailable."

    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
    try:
        response = requests.get(url)
        response.raise_for_status()
        logger.info(f"Weather API response: {response.json()}")
        # Parse and return weather information
        data = response.json()
        weather_description = data["weather"][0]["description"].capitalize()
        temperature = data["main"]["temp"]
        return f"The current weather in {city} is {weather_description} with a temperature of {temperature}°C."
    except requests.RequestException as e:
        logger.error(f"Weather API request failed: {e}")
        return "Unable to fetch weather data."


# Initialize the agent with the checkpointer
agent = CustomLangGraphAgent(
    name="weather_agent",
    description="An agent that provides weather information",
    tools=[get_current_weather],
    checkpointer=checkpointer
)

# Initialize SDK with the agent
sdk = CopilotKitSDK(agents=[agent])

# Add the CopilotKit endpoint to your FastAPI app for CoAgent integration.
add_fastapi_endpoint(app, sdk, "/copilotkit_remote")


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info(f"Starting application in ENV: {os.getenv('ENV')}")
    try:
        await safe_redis_operation(redis_client.ping())
        logger.info("Connected to Redis successfully.")
    except Exception as e:
        logger.error(f"Failed to connect to Redis on startup: {e}")


# Shutdown Event: Close Redis Connection
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup services on shutdown."""
    logger.info("Shutting down application...")
    await safe_redis_operation(redis_client.close())


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to log and report errors."""
    logger.error(f"Unhandled exception at {request.url.path}: {str(exc)}", exc_info=True)
    sentry_sdk.capture_exception(exc)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error"},
        headers={"Access-Control-Allow-Origin": "*"},
    )


if __name__ == "__main__":
    # Update port to match deployment requirements (e.g., Railway)
    port = int(os.environ.get("PORT", 8080))

    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info", access_log=True)