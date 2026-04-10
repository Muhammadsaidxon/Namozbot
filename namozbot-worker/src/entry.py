from workers import Response, WorkerEntrypoint, fetch
import json
from datetime import datetime

CITIES = [
    "Toshkent", "Samarqand", "Buxoro",
    "Andijon", "Namangan", "Farg'ona",
    "Qo'qon", "Nukus", "Qarshi",
    "Termiz", "Jizzax", "Navoiy",
    "Guliston", "Urganch",
]

MAIN_MENU = (
    "Asosiy menyu:\n"
    "📍 Shahar tanlash\n"
    "⏰ Vaqt tanlash\n"
    "🕋 Bugungi vaqtlar\n"
    "📋 Holat\n"
    "⏸ To'xtatish\n"
    "▶️ Qayta yoqish"
)

def city_keyboard():
    rows = [
        ["Toshkent", "Samarqand", "Buxoro"],
        ["Andijon", "Namangan", "Farg'ona"],
        ["Qo'qon", "Nukus", "Qarshi"],
        ["Termiz", "Jizzax", "Navoiy"],
        ["Guliston", "Urganch"],
    ]
    return {
        "keyboard": rows,
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }

def main_keyboard():
    rows = [
        ["📍 Shahar tanlash", "⏰ Vaqt tanlash"],
        ["🕋 Bugungi vaqtlar", "📋 Holat"],
        ["⏸ To'xtatish", "▶️ Qayta yoqish"],
    ]
    return {
        "keyboard": rows,
        "resize_keyboard": True,
    }

def time_keyboard():
    rows = [
        ["01:00", "02:00", "03:00", "04:00", "05:00", "06:00"],
        ["07:00", "08:00", "09:00", "10:00", "11:00", "12:00"],
        ["13:00", "14:00", "15:00", "16:00", "17:00", "18:00"],
        ["19:00", "20:00", "21:00", "22:00", "23:00", "00:00"],
    ]
    return {
        "keyboard": rows,
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }

def is_valid_time_format(value: str) -> bool:
    if len(value) != 5 or value[2] != ":":
        return False
    hh, mm = value.split(":")
    return hh.isdigit() and mm.isdigit() and 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59

async def get_user(env, user_id: str):
    raw = await env.USERS.get(user_id)
    if not raw:
        return None
    return json.loads(raw)

async def save_user(env, user_id: str, data: dict):
    await env.USERS.put(user_id, json.dumps(data, ensure_ascii=False))

