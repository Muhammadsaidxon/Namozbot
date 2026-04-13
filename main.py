import logging
import re

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN, CITIES
from storage import load_users, save_users
from api import get_prayer_times, build_prayer_message, get_city_name_from_region
from scheduler import schedule_all_for_user, remove_all_user_jobs, restore_jobs

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


def is_valid_time_format(value: str) -> bool:
    return bool(re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", value))

TIME_TYPE_MAP = {
    "🌅 Bomdoddan oldin": "bomdod_before",
    "☀️ Ertalab": "morning",
    "🌇 Kechqurun": "evening"
}

def time_type_keyboard():
    keyboard = [
        ["🌅 Bomdoddan oldin"],
        ["☀️ Ertalab"],
        ["🌇 Kechqurun"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def get_main_menu():

    keyboard = [
        ["📍 Shahar tanlash", "⏰ Xabar vaqti"],
        ["📅 Bugungi vaqtlar", "ℹ️ Holat"],
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

    if context.user_data.get("waiting_for_time"):
        await save_time(update, context)
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

    # Map back to display name
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
        await update.message.reply_text("Avval 📍 Shahar tanlash orqali shaharingizni tanlang.", reply_markup=get_main_menu())
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


async def save_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get("waiting_for_time"):
        return

    if not update.message or not update.message.text:
        return

    user_id = str(update.message.from_user.id)
    time_text = update.message.text.strip()

    if not is_valid_time_format(time_text):
        await update.message.reply_text(
            "Vaqt noto‘g‘ri.\n"
            "To‘g‘ri format: HH:MM\n"
            "Masalan: 05:00"
        )
        return

    users = load_users()
    if user_id not in users or "city" not in users[user_id]:
        context.user_data["waiting_for_time"] = False
        await update.message.reply_text("Avval /setcity orqali shaharingizni tanlang.")
        return

    users[user_id]["send_time"] = time_text
    save_users(users)

    schedule_all_for_user(int(user_id), context)
    context.user_data["waiting_for_time"] = False

    await update.message.reply_text(
        f"Kundalik yuborish vaqti saqlandi: {time_text}",
        reply_markup=get_main_menu()
    )


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

    await update.message.reply_text(build_prayer_message(region, times), reply_markup=get_main_menu())


async def mycity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    users = load_users()

    if user_id not in users or "city" not in users[user_id]:
        await update.message.reply_text("Siz hali shahar tanlamagansiz. /setcity ni bosing.")
        return

    region = users[user_id]["city"]
    city_name = get_city_name_from_region(region)
    enabled = users[user_id].get("enabled", True)

    status = "yoqilgan" if enabled else "to‘xtatilgan"

    await update.message.reply_text(
        f"Siz tanlagan shahar: {city_name}\n"
        f"Holat: {status}"
    )


async def stop_daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    users = load_users()

    if user_id not in users:
        await update.message.reply_text("Siz hali ro‘yxatdan o‘tmagansiz. /setcity ni bosing.")
        return

    users[user_id]["enabled"] = False
    save_users(users)
    remove_all_user_jobs(int(user_id), context)

    await update.message.reply_text("Kundalik xabarlar va eslatmalar to‘xtatildi.", reply_markup=get_main_menu())


async def resume_daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    users = load_users()

    if user_id not in users or "city" not in users[user_id]:
        await update.message.reply_text("Avval /setcity orqali shaharingizni tanlang.")
        return

    users[user_id]["enabled"] = True
    save_users(users)
    schedule_all_for_user(int(user_id), context)

    await update.message.reply_text("Kundalik xabarlar va eslatmalar qayta yoqildi.", reply_markup=get_main_menu())


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("waiting_for_time"):
        await save_time(update, context)
        return

    await save_city(update, context)


def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not found in .env file")

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