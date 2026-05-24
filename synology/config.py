import os
from dotenv import load_dotenv

# Load env variables
load_dotenv()

# Database Config (Points to the Postgres DB in part 2)
DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("DB_NAME", "screensaver")
DB_USER = os.getenv("DB_USER", "screensaver_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "screensaver_pass")

DB_CONFIG = {
    "host": DB_HOST,
    "database": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD
}

# API Config
API_KEY = os.getenv("API_KEY", "my_secure_screensaver_key")
PORT = int(os.getenv("PORT", 9090))

# Paths & Scanning
PHOTO_DIR = os.getenv("PHOTO_DIR", "/photos")
BUFFER_SIZE = int(os.getenv("BUFFER_SIZE", 1000))

# Clean lists
def clean_env_list(env_key, default):
    raw = os.getenv(env_key, default)
    return [item.strip() for item in raw.split(',') if item.strip()]

PHOTO_EXTENSIONS = tuple(e.lower() if e.startswith('.') else f".{e.lower()}" for e in clean_env_list("PHOTO_EXTENSIONS", ".jpg,.jpeg,.png,.heic"))
PATH_BLACKLIST = clean_env_list("PATH_BLACKLIST", "@eaDir,#recycle,.DS_Store")
