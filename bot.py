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

def get_main_menu():
    keyboard = [
        ["📍 Shahar tanlash", "⏰ Vaqt tanlash"],
        ["🕋 Bugungi vaqtlar", "📋 Holat"],
        ["⏸ To‘xtatish", "▶️ Qayta yoqish"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Assalomu alaykum!\n\n"
        "Bu bot sizga tanlagan shaharingizga mos namoz vaqtlari haqida har kuni xabar yuboradi.\n\n"
        "Quyidagicha ishlaydi:\n"
        "1) 📍 Shahar tanlash — shaharingizni tanlang.\n"
        "2) ⏰ Vaqt tanlash — xabar kelib turadigan vaqtingizni belgilang.\n"
        "3) 🕋 Bugungi vaqtlar — bugungi namoz vaqtlarini ko‘ring.\n"
        "4) 📋 Holat — hozirgi sozlamalaringizni tekshiring.\n"
        "5) ⏸ To‘xtatish / ▶️ Qayta yoqish — xabarlarni boshqaring.\n\n"
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

    if text == "⏰ Vaqt tanlash":
        await settime(update, context)
        return

    if text == "🕋 Bugungi vaqtlar":
        await today(update, context)
        return

    if text == "📋 Holat":
        await status(update, context)
        return

    if text == "📘 Info":
        await start(update, context)
        return

    if text == "⏸ To‘xtatish":
        await stop_daily(update, context)
        return

    if text == "▶️ Qayta yoqish":
        await resume_daily(update, context)
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
    send_time = users[user_id].get("send_time", "00:05")
    enabled = users[user_id].get("enabled", True)

    city_name = get_city_name_from_region(city_region) if city_region else "Tanlanmagan"
    state = "Yoqilgan" if enabled else "To‘xtatilgan"

    await update.message.reply_text(
        f"📋 Sizning holatingiz:\n\n"
        f"Shahar: {city_name}\n"
        f"Xabar vaqti: {send_time}\n"
        f"Holat: {state}",
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
        "send_time": old_data.get("send_time", "00:05"),
    }
    save_users(users)

    schedule_all_for_user(user_id, context)

    await update.message.reply_text(
        f"Shaharingiz saqlandi: {city_name}.\n"
        f"Habar kelib turadigan vaqtni tanlang.",
        reply_markup=get_main_menu()
    )


async def settime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["waiting_for_time"] = True

    keyboard = [
        ["01:00", "02:00", "03:00", "04:00", "05:00", "06:00"],
        ["07:00", "08:00", "09:00", "10:00", "11:00", "12:00"],
        ["13:00", "14:00", "15:00", "16:00", "17:00", "18:00"],
        ["19:00", "20:00", "21:00", "22:00", "23:00", "00:00"],
    ]
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await update.message.reply_text(
        "Kundalik xabar vaqtini tanlang yoki HH:MM formatida yozing.\n"
        "Masalan: 05:00",
        reply_markup=reply_markup
    )


async def mytime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    users = load_users()

    if user_id not in users:
        await update.message.reply_text("Avval /setcity ni bosing.")
        return

    send_time = users[user_id].get("send_time", "00:05")
    await update.message.reply_text(f"Sizning kundalik xabar vaqtingiz: {send_time}")


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
        await update.message.reply_text("Namoz vaqtlarini olishda xatolik bo‘ldi.")
        return

    await update.message.reply_text(build_prayer_message(region, times))


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

    await update.message.reply_text("Kundalik xabarlar va eslatmalar to‘xtatildi.")


async def resume_daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    users = load_users()

    if user_id not in users or "city" not in users[user_id]:
        await update.message.reply_text("Avval /setcity orqali shaharingizni tanlang.")
        return

    users[user_id]["enabled"] = True
    save_users(users)
    schedule_all_for_user(int(user_id), context)

    await update.message.reply_text("Kundalik xabarlar va eslatmalar qayta yoqildi.")


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