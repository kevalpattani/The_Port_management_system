# fastapi_server.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import datetime
import json
import collections # For deque

app = FastAPI(
    title="Port Data Logger & Messenger",
    description="Receives and logs event data, and sets up the C client-to-Pygame messaging.",
    version="1.0.0"
)

#memory storage for the logs from pygame - p
log_data = []

# In-memory storage for messages from C client to Pygame
# Using a deque to keep a limited number of recent messages
pygame_messages = collections.deque(maxlen=10) # Store last 10 messages

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/log_event")
async def log_event(request: Request):
    """
    Receives event data from the Pygame simulation and logs it.
    Expected data structure for a ship event:
    {
        "ship_id": int,
        "ship_name": str,
        "current_zone": str,
        "current_speed_kmh": float,
        "timestamp": str,  # Original timestamp from client
        "event_type": str, # e.g., "zone_change", "emergency", "ship_deleted", "docked", "undocked"
        "message": str     # Optional: For emergency type
    }
    """
    try:
        data = await request.json()

        # Add server-received timestamp
        data["server_received_timestamp"] = datetime.datetime.now().isoformat()

        # Append to log_data
        log_data.append(data)
        print(f"\n--- LOGGED EVENT ({data['server_received_timestamp']}) ---")
        print(json.dumps(data, indent=2))
        print("---------------------------------------------")

        return {"status": "success", "message": "Event received and logged."}
    except json.JSONDecodeError:
        print(f"Error: Received invalid JSON from {request.client.host}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")
    except Exception as e:
        print(f"An unexpected error occurred in /log_event: {e}")
        raise HTTPException(status_code=500, detail=f"Server error: {e}")

@app.get("/get_logs")
async def get_logs():
    """
    Retrieves all stored log data for polling by C client.
    """
    # print(f"\n--- Logs requested by C client ({datetime.datetime.now().isoformat()}) ---")
    return {"status": "success", "logs": log_data}

@app.post("/send_message_to_pygame")
async def send_message_to_pygame(request: Request):
    """
    Receives a message from the C client intended for Pygame.
    Expected data: {"message": "Your emergency text"}
    """
    try:
        data = await request.json()
        message_text = data.get("message")
        if not message_text:
            raise HTTPException(status_code=400, detail="Message content is required.")

        message_entry = {
            "source": "C_Client",
            "timestamp": datetime.datetime.now().isoformat(),
            "content": message_text
        }
        pygame_messages.append(message_entry) # Add to the deque
        print(f"\n--- MESSAGE FROM C CLIENT FOR PYGAME ({message_entry['timestamp']}) ---")
        print(json.dumps(message_entry, indent=2))
        print("---------------------------------------------------------------")
        return {"status": "success", "message": "Message sent for Pygame."}
    except json.JSONDecodeError:
        print(f"Error: Received invalid JSON from {request.client.host}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")
    except Exception as e:
        print(f"An unexpected error occurred in /send_message_to_pygame: {e}")
        raise HTTPException(status_code=500, detail=f"Server error: {e}")

# This endpoint is for Pygame to poll for messages from the C client
@app.get("/get_messages_for_pygame")
async def get_messages_for_pygame():
    """
    Pygame polls this endpoint to retrieve messages sent from the C client.
    After retrieval, messages are cleared from the server-side queue.
    """
    messages_to_send = list(pygame_messages) # Get all current messages
    pygame_messages.clear() # Clear them after retrieval (one-time fetch)
    if messages_to_send:
        print(f"\n--- Messages delivered to Pygame ({datetime.datetime.now().isoformat()}) ---")
        print(json.dumps(messages_to_send, indent=2))
        print("-------------------------------------------------")
    return {"status": "success", "messages": messages_to_send}


@app.get("/")
async def root():
    """
    Root endpoint for checking if the server is running.
    """
    return {"message": "Port Simulation Data Logger & Messenger is running!"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
