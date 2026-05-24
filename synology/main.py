import os
import uuid
import logging
from io import BytesIO
from datetime import datetime
from contextlib import asynccontextmanager
from PIL import Image

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

# Try to register HEIC support
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_SUPPORTED = True
except ImportError:
    HEIF_SUPPORTED = False

# --- LOGGING CONFIGURATION ---
LOG_DIR = "log"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)

log_filename = os.path.join(LOG_DIR, f"{datetime.now().strftime('%Y-%m-%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_filename)
    ]
)
logger = logging.getLogger("nas_manager")
logger.info(f"HEIC parsing support: {'ENABLED' if HEIF_SUPPORTED else 'DISABLED'}")

# Import local modules directly
from config import API_KEY, PORT
from database import init_db, get_photo_by_id
from scanner import queue_orchestrator

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Synology Scan Service starting. Checking DB configuration...")
    try:
        init_db()
    except Exception as e:
        logger.critical(f"Could not connect to PostgreSQL database: {e}")
    yield
    logger.info("Synology Scan Service shutting down.")

app = FastAPI(title="Synology NAS Photo Screensaver Scan Agent", lifespan=lifespan)

# Enable CORS for frontend accessibility (on Proxmox)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key Security for scanner
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=True)

async def verify_api_key(header_value: str = Depends(api_key_header)):
    if header_value != API_KEY:
        logger.warning(f"SECURITY ALERT: Invalid API Key attempt")
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return header_value

# --- PYDANTIC MODELS ---
class ScanRequest(BaseModel):
    path: str

# --- API ENDPOINTS ---

@app.get("/health")
async def health_check():
    return {"status": "online", "heic_supported": HEIF_SUPPORTED}

@app.post("/api/scan", status_code=202)
async def start_scan(payload: ScanRequest, background_tasks: BackgroundTasks, api_key: str = Depends(verify_api_key)):
    """
    Asynchronously crawls a folder on the NAS, parsing EXIF and indexing into the Postgres DB.
    """
    logger.info(f"Scan request received for path: {payload.path}")
    target_path = os.path.abspath(payload.path)
    if not os.path.exists(target_path):
        logger.error(f"Scan failed: Target path does not exist: {target_path}")
        raise HTTPException(status_code=400, detail="Target path does not exist")
    
    new_id = str(uuid.uuid4())
    conn = None
    try:
        from database import get_db_connection
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM nas_scans WHERE status = 'running'")
            status = 'queued' if cur.fetchone() else 'pending'
            cur.execute("INSERT INTO nas_scans (id, path, status) VALUES (%s, %s, %s)", (new_id, target_path, status))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to queue scan: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize scan in database")
    finally:
        if conn:
            conn.close()
            
    logger.info(f"Scan {new_id} added to queue as '{status}'")
    background_tasks.add_task(queue_orchestrator)
    return {"scan_id": new_id, "status": status}

@app.get("/api/photos/file/{photo_id}")
async def get_photo_file(photo_id: int):
    """
    Streams image file locally from the NAS. Converts HEIC to JPEG dynamically if requested.
    """
    row = get_photo_by_id(photo_id)
    if not row:
        raise HTTPException(status_code=404, detail="Photo not found in database")
        
    file_path = row["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Physical file not found on NAS at {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".heic":
        if not HEIF_SUPPORTED:
            raise HTTPException(status_code=400, detail="HEIC files are not supported (pillow-heif is not installed)")
        try:
            logger.debug(f"Converting HEIC file to JPEG on the fly: {file_path}")
            with Image.open(file_path) as img:
                out = BytesIO()
                img.save(out, format="JPEG", quality=85)
                out.seek(0)
                return StreamingResponse(out, media_type="image/jpeg")
        except Exception as e:
            logger.error(f"Error converting HEIC image {file_path}: {e}")
            raise HTTPException(status_code=500, detail="Failed to convert HEIC image")
            
    media_type = "image/png" if ext == ".png" else "image/jpeg"
    return FileResponse(file_path, media_type=media_type)

if __name__ == "__main__":
    import uvicorn
    logger.info("--- STARTING SYNOLOGY UVICORN AGENT ---")
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
