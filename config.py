import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    # Fallback: try to read from .env file directly
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith('BOT_TOKEN='):
                    BOT_TOKEN = line.split('=', 1)[1].strip()
                    break
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not found in .env file or environment variable")
USERS_FILE = "users.json"
UZBEKISTAN_TZ = ZoneInfo("Asia/Tashkent")

CITIES = {
    "Toshkent": "toshkent-shahri",
    "Samarqand": "samarqand",
    "Buxoro": "buxoro",
    "Andijon": "andijon",
    "Namangan": "namangan",
    "Farg‘ona": "fargona",
    "Qo‘qon": "qoqon",
    "Nukus": "nukus",
    "Qarshi": "qarshi",
    "Termiz": "termiz",
    "Jizzax": "jizzax",
    "Navoiy": "navoiy",
    "Guliston": "guliston",
    "Urganch": "urganch",
}

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0"
}