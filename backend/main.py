
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import json

app = FastAPI()

# Demo user profile
USER_PROFILE = {
    "user_id": "U001",
    "name": "Nanditha",
    "language": "Tamil",
    "location": "VIT Vellore, Katpadi, Tamil Nadu"
}

connected_clients = []


# GPS data received from ESP32
class FallAlert(BaseModel):
    gps_valid: bool = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None


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
async def fall_detected(alert: FallAlert):

    print("🚨 FALL DETECTED!")

    print("Patient:", USER_PROFILE["name"])
    print("User ID:", USER_PROFILE["user_id"])
    print("Language:", USER_PROFILE["language"])

    # Validate the GPS coordinates
    gps_valid = (
        alert.gps_valid
        and alert.latitude is not None
        and alert.longitude is not None
        and -90 <= alert.latitude <= 90
        and -180 <= alert.longitude <= 180
    )

    if gps_valid:
        latitude = alert.latitude
        longitude = alert.longitude

        live_location = f"{latitude:.6f}, {longitude:.6f}"
        maps_url = (
            f"https://www.google.com/maps?q={latitude},{longitude}"
        )

        print("GPS latitude:", latitude)
        print("GPS longitude:", longitude)
        print("Google Maps:", maps_url)

    else:
        latitude = None
        longitude = None
        live_location = "GPS location unavailable"
        maps_url = None

        print("GPS location unavailable or invalid.")

    # Build alert for connected browsers
    fall_message = {
        "type": "fall_detected",
        "user_id": USER_PROFILE["user_id"],
        "name": USER_PROFILE["name"],
        "language": USER_PROFILE["language"],

        # Live GPS location
        "gps_valid": gps_valid,
        "latitude": latitude,
        "longitude": longitude,
        "location": live_location,
        "maps_url": maps_url,

        # Registered profile location, not live GPS
        "registered_location": USER_PROFILE["location"]
    }

    message = json.dumps(fall_message)

    print(
        "Sending fall alert to",
        len(connected_clients),
        "connected browser(s)"
    )

    disconnected_clients = []

    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception as e:
            print("WebSocket error:", e)
            disconnected_clients.append(client)

    for client in disconnected_clients:
        if client in connected_clients:
            connected_clients.remove(client)

    return {
        "status": "fall_detected",
        "user_id": USER_PROFILE["user_id"],
        "gps_valid": gps_valid,
        "latitude": latitude,
        "longitude": longitude,
        "location": live_location,
        "maps_url": maps_url
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

            # Preserve existing WebRTC signaling between browsers
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
