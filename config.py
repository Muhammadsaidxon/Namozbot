import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
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