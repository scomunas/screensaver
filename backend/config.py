import os
from dotenv import load_dotenv

load_dotenv()

# Database credentials
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

# API configuration: Use BACKEND_PORT specifically
PORT = int(os.getenv("BACKEND_PORT", 9091))
