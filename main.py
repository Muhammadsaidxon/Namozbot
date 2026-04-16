import logging
import asyncio
import os
import threading

from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from datetime import datetime
from pathlib import Path

from config import BOT_TOKEN, CITIES, UZBEKISTAN_TZ
from storage import load_users, save_users
from api import (
    get_prayer_times,
    build_prayer_message,
    get_city_name_from_region,
    collect_month_times,
)
from pdf_utils import build_prayer_pdf
from scheduler import schedule_all_for_user, remove_all_user_jobs, restore_jobs

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        return


def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logging.info("Health server running on port %s", port)
    server.serve_forever()


TIME_TYPE_MAP = {
    "🌅 Bomdoddan oldin": "bomdod_before",
    "☀️ Ertalab": "morning",
    "🌇 Kechqurun": "evening"
}

MONTH_MAP = {
    "Yanvar": 1,
    "Fevral": 2,
    "Mart": 3,
    "Aprel": 4,
    "May": 5,
    "Iyun": 6,
    "Iyul": 7,
    "Avgust": 8,
    "Sentabr": 9,
    "Oktabr": 10,
    "Noyabr": 11,
    "Dekabr": 12,
}


def time_type_keyboard():
    keyboard = [
        ["🌅 Bomdoddan oldin"],
        ["☀️ Ertalab"],
        ["🌇 Kechqurun"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def months_keyboard():
    keyboard = [
        ["Yanvar", "Fevral", "Mart"],
        ["Aprel", "May", "Iyun"],
        ["Iyul", "Avgust", "Sentabr"],
        ["Oktabr", "Noyabr", "Dekabr"],
        ["⬅️ Orqaga"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def get_main_menu():
    keyboard = [
        ["📍 Shahar tanlash", "⏰ Xabar vaqti"],
        ["📅 Bugungi vaqtlar", "🗓 Oylik PDF"],
        ["ℹ️ Holat"],
        ["🔕 To‘xtatish", "🔔 Yoqish"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Assalomu alaykum!\n\n"
        "Bu bot sizga tanlagan shaharingizga mos namoz vaqtlari haqida har kuni xabar yuboradi.\n\n"
        "Quyidagicha ishlaydi:\n"
        "1) 📍 Shahar tanlash — shaharingizni tanlang.\n"
        "2) ⏰ Xabar vaqti — xabar keladigan vaqtni tanlang.\n"
        "3) 📅 Bugungi vaqtlar — bugungi namoz vaqtlarini ko‘ring.\n"
        "4) ℹ️ Holat — hozirgi sozlamalaringizni ko‘ring.\n"
        "5) 🔕 To‘xtatish / 🔔 Yoqish — xabarlarni boshqaring.\n\n"
        "Boshlash uchun pastdagi tugmalardan foydalaning.",
        reply_markup=get_main_menu()
    )


async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    if text == "📍 Shahar tanlash":
        await set_city(update, context)
        return

    if text == "⏰ Xabar vaqti":
        await settime(update, context)
        return

    if text == "📅 Bugungi vaqtlar":
        await today(update, context)
        return

    if text == "🗓 Oylik PDF":
        await month_pdf(update, context)
        return

    if text in MONTH_MAP:
        await generate_specific_month_pdf(update, context, MONTH_MAP[text], text)
        return

    if text == "⬅️ Orqaga":
        await update.message.reply_text("Asosiy menyu", reply_markup=get_main_menu())
        return

    if text == "ℹ️ Holat":
        await status(update, context)
        return

    if text == "📘 Info":
        await start(update, context)
        return

    if text == "🔕 To‘xtatish":
        await stop_daily(update, context)
        return

    if text == "🔔 Yoqish":
        await resume_daily(update, context)
        return

    if text in TIME_TYPE_MAP:
        await save_time_type(update, context)
        return

    await save_city(update, context)


async def set_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        ["Toshkent", "Samarqand", "Buxoro"],
        ["Andijon", "Namangan", "Farg‘ona"],
        ["Qo‘qon", "Nukus", "Qarshi"],
        ["Termiz", "Jizzax", "Navoiy"],
        ["Guliston", "Urganch"],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "Shaharingizni tanlang:",
        reply_markup=reply_markup
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    users = load_users()

    if user_id not in users:
        await update.message.reply_text(
            "Siz hali sozlamalarni tanlamagansiz.\n"
            "Avval 📍 Shahar tanlash tugmasini bosing.",
            reply_markup=get_main_menu()
        )
        return

    city_region = users[user_id].get("city")
    send_time_type = users[user_id].get("send_time_type", "morning")
    enabled = users[user_id].get("enabled", True)

    city_name = get_city_name_from_region(city_region) if city_region else "Tanlanmagan"
    state = "Yoqilgan" if enabled else "To‘xtatilgan"

    time_type_display = {
        "bomdod_before": "Bomdoddan 15 daqiqa oldin",
        "morning": "Ertalab (08:00)",
        "evening": "Kechqurun (19:00)"
    }.get(send_time_type, send_time_type)

    await update.message.reply_text(
        f"📍 Shahar: {city_name}\n"
        f"⏰ Xabar vaqti: {time_type_display}\n"
        f"🔔 Holat: {state}",
        reply_markup=get_main_menu()
    )


async def save_time_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    text = update.message.text.strip()

    users = load_users()
    if user_id not in users or "city" not in users[user_id]:
        await update.message.reply_text(
            "Avval 📍 Shahar tanlash orqali shaharingizni tanlang.",
            reply_markup=get_main_menu()
        )
        return

    time_type = TIME_TYPE_MAP[text]
    users[user_id]["send_time_type"] = time_type
    save_users(users)

    schedule_all_for_user(int(user_id), context)

    await update.message.reply_text(
        "✅ Xabar vaqti saqlandi.",
        reply_markup=get_main_menu()
    )


async def save_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    city_name = update.message.text.strip()

    if city_name not in CITIES:
        return

    user_id = update.message.from_user.id
    region = CITIES[city_name]

    users = load_users()
    old_data = users.get(str(user_id), {})

    users[str(user_id)] = {
        "city": region,
        "enabled": True,
        "send_time_type": old_data.get("send_time_type", "morning"),
    }
    save_users(users)

    schedule_all_for_user(user_id, context)

    await update.message.reply_text(
        f"Shaharingiz saqlandi: {city_name}.\n"
        f"Habar kelib turadigan vaqtni tanlang.",
        reply_markup=get_main_menu()
    )


async def settime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Kundalik xabar vaqtini tanlang:",
        reply_markup=time_type_keyboard()
    )


async def mytime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    users = load_users()

    if user_id not in users:
        await update.message.reply_text("Avval /setcity ni bosing.")
        return

    send_time_type = users[user_id].get("send_time_type", "morning")
    time_display = {
        "bomdod_before": "Bomdoddan 15 daqiqa oldin",
        "morning": "Ertalab (08:00)",
        "evening": "Kechqurun (19:00)"
    }.get(send_time_type, send_time_type)
    await update.message.reply_text(f"Sizning kundalik xabar vaqtingiz: {time_display}")


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    users = load_users()

    if user_id not in users or "city" not in users[user_id]:
        await update.message.reply_text("Avval /setcity orqali shaharingizni tanlang.")
        return

    region = users[user_id]["city"]
    times = get_prayer_times(region)

    if not times:
        await update.message.reply_text(
            "⚠️ Vaqtlarni olishda xatolik yuz berdi. Keyinroq urinib ko‘ring.",
            reply_markup=get_main_menu()
        )
        return

    await update.message.reply_text(
        build_prayer_message(region, times),
        reply_markup=get_main_menu()
    )


async def month_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    users = load_users()

    if user_id not in users or "city" not in users[user_id]:
        await update.message.reply_text(
            "Avval 📍 Shahar tanlash orqali shaharingizni tanlang."
        )
        return

    await update.message.reply_text(
        "Qaysi oy uchun PDF kerak? Tanlang:",
        reply_markup=months_keyboard()
    )


async def generate_specific_month_pdf(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    month_num: int,
    month_name: str,
) -> None:
    user_id = str(update.message.from_user.id)
    users = load_users()

    if user_id not in users or "city" not in users[user_id]:
        await update.message.reply_text(
            "Avval 📍 Shahar tanlash orqali shaharingizni tanlang."
        )
        return

    region = users[user_id]["city"]
    city_name = get_city_name_from_region(region)
    now = datetime.now(UZBEKISTAN_TZ)

    wait_msg = await update.message.reply_text(
        f"⏳ {month_name} oyi uchun PDF tayyorlanmoqda..."
    )
    try:
        logging.info(
            "month_pdf started for user_id=%s region=%s month=%s",
            user_id, region, month_num
        )
        rows = await asyncio.to_thread(collect_month_times, region, now.year, month_num)
        if not rows:
            await update.message.reply_text("Ma’lumot olishda xatolik bo‘ldi.")
            return

        output_path = Path("generated") / f"{user_id}_{now.year}_{month_num:02d}_oylik.pdf"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        build_prayer_pdf(
            title=f"{month_name} {now.year} - Namoz vaqtlari",
            city_name=city_name,
            rows=rows,
            output_path=str(output_path),
        )

        with open(output_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=f"{city_name}_{month_name}_{now.year}.pdf",
                caption=f"✅ {month_name} oyi uchun taqvim tayyor.",
                reply_markup=get_main_menu()
            )
    except Exception as e:
        logging.exception("month_pdf error: %s", e)
        await update.message.reply_text("Oylik PDF yaratishda xatolik bo‘ldi.")
    finally:
        try:
            await wait_msg.delete()
        except Exception:
            pass


async def mycity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    users = load_users()

    if user_id not in users or "city" not in users[user_id]:
        await update.message.reply_text("Siz hali shahar tanlamagansiz. /setcity ni bosing.")
        return

    region = users[user_id]["city"]
    city_name = get_city_name_from_region(region)
    enabled = users[user_id].get("enabled", True)

    status_text = "yoqilgan" if enabled else "to‘xtatilgan"

    await update.message.reply_text(
        f"Siz tanlagan shahar: {city_name}\n"
        f"Holat: {status_text}"
    )


async def stop_daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    users = load_users()

    if user_id not in users:
        await update.message.reply_text(
            "Siz hali ro‘yxatdan o‘tmagansiz. /setcity ni bosing."
        )
        return

    users[user_id]["enabled"] = False
    save_users(users)
    remove_all_user_jobs(int(user_id), context)

    await update.message.reply_text(
        "Kundalik xabarlar va eslatmalar to‘xtatildi.",
        reply_markup=get_main_menu()
    )


async def resume_daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    users = load_users()

    if user_id not in users or "city" not in users[user_id]:
        await update.message.reply_text("Avval /setcity orqali shaharingizni tanlang.")
        return

    users[user_id]["enabled"] = True
    save_users(users)
    schedule_all_for_user(int(user_id), context)

    await update.message.reply_text(
        "Kundalik xabarlar va eslatmalar qayta yoqildi.",
        reply_markup=get_main_menu()
    )


def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not found in environment variable")

    threading.Thread(target=run_health_server, daemon=True).start()

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(restore_jobs)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setcity", set_city))
    app.add_handler(CommandHandler("settime", settime))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("mycity", mycity))
    app.add_handler(CommandHandler("mytime", mytime))
    app.add_handler(CommandHandler("stop", stop_daily))
    app.add_handler(CommandHandler("resume", resume_daily))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_buttons))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()