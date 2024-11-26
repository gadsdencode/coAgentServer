# main.py

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from copilotkit import CopilotKitSDK, Action as CopilotAction
from fastapi.responses import StreamingResponse
import asyncio
import json
import logging
import uvicorn
import os
import datetime
import redis
from typing import Optional
import uuid
import time
from pydantic import BaseModel


app = FastAPI(
    redirect_slashes=False  # Add this line
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://ai-customer-support-nine-eta.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging properly
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Redis connection
redis = redis.from_url("redis://localhost", decode_responses=True)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger = logging.getLogger("uvicorn.access")
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    return response


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "version": "1.0.0"
    }


@app.post("/copilotkit_remote/info")
async def copilotkit_remote_info():
    return {
        "name": "basic_agent",
        "description": "A basic agent that can perform tasks",
        "capabilities": ["fetch_data", "process_data"]
    }


@app.post("/human_approval")
async def request_human_approval(request: Request):
    data = await request.json()
    # Generate unique request ID if not provided
    request_id = data.get('request_id', str(uuid.uuid4()))

    # Store request data with timestamp
    await redis.hset(
        f"approval_request:{request_id}",
        mapping={
            'data': json.dumps(data),
            'timestamp': str(time.time()),
            'status': 'pending'
        }
    )
    # Set expiration for 1 hour
    await redis.expire(f"approval_request:{request_id}", 3600)

    return StreamingResponse(human_approval_stream(request_id))


async def check_human_approval(request_id: str) -> Optional[bool]:
    try:
        # Get current status from Redis
        request_data = await redis.hgetall(f"approval_request:{request_id}")

        if not request_data:
            logger.error(f"No approval request found for ID: {request_id}")
            return None

        # Check if request has expired (1 hour timeout)
        timestamp = float(request_data.get('timestamp', 0))
        if time.time() - timestamp > 3600:
            await redis.delete(f"approval_request:{request_id}")
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
                # Request expired or error occurred
                yield f"data: {json.dumps({'error': 'Request expired or invalid'})}\n\n"
                break

            if approval_status:
                yield f"data: {json.dumps({'approved': True})}\n\n"
                # Cleanup after approval
                await redis.delete(f"approval_request:{request_id}")
                break

            attempts += 1
            await asyncio.sleep(10)  # Check every 10 seconds

        if attempts >= max_attempts:
            yield f"data: {json.dumps({'error': 'Request timed out'})}\n\n"
            await redis.delete(f"approval_request:{request_id}")

    except Exception as e:
        logger.error(f"Error in approval stream: {str(e)}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


@app.post("/copilotkit_remote")  # Changed from /api/copilotkit_remote
async def copilotkit_remote_stream():
    async def event_generator():
        # Simulate intermediate states
        intermediate_states = [
            {
                "agentName": "basic_agent",
                "node": "fetch_data",
                "status": "processing",
                "state": {"input": "Fetching data...", "messages": []}
            },
            {
                "agentName": "basic_agent",
                "node": "process_data",
                "status": "processing",
                "state": {"input": "Processing data...", "messages": []}
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
                        "wind_speed": 15
                    },
                    "input": "Fetch the name for user ID 123.",
                    "messages": []
                }
            },
        ]

        for state in intermediate_states:
            yield f"data:{json.dumps(state)}\n\n"
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
    handler=fetch_name_for_user_id
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
        # Check if request exists
        request_data = await redis.hgetall(f"approval_request:{update.request_id}")
        if not request_data:
            raise HTTPException(status_code=404, detail="Approval request not found")

        # Check if request has expired
        timestamp = float(request_data.get('timestamp', 0))
        if time.time() - timestamp > 3600:
            await redis.delete(f"approval_request:{update.request_id}")
            raise HTTPException(status_code=410, detail="Approval request has expired")

        # Update approval status
        await redis.hset(
            f"approval_request:{update.request_id}",
            'status',
            'approved' if update.approved else 'rejected'
        )

        return {"status": "success", "request_id": update.request_id}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating approval status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    # Update port to match Railway's requirements
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # Required for Railway
        port=port,
        log_level="info",
        access_log=True
    )
