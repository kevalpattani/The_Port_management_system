# fastapi_server.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import datetime
import json

app = FastAPI(
    title="Port Simulation Data Logger",
    description="Receives and logs event data from the Pygame port simulation.",
    version="1.0.0"
)

# In-memory storage for logs (for demonstration purposes)
# In a real application, you would use a database (e.g., SQLite, PostgreSQL, MongoDB)
log_data = []

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
    The data is expected to be in JSON format.
    """
    try:
        data = await request.json()
        
        # Add a timestamp to the log entry if it's not already there
        if "server_received_timestamp" not in data:
            data["server_received_timestamp"] = datetime.datetime.now().isoformat()
            
        log_data.append(data) # Store the received data
        print(f"\n--- Received Event Data ({data['server_received_timestamp']}) ---")
        print(json.dumps(data, indent=2))
        print("--------------------------------------------------")
        return {"status": "success", "message": "Event received and logged."}
    except json.JSONDecodeError:
        print(f"Error: Received invalid JSON from {request.client.host}")
        return {"status": "error", "message": "Invalid JSON payload."}, 400
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {"status": "error", "message": f"Server error: {e}"}, 500

@app.get("/get_logs")
async def get_logs():
    """
    Retrieves all stored log data.
    """
    print(f"\n--- Logs requested ({datetime.datetime.now().isoformat()}) ---")
    return {"status": "success", "logs": log_data}

@app.get("/")
async def root():
    """
    Root endpoint for checking if the server is running.
    """
    return {"message": "Port Simulation Data Logger is running!"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
