import os
import uuid
import logging
import asyncio
from datetime import datetime
from psycopg2.extras import execute_values, DictCursor
from config import PHOTO_EXTENSIONS, PATH_BLACKLIST, BUFFER_SIZE
from database import get_db_connection
from scanner_utils import extract_photo_metadata

logger = logging.getLogger("nas_manager")
worker_lock = asyncio.Lock()

def process_scan(scan_id: str, root_path: str):
    logger.info(f"Starting photo scan [ID: {scan_id}] for Path: {root_path}")
    conn = get_db_connection()
    if not conn:
        logger.error(f"Scan {scan_id} failed: Could not connect to DB")
        return
        
    try:
        with conn.cursor() as cur:
            # 1. Update status to running
            cur.execute("UPDATE nas_scans SET status = 'running' WHERE id = %s", (scan_id,))
            conn.commit()

            # 2. Mark previous scans for this same root path as superseded
            cur.execute("""
                UPDATE nas_scans 
                SET status = 'superseded' 
                WHERE path = %s AND id != %s AND status = 'completed'
            """, (root_path, scan_id))
            conn.commit()

            # 3. Retrieve currently cached photos in DB to avoid reprocessing EXIF for unchanged files
            logger.info("Fetching existing photo cache from DB...")
            cur.execute("SELECT file_path, file_size FROM nas_photos WHERE file_path LIKE %s", (root_path + '%',))
            db_cache = {row[0]: row[1] for row in cur.fetchall()}
            logger.info(f"Found {len(db_cache)} files in database cache.")

            photo_buffer = []
            count = 0
            imported_count = 0
            
            # 4. Walk file system
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
                            # It exists in cache and hasn't changed. Skip EXIF parsing
                            continue

                        rel_dir = os.path.relpath(root, root_path)
                        if rel_dir == ".":
                            rel_dir = "Root"
                        
                        photo_buffer.append((
                            scan_id,
                            full_path,
                            name,
                            rel_dir,
                            current_size,
                            meta["width"],
                            meta["height"],
                            meta["date_taken"],
                            meta["camera_make"],
                            meta["camera_model"],
                            meta["lens_model"],
                            meta["exposure_time"],
                            meta["f_number"],
                            meta["iso"],
                            meta["focal_length"]
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

            # 5. Update scan_id in bulk for unchanged, existing cached files to keep them active
            logger.info("Updating scan IDs for unchanged files in the database...")
            cur.execute("""
                UPDATE nas_photos 
                SET scan_id = %s 
                WHERE file_path LIKE %s AND scan_id != %s
            """, (scan_id, root_path + '%', scan_id))
            conn.commit()

            # 6. Purge files deleted from disk
            logger.info("Purging deleted files from database...")
            cur.execute("""
                DELETE FROM nas_photos 
                WHERE file_path LIKE %s AND (scan_id IS NULL OR scan_id != %s)
            """, (root_path + '%', scan_id))
            conn.commit()
            
            # 7. Mark scan as completed
            cur.execute("""
                UPDATE nas_scans 
                SET status = 'completed', total_count = %s, imported_count = %s 
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
    logger.info("Queue Orchestrator running.")
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
                        logger.info("A scan is already running. Orchestrator waiting.")
                        break
                    
                    cur.execute("""
                        SELECT id, path FROM nas_scans 
                        WHERE status IN ('pending', 'queued') 
                        ORDER BY created_at ASC 
                        LIMIT 1
                    """)
                    next_task = cur.fetchone()
            except Exception as e:
                logger.error(f"Orchestrator DB error: {e}")
            finally:
                conn.close()

            if not next_task:
                logger.info("No pending tasks in queue.")
                break

            logger.info(f"Orchestrator starting task: {next_task['id']}")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, process_scan, str(next_task['id']), next_task['path'])
