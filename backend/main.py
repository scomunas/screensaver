import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from config import PORT
from database import init_db, get_random_photo_record

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
        "focal_length": row["focal_length"]
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("--- STARTING backend UVICORN SERVICE ---")
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
