from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Demo user profile
USER_PROFILE = {
    "user_id": "U001",
    "name": "Nanditha",
    "language": "Tamil",
    "location": "VIT Vellore, Katpadi, Tamil Nadu"
}

connected_clients = []


app.mount("/static", StaticFiles(directory="../frontend"), name="static")


@app.get("/")
async def home():

    return HTMLResponse("""
    <h1>Fall Detection Emergency System</h1>

    <p>Server is running.</p>

    <a href="/static/caller.html">Caller</a><br>
    <a href="/static/receiver.html">Receiver</a>
    """)


@app.post("/fall")
async def fall_detected():

    print("🚨 FALL DETECTED!")

    print("Patient:", USER_PROFILE["name"])
    print("User ID:", USER_PROFILE["user_id"])
    print("Location:", USER_PROFILE["location"])
    print("Language:", USER_PROFILE["language"])

    fall_message = {
        "type": "fall_detected",
        "user_id": USER_PROFILE["user_id"],
        "name": USER_PROFILE["name"],
        "location": USER_PROFILE["location"],
        "language": USER_PROFILE["language"]
    }

    import json

    message = json.dumps(fall_message)

    print(
        "Sending fall alert to",
        len(connected_clients),
        "connected browser(s)"
    )

    for client in connected_clients:

        try:
            await client.send_text(message)

        except Exception as e:
            print("WebSocket error:", e)

    return {
        "status": "fall_detected",
        "user_id": USER_PROFILE["user_id"]
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    await websocket.accept()

    connected_clients.append(websocket)

    print(
        "Browser connected. Total connections:",
        len(connected_clients)
    )

    try:

        while True:

            message = await websocket.receive_text()

            print("WebSocket message:", message)

            for client in connected_clients:

                if client != websocket:

                    try:

                        await client.send_text(message)

                    except Exception as e:

                        print("Forwarding error:", e)

    except Exception:

        if websocket in connected_clients:

            connected_clients.remove(websocket)

        print(
            "Browser disconnected. Total connections:",
            len(connected_clients)
        )
