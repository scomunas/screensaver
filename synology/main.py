import os
import re
import uuid
import time
import logging
import asyncio
from io import BytesIO
from datetime import datetime
from contextlib import asynccontextmanager
from PIL import Image
import exifread
import psycopg2
from psycopg2.extras import execute_values, DictCursor

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
logger = logging.getLogger("synology_agent")
logger.info(f"HEIC parsing support: {'ENABLED' if HEIF_SUPPORTED else 'DISABLED'}")

from dotenv import load_dotenv

# Load env variables from .env
load_dotenv()

# --- ENVIRONMENT CONFIGURATION ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "screensaver")
DB_USER = os.getenv("DB_USER", "screensaver_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "screensaver_pass")

DB_CONFIG = {
    "host": DB_HOST,
    "database": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD
}

API_KEY = os.getenv("API_KEY", "my_secure_screensaver_key")
PORT = int(os.getenv("SYNOLOGY_PORT", 9090))
BUFFER_SIZE = int(os.getenv("BUFFER_SIZE", 1000))

def clean_env_list(env_key, default):
    raw = os.getenv(env_key, default)
    return [item.strip() for item in raw.split(',') if item.strip()]

PHOTO_EXTENSIONS = tuple(e.lower() if e.startswith('.') else f".{e.lower()}" for e in clean_env_list("PHOTO_EXTENSIONS", ".jpg,.jpeg,.png,.heic"))
PATH_BLACKLIST = clean_env_list("PATH_BLACKLIST", "@eaDir,#recycle,.DS_Store")

worker_lock = asyncio.Lock()

# --- DATABASE CONNECTION ---
def get_db_connection(max_retries=10, delay=2):
    retries = 0
    while retries < max_retries:
        try:
            return psycopg2.connect(**DB_CONFIG)
        except psycopg2.OperationalError as e:
            retries += 1
            logger.warning(f"Database connection failed. Retry {retries}/{max_retries} in {delay}s... Error: {e}")
            time.sleep(delay)
    
    logger.critical("Could not connect to the database after maximum retries.")
    raise Exception("Database connection failed.")

# --- METADATA EXTRACTION UTILS ---
def get_clean_string(tag_val):
    if tag_val is None:
        return None
    val_str = str(tag_val).strip()
    val_str = val_str.replace('\x00', '').strip()
    return val_str if val_str and val_str.lower() != 'none' else None

def parse_ratio(ratio):
    if ratio is None:
        return None
    try:
        if hasattr(ratio, 'values') and len(ratio.values) > 0:
            val = ratio.values[0]
            if hasattr(val, 'num') and hasattr(val, 'den'):
                if val.den == 0:
                    return None
                return float(val.num) / float(val.den)
        val_str = str(ratio)
        if '/' in val_str:
            num, den = val_str.split('/')
            return float(num) / float(den)
        return float(val_str)
    except Exception:
        return None

def parse_iso(iso_val):
    if iso_val is None:
        return None
    try:
        if hasattr(iso_val, 'values') and len(iso_val.values) > 0:
            return int(iso_val.values[0])
        return int(str(iso_val).split(',')[0].strip())
    except Exception:
        return None

def get_exif_date(tags):
    for key in ['EXIF DateTimeOriginal', 'Image DateTime', 'EXIF DateTimeDigitized']:
        date_tag = tags.get(key)
        if date_tag:
            try:
                date_str = get_clean_string(date_tag)
                if date_str:
                    return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
            except Exception:
                continue
    return None

def get_date_from_filename(filename):
    patterns = [
        r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})',
        r'(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})',
        r'IMG_(\d{4})(\d{2})(\d{2})_(\d{6})'
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                p = match.groups()
                return datetime(int(p[0]), int(p[1]), int(p[2]), int(p[3]), int(p[4]), int(p[5]))
            except Exception:
                continue
    return None

