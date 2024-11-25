# main.py

from fastapi import FastAPI
from copilotkit.integrations.fastapi import add_fastapi_endpoint
from copilotkit import CopilotKitSDK, Action as CopilotAction
from fastapi.responses import StreamingResponse
import asyncio
import json

app = FastAPI()


@app.post("/copilotkit_remote_stream")
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

# Add the CopilotKit endpoint to your FastAPI app with a different
#  path to avoid conflicts
add_fastapi_endpoint(app, sdk, "/copilotkit_remote_action")
