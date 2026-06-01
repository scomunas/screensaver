import os
import logging
import requests
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from config import PORT, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SYNOLOGY_URL
from database import init_db, get_random_photo_record, get_photo_record_by_id

# --- LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("nas_backend")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FastAPI backend starting. Initializing database schema...")
    try:
        init_db()
    except Exception as e:
        logger.critical(f"Database setup failed on backend start: {e}")
    yield
    logger.info("FastAPI backend shutting down.")

app = FastAPI(title="Photo Screensaver Backend API", lifespan=lifespan)

# Enable CORS for frontend accessibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "online"}

@app.get("/api/photos/random")
async def get_random_photo():
    """
    Retrieves metadata for a random photo from the database.
    """
    row = get_random_photo_record()
    if not row:
        raise HTTPException(
            status_code=404, 
            detail="No photos found in catalog database. Please run a library scan from your Synology service."
        )
    
    return {
        "id": row["id"],
        "file_name": row["file_name"],
        "directory": row["directory"],
        "file_size": row["file_size"],
        "width": row["width"],
        "height": row["height"],
        "date_taken": row["date_taken"].isoformat() if row["date_taken"] else None,
        "camera_make": row["camera_make"],
        "camera_model": row["camera_model"],
        "lens_model": row["lens_model"],
        "exposure_time": row["exposure_time"],
        "f_number": row["f_number"],
        "iso": row["iso"],
        "focal_length": row["focal_length"],
        "media_type": row["media_type"],
        "duration": row["duration"]
    }

@app.post("/api/photos/{photo_id}/send")
async def send_photo_to_telegram(photo_id: int):
    # 1. Check if Telegram configuration is present
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Telegram bot configurations are missing.")
        raise HTTPException(
            status_code=500,
            detail="Telegram bot configurations are not set on backend. Please configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in the .env file."
        )

    # 2. Get photo record from DB
    row = get_photo_record_by_id(photo_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Media record with ID {photo_id} not found.")

    file_size = row["file_size"]
    media_type = row["media_type"]
    file_name = row["file_name"]
    file_path = row["file_path"]

    # 3. Size check: <= 50MB (50 * 1024 * 1024 bytes)
    max_upload_size = 50 * 1024 * 1024
    import html
    try:
        if file_size <= max_upload_size:
            # Send as direct file attachment
            # Fetch bytes from synology service
            synology_file_url = f"{SYNOLOGY_URL}/api/photos/file/{photo_id}"
            logger.info(f"Requesting file bytes from Synology: {synology_file_url}")
            
            # Streaming from Synology API (timeout 30s)
            file_response = requests.get(synology_file_url, timeout=30)
            if not file_response.ok:
                raise Exception(f"Failed to fetch file from Synology. Status: {file_response.status_code}")
            
            file_bytes = file_response.content
            
            # Post to Telegram Bot API
            # For photos: sendPhoto, for videos: sendVideo
            if media_type == 'video':
                tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
                files = {"video": (file_name, file_bytes)}
            else:
                tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
                # HEIC is converted to JPEG on the fly by Synology agent
                upload_name = file_name.rsplit('.', 1)[0] + '.jpg' if file_name.lower().endswith('.heic') else file_name
                files = {"photo": (upload_name, file_bytes)}
                
            escaped_path = html.escape(file_path)
            caption_text = f"<b>Compartido desde Screensaver</b>\n{escaped_path}"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID, 
                "caption": caption_text,
                "parse_mode": "HTML"
            }
            
            logger.info(f"Uploading file to Telegram: {tg_url}")
            tg_response = requests.post(tg_url, data=payload, files=files, timeout=60)
        else:
            # Send as direct link
            tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            external_link = f"http://{os.getenv('SYNOLOGY_IP', 'localhost')}:{os.getenv('SYNOLOGY_PORT', '9092')}/api/photos/file/{photo_id}"
            
            escaped_path = html.escape(file_path)
            message_text = f"<b>Compartido desde Screensaver</b>\n{escaped_path}\n(Tamaño: {file_size / (1024*1024):.1f}MB - Supera los 50MB)\nEnlace: {external_link}"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID, 
                "text": message_text,
                "parse_mode": "HTML"
            }
            
            logger.info(f"Sending video link to Telegram: {tg_url}")
            tg_response = requests.post(tg_url, json=payload, timeout=10)

        if not tg_response.ok:
            logger.error(f"Telegram API responded with error: {tg_response.status_code} - {tg_response.text}")
            raise Exception(f"Telegram API Error: {tg_response.text}")

        return {"status": "success", "message": "Media sent successfully to Telegram."}

    except Exception as e:
        logger.error(f"Error sending media to Telegram: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send media to Telegram: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    logger.info("--- STARTING backend UVICORN SERVICE ---")
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
