
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional
from database import initialize_database, create_user, get_user
import json
from gtts import gTTS
from pathlib import Path
import asyncio


app = FastAPI()
initialize_database()

# Folder for dynamically generated emergency audio
AUDIO_DIR = Path(__file__).parent.parent / "frontend" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# gTTS language codes
LANGUAGE_CODES = {
    "Tamil": "ta",
    "English": "en",
    "Hindi": "hi",
    "Telugu": "te",
    "Malayalam": "ml"
}


def generate_emergency_audio(user_profile):
    language = user_profile["language"]
    language_code = LANGUAGE_CODES.get(language)

    if not language_code:
        raise ValueError("Unsupported emergency audio language")

    name = user_profile["name"]

    messages = {
        "Tamil": (
            f"அவசர எச்சரிக்கை. {name} கீழே விழுந்திருக்கலாம். "
            "தயவுசெய்து உடனடியாக உதவி செய்யுங்கள்."
        ),
        "English": (
            f"Emergency alert. {name} may have fallen. "
            "Please check on them immediately."
        ),
        "Hindi": (
            f"आपातकालीन सूचना। {name} गिर गए हो सकते हैं। "
            "कृपया तुरंत उनकी सहायता करें।"
        ),
        "Telugu": (
            f"అత్యవసర హెచ్చరిక. {name} పడిపోయి ఉండవచ్చు. "
            "దయచేసి వెంటనే సహాయం చేయండి."
        ),
        "Malayalam": (
            f"അടിയന്തര അറിയിപ്പ്. {name} വീണിരിക്കാം. "
            "ദയവായി ഉടൻ സഹായിക്കുക."
        )
    }

    message_text = messages[language]

    # Use a unique filename so different users' messages do not overwrite each other.
    output_file = AUDIO_DIR / f"emergency_{user_profile['user_id']}.mp3"

    tts = gTTS(text=message_text, lang=language_code)
    tts.save(str(output_file))

    return output_file


# Fallback demo profile used when the requested user ID is U001
# and U001 has not been registered in the database.
USER_PROFILE = {
    "user_id": "U001",
    "name": "Nanditha",
    "language": "Tamil",
    "location": "VIT Vellore, Katpadi, Tamil Nadu"
}


connected_clients = []


# Fall alert data received from the ESP32 or a test request
class FallAlert(BaseModel):
    user_id: str = "U001"
    gps_valid: bool = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None


# User registration data
class UserRegistration(BaseModel):
    user_id: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=7, max_length=20)
    language: str
    location: str = ""

class AudioRequest(BaseModel):
    user_id: str


# Serve frontend files
app.mount(
    "/static",
    StaticFiles(directory="../frontend"),
    name="static"
)


@app.get("/")
async def home():
    return HTMLResponse("""
    <h1>Fall Detection Emergency System</h1>
    <p>Server is running.</p>
    <a href="/static/register.html">Register User</a><br>
    <a href="/static/caller.html">Caller</a><br>
    <a href="/static/receiver.html">Receiver</a>
    """)


# Register a new user
@app.post("/register")
async def register_user(user: UserRegistration):
    user_id = user.user_id.strip()
    name = user.name.strip()
    phone = user.phone.strip()
    language = user.language.strip()
    location = user.location.strip()

    if not all([user_id, name, phone, language]):
        raise HTTPException(
            status_code=400,
            detail="User ID, name, phone, and language are required."
        )

    allowed_languages = {
        "Tamil",
        "English",
        "Hindi",
        "Telugu",
        "Malayalam"
    }

    if language not in allowed_languages:
        raise HTTPException(
            status_code=400,
            detail="Please select a supported language."
        )

    try:
        create_user(
            user_id,
            name,
            phone,
            language,
            location
        )
    except Exception as error:
        raise HTTPException(
            status_code=409,
            detail="Could not register user. The ID may already exist."
        ) from error

    return {
        "status": "registered",
        "user": get_user(user_id)
    }

@app.post("/generate-audio")
async def generate_audio(request: AudioRequest):
    user_profile = get_user(request.user_id)

    if user_profile is None and request.user_id == "U001":
        user_profile = USER_PROFILE.copy()

    if user_profile is None:
        raise HTTPException(
            status_code=404,
            detail="User is not registered."
        )

    try:
        audio_file = await asyncio.to_thread(
            generate_emergency_audio,
            user_profile
        )

        return {
            "status": "success",
            "user_id": user_profile["user_id"],
            "language": user_profile["language"],
            "audio_url": (
                f"/static/audio/{audio_file.name}"
            )
        }

    except Exception as error:
        print("Audio generation failed:", error)
        raise HTTPException(
            status_code=500,
            detail="Could not generate emergency audio."
        )

# Retrieve a user's profile and process the fall alert
@app.post("/fall")
async def fall_detected(alert: FallAlert):
    print("\n🚨 FALL DETECTED!")

    # Retrieve the correct registered user
    user_profile = get_user(alert.user_id)

    # Keep the existing demo profile as a fallback for U001 only.
    if user_profile is None and alert.user_id == "U001":
        user_profile = USER_PROFILE.copy()

    # Do not accidentally alert the wrong person if an unknown ID is sent.
    if user_profile is None:
        raise HTTPException(
            status_code=404,
            detail=f"User ID '{alert.user_id}' is not registered."
        )

    print("Patient:", user_profile["name"])
    print("User ID:", user_profile["user_id"])
    print(
        "Emergency contact:",
        user_profile.get("phone", "Not registered")
    )
    print("Preferred language:", user_profile["language"])

    # Validate GPS coordinates
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

    # Send the registered user's details to connected browsers
    fall_message = {
        "type": "fall_detected",
        "user_id": user_profile["user_id"],
        "name": user_profile["name"],
        "phone": user_profile.get("phone", ""),
        "language": user_profile["language"],

        # Current GPS location
        "gps_valid": gps_valid,
        "latitude": latitude,
        "longitude": longitude,
        "location": live_location,
        "maps_url": maps_url,

        # Location entered during registration
        "registered_location": user_profile.get("location", "")
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
        except Exception as error:
            print("WebSocket error:", error)
            disconnected_clients.append(client)

    for client in disconnected_clients:
        if client in connected_clients:
            connected_clients.remove(client)

    return {
        "status": "fall_detected",
        "user_id": user_profile["user_id"],
        "name": user_profile["name"],
        "gps_valid": gps_valid,
        "latitude": latitude,
        "longitude": longitude,
        "location": live_location,
        "maps_url": maps_url
    }


# WebSocket: preserve browser communication and WebRTC signaling
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

            # Forward signaling messages to other connected browsers
            for client in connected_clients.copy():
                if client != websocket:
                    try:
                        await client.send_text(message)
                    except Exception as error:
                        print("Forwarding error:", error)

    except Exception:
        if websocket in connected_clients:
            connected_clients.remove(websocket)

        print(
            "Browser disconnected. Total connections:",
            len(connected_clients)
        )
