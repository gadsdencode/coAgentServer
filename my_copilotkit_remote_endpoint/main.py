# main.py

from fastapi import FastAPI, Request
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
