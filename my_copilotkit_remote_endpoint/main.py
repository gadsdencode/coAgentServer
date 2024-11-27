# main.py

from fastapi import FastAPI, Request, HTTPException
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from copilotkit import CopilotKitSDK, Action as CopilotAction
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
from my_copilotkit_remote_endpoint.utils import redis_client, redis_utils


safe_redis_operation = redis_utils.safe_redis_operation
# For the Sentry DSN, store it in an environment variable
SENTRY_DSN = os.getenv(
    "SENTRY_DSN",
    "https://fde9c73970d2156b60353a776ebaa698@o4508369368514560."
    "ingest.us.sentry.io/4508369376706560"
)

sentry_sdk.init(
    dsn=SENTRY_DSN,
    traces_sample_rate=1.0,
    _experiments={
        "continuous_profiling_auto_start": True,
    },
)
app = FastAPI(redirect_slashes=False)
app.add_middleware(SentryAsgiMiddleware)

# For the CORS middleware
allowed_origins_dev = ["*"]
allowed_origins_prod = [
    "http://localhost:3000",
    "https://ai-customer-support-nine-eta.vercel.app",
    "https://coagentserver-production.up.railway.app",
]

allowed_origins = [
    "http://localhost:3000",
    "https://ai-customer-support-nine-eta.vercel.app",
    "https://coagentserver-production.up.railway.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Model for incoming action request
class CopilotActionRequest(BaseModel):
    action_name: str
    parameters: Optional[dict] = None


@app.get("/sentry-debug")
async def trigger_error():
    1 / 0


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    sentry_sdk.capture_exception(exc)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = request.headers.get("origin", "http://localhost:3000")
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


# Health check endpoint
@app.get("/health")
async def health_check():
    redis_status = "up"
    try:
        await safe_redis_operation(redis_client.ping())
    except Exception:
        redis_status = "down"

    return {
        "status": "healthy",
        "redis": redis_status,
        "timestamp": datetime.datetime.now().isoformat(),
        "version": "1.0.0",
    }


@app.post("/copilotkit_remote/info")
async def copilotkit_remote_info():
    return {
        "name": "basic_agent",
        "description": "A basic agent that can perform tasks",
        "capabilities": ["fetch_data", "process_data"],
    }


@app.post("/human_approval")
async def request_human_approval(request: Request):
    data = await request.json()
    request_id = data.get('request_id', str(uuid.uuid4()))
    approval_key = f"approval_request:{request_id}"

    approval_data = {
        'data': json.dumps(data),
        'timestamp': str(time.time()),
        'status': 'pending'
    }

    await safe_redis_operation(
        redis_client.hset(approval_key, mapping=approval_data)
    )
    await safe_redis_operation(
        redis_client.expire(approval_key, 3600)
    )

    return StreamingResponse(
        human_approval_stream(request_id),
        media_type="text/event-stream"
    )


async def check_human_approval(request_id: str) -> Optional[bool]:
    try:
        request_data = await safe_redis_operation(
            redis_client.hgetall(f"approval_request:{request_id}")
        )

        if not request_data:
            logger.error(f"No approval request found for ID: {request_id}")
            return None

        timestamp = float(request_data.get('timestamp', 0))
        if time.time() - timestamp > 3600:
            await safe_redis_operation(
                redis_client.delete(f"approval_request:{request_id}")
            )
            logger.warning(f"Approval request {request_id} timed out")
            return None

        return request_data.get('status') == 'approved'

    except Exception as e:
        logger.error(f"Error checking approval status: {str(e)}")
        return None


async def human_approval_stream(request_id: str):
    try:
        attempts = 0
        max_attempts = 360  # 1 hour with 10-second intervals

        while attempts < max_attempts:
            approval_status = await check_human_approval(request_id)

            if approval_status is None:
                error_msg = {'error': 'Request expired or invalid'}
                yield f"data: {json.dumps(error_msg)}\n\n"
                break

            if approval_status:
                yield f"data: {json.dumps({'approved': True})}\n\n"
                await safe_redis_operation(
                    redis_client.delete(f"approval_request:{request_id}")
                )
                break

            attempts += 1
            await asyncio.sleep(10)  # Check every 10 seconds

        if attempts >= max_attempts:
            yield f"data: {json.dumps({'error': 'Request timed out'})}\n\n"
            await safe_redis_operation(
                redis_client.delete(f"approval_request:{request_id}")
            )

    except Exception as e:
        logger.error(f"Error in approval stream: {str(e)}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


@app.post("/copilotkit_remote")
async def copilotkit_remote_action(request: Request):
    try:
        data = await request.json()
        logger.info(f"Received action request: {data}")

        action_request = CopilotActionRequest(**data)
        action_name = action_request.action_name
        parameters = action_request.parameters or {}

        action = sdk.get_action(action_name)
        if not action:
            raise HTTPException(
                status_code=404,
                detail=f"Action '{action_name}' not found"
            )

        result = await action.handler(**parameters)

        msg = (
            f"Action '{action_name}' executed successfully "
            f"with result: {result}"
        )
        logger.info(msg)

        return JSONResponse(
            content={"status": "success", "result": result}
        )

    except HTTPException as he:
        error_msg = (
            f"HTTP Error while executing action "
            f"'{data.get('action_name', '')}': {str(he)}"
        )
        logger.error(error_msg)
        raise he
    except ValueError as ve:
        logger.error(f"ValueError in request payload: {str(ve)}")
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Invalid request payload"}
        )
    except Exception as e:
        logger.error(
            "Unexpected error while executing action: {str(e)}",
            exc_info=True
        )
        sentry_sdk.capture_exception(e)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.post("/copilotkit_remote/stream")
async def copilotkit_remote_stream():
    async def event_generator():
        # Simulate intermediate states
        intermediate_states = [
            {
                "agentName": "basic_agent",
                "node": "fetch_data",
                "status": "processing",
                "state": {"input": "Fetching data...", "messages": []},
            },
            {
                "agentName": "basic_agent",
                "node": "process_data",
                "status": "processing",
                "state": {"input": "Processing data...", "messages": []},
            },
            {
                "agentName": "basic_agent",
                "node": "complete",
                "status": "completed",
                "state": {
                    "final_response": {
                        "conditions": "Sunny",
                        "temperature": 25,
                        "wind_direction": "NW",
                        "wind_speed": 15,
                    },
                    "input": "Fetch the name for user ID 123.",
                    "messages": [],
                },
            },
        ]

        for state in intermediate_states:
            yield f"data: {json.dumps(state)}\n\n"
            await asyncio.sleep(1)  # Simulate delay between states

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Define your backend action
async def fetch_name_for_user_id(userId: str):
    # Replace with your database logic
    return {"name": "User_" + userId}

# This is a dummy action for demonstration purposes
action = CopilotAction(
    name="fetchNameForUserId",
    description="Fetches user name from the database for a given ID.",
    parameters=[
        {
            "name": "userId",
            "type": "string",
            "description": "The ID of the user to fetch data for.",
            "required": True,
        }
    ],
    handler=fetch_name_for_user_id,
)

# Initialize the CopilotKit SDK
sdk = CopilotKitSDK(actions=[action])
add_fastapi_endpoint(app, sdk, "/api/copilotkit")


class ApprovalUpdate(BaseModel):
    request_id: str
    approved: bool


@app.post("/update_approval_status")
async def update_approval_status(update: ApprovalUpdate):
    try:
        approval_key = f"approval_request:{update.request_id}"
        request_data = await safe_redis_operation(
            redis_client.hgetall(approval_key)
        )
        if not request_data:
            raise HTTPException(
                status_code=404,
                detail="Approval request not found"
            )

        timestamp = float(request_data.get('timestamp', 0))
        if time.time() - timestamp > 3600:
            await safe_redis_operation(
                redis_client.delete(approval_key)
            )
            raise HTTPException(
                status_code=410,
                detail="Approval request has expired"
            )

        await safe_redis_operation(
            redis_client.hset(
                approval_key,
                'status',
                'approved' if update.approved else 'rejected'
            )
        )

        return {"status": "success", "request_id": update.request_id}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating approval status: {str(e)}")
        sentry_sdk.capture_exception(e)
        raise HTTPException(status_code=500, detail="Internal server error")


# Application startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting up application...")
    # Any additional startup tasks can go here
    pass


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup services on shutdown."""
    logger.info("Shutting down application...")
    try:
        await redis_client.close()
        logger.info("Redis connection closed successfully")
    except Exception as e:
        logger.error(f"Error closing Redis connection: {str(e)}")

if __name__ == "__main__":
    # Update port to match Railway's requirements
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # Required for Railway
        port=port,
        log_level="info",
        access_log=True,
    )
