import logging
from typing import Optional, Dict, List
from datetime import date
from calendar import monthrange
import requests

from config import HEADERS, CITIES


def get_city_name_from_region(region: str) -> str:
    for city_name, city_region in CITIES.items():
        if city_region == region:
            return city_name
    return region


def get_prayer_times(region: str) -> Optional[Dict[str, str]]:
    url = "https://namoz-vaqti.uz/index.php"
    params = {
        "region": region,
        "lang": "lotin",
        "period": "today",
        "format": "json",
    }

    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=20)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logging.error("Prayer API error: %s", e)
        return None

    try:
        times = data["today"]["times"]
        return {
            "Bomdod": times["bomdod"],
            "Quyosh": times["quyosh"],
            "Peshin": times["peshin"],
            "Asr": times["asr"],
            "Shom": times["shom"],
            "Xufton": times["xufton"],
        }
    except Exception as e:
        logging.error("Prayer API parse error: %s", e)
        return None


def build_prayer_message(region: str, times: Dict[str, str]) -> str:
    city_name = get_city_name_from_region(region)
    return (
        f"Bugungi namoz vaqtlari — {city_name}\n\n"
        f"Bomdod: {times['Bomdod']}\n"
        f"Quyosh: {times['Quyosh']}\n"
        f"Peshin: {times['Peshin']}\n"
        f"Asr: {times['Asr']}\n"
        f"Shom: {times['Shom']}\n"
        f"Xufton: {times['Xufton']}"
    )


def get_prayer_times_for_date(region: str, day: date) -> Optional[Dict[str, str]]:
    url = "https://namoz-vaqti.uz/index.php"
    params = {
        "region": region,
        "lang": "lotin",
        "period": day.isoformat(),
        "format": "json",
    }

    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=20)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logging.error("Prayer API error: %s", e)
        return None

    try:
        times = data["times"] if "times" in data else data["today"]["times"]
        return {
            "Bomdod": times["bomdod"],
            "Quyosh": times["quyosh"],
            "Peshin": times["peshin"],
            "Asr": times["asr"],
            "Shom": times["shom"],
            "Xufton": times["xufton"],
        }
    except Exception as e:
        logging.error("Prayer API parse error: %s", e)
        return None


def collect_month_times(region: str, year: int, month: int) -> List[Dict[str, str]]:
    days_in_month = monthrange(year, month)[1]
    results: List[Dict[str, str]] = []

    for day in range(1, days_in_month + 1):
        current = date(year, month, day)
        times = get_prayer_times_for_date(region, current)
        if times:
            results.append({
                "date": current.isoformat(),
                **times
            })
    return results

