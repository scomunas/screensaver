import time
import logging
import psycopg2
from psycopg2.extras import DictCursor
from config import DB_CONFIG

logger = logging.getLogger("nas_backend")

def get_db_connection(max_retries=10, delay=2):
    retries = 0
    while retries < max_retries:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            return conn
        except psycopg2.OperationalError as e:
            retries += 1
            logger.warning(f"Database connection failed. Retry {retries}/{max_retries} in {delay}s... Error: {e}")
            time.sleep(delay)
    
    logger.critical("Could not connect to the database after maximum retries.")
    raise Exception("Database connection failed.")

def init_db():
    logger.info("Initializing database tables...")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Scans tracking table
            cur.execute('''
                CREATE TABLE IF NOT EXISTS nas_scans (
                    id UUID PRIMARY KEY, 
                    path TEXT NOT NULL, 
                    status TEXT DEFAULT 'pending', 
                    total_count INTEGER DEFAULT 0,
                    imported_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 2. Photos metadata table
            cur.execute('''
                CREATE TABLE IF NOT EXISTS nas_photos (
                    id SERIAL PRIMARY KEY,
                    scan_id UUID REFERENCES nas_scans(id) ON DELETE SET NULL, 
                    file_path TEXT UNIQUE NOT NULL, 
                    file_name TEXT NOT NULL,
                    directory TEXT NOT NULL,
                    file_size BIGINT NOT NULL,
                    width INTEGER,
                    height INTEGER,
                    date_taken TIMESTAMP,
                    camera_make TEXT,
                    camera_model TEXT,
                    lens_model TEXT,
                    exposure_time TEXT,
                    f_number REAL,
                    iso INTEGER,
                    focal_length REAL,
                    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Indexes
            cur.execute('CREATE INDEX IF NOT EXISTS idx_nas_photos_scan_id ON nas_photos(scan_id)')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_nas_photos_path ON nas_photos(file_path)')
            
            # Migrations for video support
            cur.execute("ALTER TABLE nas_photos ADD COLUMN IF NOT EXISTS media_type VARCHAR(10) DEFAULT 'photo'")
            cur.execute("ALTER TABLE nas_photos ADD COLUMN IF NOT EXISTS duration REAL")
            cur.execute("ALTER TABLE nas_photos ALTER COLUMN file_size TYPE BIGINT")
            
            conn.commit()
            logger.info("Database initialized successfully.")
    except Exception as e:
        logger.critical(f"CRITICAL ERROR during DB initialization: {e}")
        if conn:
            conn.rollback()
        raise e
    finally:
        conn.close()

def get_random_photo_record():
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("""
                SELECT id, file_path, file_name, directory, file_size, width, height, 
                       date_taken, camera_make, camera_model, lens_model, 
                       exposure_time, f_number, iso, focal_length, media_type, duration
                FROM nas_photos
                ORDER BY RANDOM()
                LIMIT 1
            """)
            return cur.fetchone()
    except Exception as e:
        logger.error(f"Error fetching random photo: {e}")
        return None
    finally:
        conn.close()