def extract_photo_metadata(file_path: str) -> dict:
    metadata = {
        "width": None, "height": None, "date_taken": None, "camera_make": None,
        "camera_model": None, "lens_model": None, "exposure_time": None,
        "f_number": None, "iso": None, "focal_length": None
    }
    
    # Dimensions (Pillow header read)
    try:
        with Image.open(file_path) as img:
            metadata["width"], metadata["height"] = img.size
    except Exception as e:
        logger.warning(f"Pillow failed to read dimensions for {file_path}: {e}")
    
    # EXIF extraction
    try:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            metadata["date_taken"] = get_exif_date(tags)
            metadata["camera_make"] = get_clean_string(tags.get('Image Make'))
            metadata["camera_model"] = get_clean_string(tags.get('Image Model'))
            metadata["lens_model"] = get_clean_string(tags.get('EXIF LensModel')) or get_clean_string(tags.get('EXIF LensSpecification'))
            
            exposure = tags.get('EXIF ExposureTime')
            if exposure:
                metadata["exposure_time"] = get_clean_string(exposure)
                
            metadata["f_number"] = parse_ratio(tags.get('EXIF FNumber'))
            metadata["iso"] = parse_iso(tags.get('EXIF ISOSpeedRatings'))
            metadata["focal_length"] = parse_ratio(tags.get('EXIF FocalLength'))
    except Exception as e:
        logger.warning(f"exifread failed for {file_path}: {e}")
    
    # Date Fallbacks
    filename = os.path.basename(file_path)
    if not metadata["date_taken"]:
        metadata["date_taken"] = get_date_from_filename(filename)
    if not metadata["date_taken"]:
        try:
            st = os.stat(file_path)
            try:
                metadata["date_taken"] = datetime.fromtimestamp(st.st_birthtime)
            except AttributeError:
                metadata["date_taken"] = datetime.fromtimestamp(st.st_mtime)
        except Exception:
            metadata["date_taken"] = datetime.now()

    return metadata

# --- SCAN ENGINE ---
def process_scan(scan_id: str, root_path: str):
    logger.info(f"Starting photo scan [ID: {scan_id}] for Path: {root_path}")
    conn = get_db_connection()
    if not conn:
        logger.error(f"Scan {scan_id} failed: Could not connect to DB")
        return
        
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE nas_scans SET status = 'running' WHERE id = %s", (scan_id,))
            conn.commit()

            cur.execute("""
                UPDATE nas_scans SET status = 'superseded' 
                WHERE path = %s AND id != %s AND status = 'completed'
            """, (root_path, scan_id))
            conn.commit()

            # Retrieve database cache
            logger.info("Fetching existing photo cache from DB...")
            cur.execute("SELECT file_path, file_size FROM nas_photos WHERE file_path LIKE %s", (root_path + '%',))
            db_cache = {row[0]: row[1] for row in cur.fetchall()}
            logger.info(f"Found {len(db_cache)} files in database cache.")

            photo_buffer = []
            count = 0
            imported_count = 0
            
            for root, dirs, files in os.walk(root_path):
                dirs[:] = [d for d in dirs if not any(black in d for black in PATH_BLACKLIST)]
                
                for name in files:
                    if any(black in name for black in PATH_BLACKLIST):
                        continue
                    
                    if name.lower().endswith(PHOTO_EXTENSIONS):
                        full_path = os.path.join(root, name)
                        count += 1
                        
                        try:
                            st = os.stat(full_path)
                            current_size = st.st_size
                        except Exception as e:
                            logger.warning(f"Could not stat file {full_path}: {e}")
                            continue

                        cached_size = db_cache.get(full_path)
                        
                        if cached_size != current_size:
                            logger.info(f"Extracting metadata for: {name}")
                            meta = extract_photo_metadata(full_path)
                            imported_count += 1
                        else:
                            # Photo unchanged, skip processing
                            continue

                        rel_dir = os.path.relpath(root, root_path)
                        if rel_dir == ".":
                            rel_dir = "Root"
                        
                        photo_buffer.append((
                            scan_id, full_path, name, rel_dir, current_size,
                            meta["width"], meta["height"], meta["date_taken"],
                            meta["camera_make"], meta["camera_model"], meta["lens_model"],
                            meta["exposure_time"], meta["f_number"], meta["iso"], meta["focal_length"]
                        ))

                        if len(photo_buffer) >= BUFFER_SIZE:
                            logger.info(f"Saving batch of {len(photo_buffer)} photos to database...")
                            insert_photos_batch(cur, photo_buffer)
                            conn.commit()
                            photo_buffer = []

            if photo_buffer:
                logger.info(f"Saving final batch of {len(photo_buffer)} photos to database...")
                insert_photos_batch(cur, photo_buffer)
                conn.commit()

            # Keep unchanged files active by updating scan_id in bulk
            logger.info("Updating scan IDs for unchanged files in the database...")
            cur.execute("""
                UPDATE nas_photos SET scan_id = %s 
                WHERE file_path LIKE %s AND scan_id != %s
            """, (scan_id, root_path + '%', scan_id))
            conn.commit()

            # Purge deleted files from DB
            logger.info("Purging deleted files from database...")
            cur.execute("""
                DELETE FROM nas_photos 
                WHERE file_path LIKE %s AND (scan_id IS NULL OR scan_id != %s)
            """, (root_path + '%', scan_id))
            conn.commit()
            
            cur.execute("""
                UPDATE nas_scans SET status = 'completed', total_count = %s, imported_count = %s 
                WHERE id = %s
            """, (count, imported_count, scan_id))
            conn.commit()
            logger.info(f"Scan {scan_id} finished successfully. Scanned {count} files, updated {imported_count} files.")

    except Exception as e:
        logger.error(f"Error during scan {scan_id}: {e}")
        if conn:
            conn.rollback()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE nas_scans SET status = %s WHERE id = %s", (f"error: {str(e)}", scan_id))
                conn.commit()
        except Exception as db_err:
            logger.error(f"Failed to write error status to DB: {db_err}")
    finally:
        if conn:
            conn.close()

