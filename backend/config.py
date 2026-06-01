import os
from dotenv import load_dotenv

load_dotenv()

# Database credentials
DB_HOST = os.getenv("DB_IP", "db")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "screensaver")
DB_USER = os.getenv("DB_USER", "screensaver_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "screensaver_pass")

DB_CONFIG = {
    "host": DB_HOST,
    "port": DB_PORT,
    "database": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD
}

# API configuration
PORT = int(os.getenv("BACKEND_PORT", 9090))

# Telegram notifications settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SYNOLOGY_HOST = os.getenv("SYNOLOGY_IP", "localhost")
SYNOLOGY_PORT = int(os.getenv("SYNOLOGY_PORT", 9092))
SYNOLOGY_URL = f"http://{SYNOLOGY_HOST}:{SYNOLOGY_PORT}"