async def send_message(bot_token, chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    return await fetch(
        url,
        method="POST",
        headers={"Content-Type": "application/json"},
        body=json.dumps(payload, ensure_ascii=False),
    )

async def handle_start(env, bot_token, chat_id):
    text = (
        "Assalomu alaykum!\n\n"
        "Bu bot sizga tanlagan shaharingizga mos namoz vaqtlari haqida har kuni xabar yuboradi.\n\n"
        "1) 📍 Shahar tanlash — shaharingizni tanlang.\n"
        "2) ⏰ Vaqt tanlash — xabar keladigan vaqtni belgilang.\n"
        "3) 🕋 Bugungi vaqtlar — bugungi namoz vaqtlarini ko'ring.\n"
        "4) 📋 Holat — hozirgi sozlamalaringizni ko'ring.\n"
        "5) ⏸ To'xtatish / ▶️ Qayta yoqish — xabarlarni boshqaring.\n\n"
        "Boshlash uchun pastdagi tugmalardan foydalaning."
    )
    await send_message(bot_token, chat_id, text, main_keyboard())

async def handle_set_city(bot_token, chat_id):
    await send_message(bot_token, chat_id, "Shaharingizni tanlang:", city_keyboard())

async def handle_status(env, bot_token, chat_id, user_id):
    user = await get_user(env, user_id)
    if not user:
        await send_message(
            bot_token,
            chat_id,
            "Siz hali sozlamalarni tanlamagansiz.\nAvval 📍 Shahar tanlash tugmasini bosing.",
            main_keyboard(),
        )
        return

    city_name = user.get("city", "Tanlanmagan")
    send_time = user.get("send_time", "00:05")
    enabled = user.get("enabled", True)
    state = "Yoqilgan" if enabled else "To'xtatilgan"

    text = (
        "📋 Sizning holatingiz:\n\n"
        f"Shahar: {city_name}\n"
        f"Xabar vaqti: {send_time}\n"
        f"Holat: {state}"
    )
    await send_message(bot_token, chat_id, text, main_keyboard())

async def handle_set_time(env, bot_token, chat_id, user_id):
    user = await get_user(env, user_id) or {}
    user["waiting_for_time"] = True
    await save_user(env, user_id, user)

    await send_message(
        bot_token,
        chat_id,
        "Kundalik xabar vaqtini tanlang yoki HH:MM formatida yozing.\nMasalan: 05:00",
        time_keyboard(),
    )

async def handle_save_city(env, bot_token, chat_id, user_id, city_name):
    if city_name not in CITIES:
        return False

    old_user = await get_user(env, user_id) or {}
    new_user = {
        "city": city_name,
        "enabled": True,
        "send_time": old_user.get("send_time", "00:05"),
        "waiting_for_time": False,
    }
    await save_user(env, user_id, new_user)

    await send_message(
        bot_token,
        chat_id,
        f"Shaharingiz saqlandi: {city_name}.\nXabar kelib turadigan vaqtni tanlang.",
        main_keyboard(),
    )
    return True

async def handle_save_time(env, bot_token, chat_id, user_id, time_text):
    user = await get_user(env, user_id)
    if not user or "city" not in user:
        await send_message(bot_token, chat_id, "Avval 📍 Shahar tanlash orqali shaharingizni tanlang.", main_keyboard())
        return

    if not is_valid_time_format(time_text):
        await send_message(
            bot_token,
            chat_id,
            "Vaqt noto'g'ri.\nTo'g'ri format: HH:MM\nMasalan: 05:00",
        )
        return

    user["send_time"] = time_text
    user["waiting_for_time"] = False
    await save_user(env, user_id, user)

    await send_message(
        bot_token,
        chat_id,
        f"Kundalik yuborish vaqti saqlandi: {time_text}",
        main_keyboard(),
    )

async def handle_today_placeholder(env, bot_token, chat_id, user_id):
    user = await get_user(env, user_id)
    if not user or "city" not in user:
        await send_message(bot_token, chat_id, "Avval 📍 Shahar tanlash orqali shaharingizni tanlang.", main_keyboard())
        return

    city = user["city"]
    await send_message(
        bot_token,
        chat_id,
        f"🕋 {city} uchun bugungi vaqtlar API qismi keyingi bosqichda ulanadi.\nHozircha storage va menyu qismi tayyor.",
        main_keyboard(),
    )

async def handle_stop(env, bot_token, chat_id, user_id):
    user = await get_user(env, user_id)
    if not user:
        await send_message(bot_token, chat_id, "Siz hali ro'yxatdan o'tmagansiz. Avval 📍 Shahar tanlashni bosing.", main_keyboard())
        return
    user["enabled"] = False
    user["waiting_for_time"] = False
    await save_user(env, user_id, user)
    await send_message(bot_token, chat_id, "Kundalik xabarlar va eslatmalar to'xtatildi.", main_keyboard())

async def handle_resume(env, bot_token, chat_id, user_id):
    user = await get_user(env, user_id)
    if not user or "city" not in user:
        await send_message(bot_token, chat_id, "Avval 📍 Shahar tanlash orqali shaharingizni tanlang.", main_keyboard())
        return
    user["enabled"] = True
    user["waiting_for_time"] = False
    await save_user(env, user_id, user)
    await send_message(bot_token, chat_id, "Kundalik xabarlar va eslatmalar qayta yoqildi.", main_keyboard())

class Default(WorkerEntrypoint):
    async def fetch(self, request, env, ctx):
        if request.method == "GET":
            return Response("Namoz bot is running", status=200)

        if request.method != "POST":
            return Response("Method not allowed", status=405)

        try:
            update = await request.json()
        except Exception as e:
            return Response(f"Bad JSON: {e}", status=400)

        message = getattr(update, "message", None)
        if not message:
            return Response("OK", status=200)

        chat = getattr(message, "chat", None)
        if not chat:
            return Response("OK", status=200)

        chat_id = getattr(chat, "id", None)
        text = (getattr(message, "text", "") or "").strip()
        from_user = getattr(message, "from_user", None)
        user_id = str(getattr(from_user, "id", chat_id))

        if not chat_id:
            return Response("OK", status=200)

        bot_token = env.BOT_TOKEN
        user = await get_user(env, user_id)

        if text == "/start":
            await handle_start(env, bot_token, chat_id)
        elif text in ("/setcity", "📍 Shahar tanlash"):
            await handle_set_city(bot_token, chat_id)
        elif text in ("/settime", "⏰ Vaqt tanlash"):
            await handle_set_time(env, bot_token, chat_id, user_id)
        elif text in ("/today", "🕋 Bugungi vaqtlar"):
            await handle_today_placeholder(env, bot_token, chat_id, user_id)
        elif text in ("/status", "📋 Holat"):
            await handle_status(env, bot_token, chat_id, user_id)
        elif text in ("/stop", "⏸ To'xtatish"):
            await handle_stop(env, bot_token, chat_id, user_id)
        elif text in ("/resume", "▶️ Qayta yoqish"):
            await handle_resume(env, bot_token, chat_id, user_id)
        elif user and user.get("waiting_for_time"):
            await handle_save_time(env, bot_token, chat_id, user_id, text)
        else:
            saved = await handle_save_city(env, bot_token, chat_id, user_id, text)
            if not saved:
                await send_message(
                    bot_token,
                    chat_id,
                    "Buyruqni tushunmadim. Pastdagi tugmalardan foydalaning.",
                    main_keyboard(),
                )

        return Response("OK", status=200)
