from datetime import time, datetime, timedelta
from telegram.ext import ContextTypes

from config import UZBEKISTAN_TZ
from storage import load_users
from api import get_prayer_times, build_prayer_message


REMINDER_OFFSET_MINUTES = 15


def parse_user_time(time_str: str) -> time:
    hour, minute = map(int, time_str.split(":"))
    return time(hour=hour, minute=minute, tzinfo=UZBEKISTAN_TZ)


def parse_clock_to_datetime(clock_str: str) -> datetime:
    now = datetime.now(UZBEKISTAN_TZ)
    hour, minute = map(int, clock_str.split(":"))
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def subtract_minutes(time_str: str, minutes: int) -> str:
    dt = datetime.strptime(time_str, "%H:%M")
    dt -= timedelta(minutes=minutes)
    return dt.strftime("%H:%M")


def resolve_send_time(user_data: dict, prayer_times: dict) -> str:
    t = user_data.get("send_time_type", "morning")

    if t == "bomdod_before":
        bomdod = prayer_times.get("Bomdod")
        if bomdod:
            return subtract_minutes(bomdod, 15)
        return "04:00"  # Fallback

    elif t == "morning":
        return "08:00"

    elif t == "evening":
        return "19:00"

    return "08:00"  # Default


def remove_jobs_by_prefix(user_id: int, context: ContextTypes.DEFAULT_TYPE, prefix: str) -> None:
    job_name_prefix = f"{prefix}_{user_id}"
    for job in context.job_queue.jobs():
        if job.name and job.name.startswith(job_name_prefix):
            job.schedule_removal()


def remove_all_user_jobs(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    prefixes = ["summary", "refresh", "reminder"]
    for prefix in prefixes:
        remove_jobs_by_prefix(user_id, context, prefix)


async def send_daily_prayer_times(context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = context.job.data["user_id"]

    users = load_users()
    user_data = users.get(str(user_id))
    if not user_data or not user_data.get("enabled", True):
        return

    region = user_data.get("city")
    if not region:
        return

    times = get_prayer_times(region)
    if not times:
        await context.bot.send_message(
            chat_id=user_id,
            text="Bugungi namoz vaqtlarini olishda xatolik bo‘ldi."
        )
        return

    await context.bot.send_message(
        chat_id=user_id,
        text=build_prayer_message(region, times)
    )


async def send_prayer_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data
    user_id = data["user_id"]
    prayer_name = data["prayer_name"]
    prayer_time = data["prayer_time"]

    users = load_users()
    user_data = users.get(str(user_id))
    if not user_data or not user_data.get("enabled", True):
        return

    await context.bot.send_message(
        chat_id=user_id,
        text=f"{prayer_name} vaqti {REMINDER_OFFSET_MINUTES} daqiqadan keyin ({prayer_time})."
    )


def schedule_prayer_reminders_for_user(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    users = load_users()
    user_data = users.get(str(user_id))
    if not user_data or not user_data.get("enabled", True):
        return

    region = user_data.get("city")
    if not region:
        return

    times = get_prayer_times(region)
    if not times:
        return

    remove_jobs_by_prefix(user_id, context, "reminder")

    prayers_to_remind = ["Bomdod", "Peshin", "Asr", "Shom", "Xufton"]

    now = datetime.now(UZBEKISTAN_TZ)

    for prayer_name in prayers_to_remind:
        prayer_clock = times.get(prayer_name)
        if not prayer_clock:
            continue

        prayer_dt = parse_clock_to_datetime(prayer_clock)
        reminder_dt = prayer_dt - timedelta(minutes=REMINDER_OFFSET_MINUTES)

        if reminder_dt > now:
            context.job_queue.run_once(
                send_prayer_reminder,
                when=reminder_dt,
                name=f"reminder_{user_id}_{prayer_name}",
                data={
                    "user_id": user_id,
                    "prayer_name": prayer_name,
                    "prayer_time": prayer_clock,
                },
            )


async def refresh_user_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = context.job.data["user_id"]
    schedule_prayer_reminders_for_user(user_id, context)


def schedule_daily_summary_for_user(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    users = load_users()
    user_data = users.get(str(user_id))
    if not user_data or not user_data.get("enabled", True):
        return

    region = user_data.get("city")
    if not region:
        return

    times = get_prayer_times(region)
    if not times:
        return

    send_time_str = resolve_send_time(user_data, times)

    remove_jobs_by_prefix(user_id, context, "summary")

    context.job_queue.run_daily(
        send_daily_prayer_times,
        time=parse_user_time(send_time_str),
        name=f"summary_{user_id}",
        data={"user_id": user_id},
    )


def schedule_daily_refresh_for_user(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    remove_jobs_by_prefix(user_id, context, "refresh")

    context.job_queue.run_daily(
        refresh_user_reminders,
        time=time(hour=0, minute=10, tzinfo=UZBEKISTAN_TZ),
        name=f"refresh_{user_id}",
        data={"user_id": user_id},
    )


def schedule_all_for_user(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    users = load_users()
    user_data = users.get(str(user_id))
    if not user_data or not user_data.get("enabled", True):
        remove_all_user_jobs(user_id, context)
        return

    schedule_daily_summary_for_user(user_id, context)
    schedule_daily_refresh_for_user(user_id, context)
    schedule_prayer_reminders_for_user(user_id, context)


async def restore_jobs(application) -> None:
    users = load_users()

    for user_id_str, user_data in users.items():
        if not user_data.get("enabled", True):
            continue
        if not user_data.get("city"):
            continue

        user_id = int(user_id_str)

        region = user_data.get("city")
        times = get_prayer_times(region)
        if not times:
            continue

        send_time_str = resolve_send_time(user_data, times)

        application.job_queue.run_daily(
            send_daily_prayer_times,
            time=parse_user_time(send_time_str),
            name=f"summary_{user_id}",
            data={"user_id": user_id},
        )

        application.job_queue.run_daily(
            refresh_user_reminders,
            time=time(hour=0, minute=10, tzinfo=UZBEKISTAN_TZ),
            name=f"refresh_{user_id}",
            data={"user_id": user_id},
        )

        temp_context = type("TempContext", (), {"job_queue": application.job_queue})()
        schedule_prayer_reminders_for_user(user_id, temp_context)