def insert_photos_batch(cur, photo_buffer):
    query = """
        INSERT INTO nas_photos (
            scan_id, file_path, file_name, directory, file_size, 
            width, height, date_taken, camera_make, camera_model, 
            lens_model, exposure_time, f_number, iso, focal_length
        ) VALUES %s
        ON CONFLICT (file_path) DO UPDATE SET
            scan_id = EXCLUDED.scan_id,
            file_name = EXCLUDED.file_name,
            directory = EXCLUDED.directory,
            file_size = EXCLUDED.file_size,
            width = EXCLUDED.width,
            height = EXCLUDED.height,
            date_taken = EXCLUDED.date_taken,
            camera_make = EXCLUDED.camera_make,
            camera_model = EXCLUDED.camera_model,
            lens_model = EXCLUDED.lens_model,
            exposure_time = EXCLUDED.exposure_time,
            f_number = EXCLUDED.f_number,
            iso = EXCLUDED.iso,
            focal_length = EXCLUDED.focal_length;
    """
    execute_values(cur, query, photo_buffer)

async def queue_orchestrator():
    async with worker_lock:
        while True:
            conn = get_db_connection()
            if not conn:
                break
            next_task = None
            try:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT id FROM nas_scans WHERE status = 'running'")
                    if cur.fetchone():
                        break
                    cur.execute("""
                        SELECT id, path FROM nas_scans 
                        WHERE status IN ('pending', 'queued') 
                        ORDER BY created_at ASC LIMIT 1
                    """)
                    next_task = cur.fetchone()
            except Exception as e:
                logger.error(f"Orchestrator DB error: {e}")
            finally:
                conn.close()

            if not next_task:
                break

            logger.info(f"Orchestrator starting scan: {next_task['id']}")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, process_scan, str(next_task['id']), next_task['path'])

# --- FastAPI APP ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Synology Scan Service booting...")
    yield

app = FastAPI(title="Synology NAS Photo Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=True)

async def verify_api_key(header_value: str = Depends(api_key_header)):
    if header_value != API_KEY:
        logger.warning("Invalid API Key attempt")
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return header_value

class ScanRequest(BaseModel):
    path: str

@app.get("/health")
async def health_check():
    return {"status": "online", "heic_supported": HEIF_SUPPORTED}

@app.post("/api/scan", status_code=202)
async def start_scan(payload: ScanRequest, background_tasks: BackgroundTasks, api_key: str = Depends(verify_api_key)):
    target_path = os.path.abspath(payload.path)
    if not os.path.exists(target_path):
        raise HTTPException(status_code=400, detail="Target path does not exist")
    
    new_id = str(uuid.uuid4())
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM nas_scans WHERE status = 'running'")
            status = 'queued' if cur.fetchone() else 'pending'
            cur.execute("INSERT INTO nas_scans (id, path, status) VALUES (%s, %s, %s)", (new_id, target_path, status))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to queue scan: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize scan in database")
    finally:
        conn.close()
            
    background_tasks.add_task(queue_orchestrator)
    return {"scan_id": new_id, "status": status}

@app.get("/api/photos/file/{photo_id}")
async def get_photo_file(photo_id: int):
    conn = get_db_connection()
    row = None
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT file_path FROM nas_photos WHERE id = %s", (photo_id,))
            row = cur.fetchone()
    except Exception as e:
        logger.error(f"Error fetching photo by id: {e}")
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Photo not found in database")
        
    file_path = row["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Physical file not found on NAS storage")

    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".heic":
        if not HEIF_SUPPORTED:
            raise HTTPException(status_code=400, detail="HEIC files are not supported (pillow-heif is not installed)")
        try:
            with Image.open(file_path) as img:
                out = BytesIO()
                img.save(out, format="JPEG", quality=85)
                out.seek(0)
                return StreamingResponse(out, media_type="image/jpeg")
        except Exception as e:
            logger.error(f"Error converting HEIC: {e}")
            raise HTTPException(status_code=500, detail="Failed to convert HEIC image")
            
    media_type = "image/png" if ext == ".png" else "image/jpeg"
    return FileResponse(file_path, media_type=media_type)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT)
