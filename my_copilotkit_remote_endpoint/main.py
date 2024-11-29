# my_copilotkit_remote_endpoint/main.py
from fastapi import FastAPI, Request, HTTPException
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from copilotkit import CopilotKitSDK, LangGraphAgent
from fastapi.responses import StreamingResponse, JSONResponse
import asyncio
import json
import logging
import uvicorn
import os
import datetime
from typing import Optional
import uuid
import time
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import sentry_sdk
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from my_copilotkit_remote_endpoint.utils.redis_client import redis_client
from my_copilotkit_remote_endpoint.utils.redis_utils import safe_redis_operation
import redis.asyncio as redis
from my_copilotkit_remote_endpoint.agent import the_langraph_graph  # Import the compiled LangGraph graph from agent.py
from dotenv import load_dotenv

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
async def add_cors_headers(request: Request, call_next):
    """Middleware to add CORS headers."""
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = request.headers.get(
        "origin", "http://localhost:3000"
    )
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


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


# Define your LangGraph agent within CopilotKitSDK (Updated to use the compiled graph directly)
sdk = CopilotKitSDK(
    agents=[
        LangGraphAgent(
            name="basic_agent",
            description="An agent that answers questions about the weather.",
            graph=the_langraph_graph,
        )
    ]
)

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
    # Start of Selection
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