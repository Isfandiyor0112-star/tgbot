import telebot
import requests
import os
import time
import http.server
import socketserver
from threading import Thread
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# --- Настройка порта для Render ---
# Используем встроенный сервер, чтобы Render видел открытый порт
def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    handler.log_message = lambda *args: None  # Отключаем лишние логи в консоли
    with socketserver.TCPServer(("", port), handler) as httpd:
        httpd.serve_forever()

# --- Инициализация бота ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start_cmd(message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📍 Joylashuvni yuborish", request_location=True))
    bot.send_message(
        message.chat.id, 
        "Salom! Men yaqin joylarni topuvchi botman.\nJoylashuvingizni yuboring 👇", 
        reply_markup=kb
    )

@bot.message_handler(content_types=['location'])
def handle_location(message):
    lat, lon = message.location.latitude, message.location.longitude

    try:
        # Reverse geocoding
        rev_url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=10&addressdetails=1"
        resp = requests.get(rev_url, headers={'User-Agent': 'GeoBot-App'}).json()
        
        country = resp.get("address", {}).get("country", "Noma’lum mamlakat")
        display_name = resp.get("display_name", "Joy topilmadi")

        bot.send_message(
            message.chat.id,
            f"📍 Joylashuvni aniqladim:\n<b>{display_name}</b>\n🌍 {country}",
            parse_mode="HTML"
        )

        kb = InlineKeyboardMarkup()
        # Твои категории полностью сохранены
        categories = {
            "🍴 Restoran": "restaurant",
            "💊 Dorixona": "pharmacy",
            "🏧 Bankomat": "atm",
            "⛽️ Yoqilg‘i": "fuel",
            "🛍 Do‘kon": "supermarket"
        }
        for k, v in categories.items():
            kb.add(InlineKeyboardButton(k, callback_data=f"{v}|{lat}|{lon}"))

        bot.send_message(message.chat.id, "Qaysi turdagi joylarni topay?", reply_markup=kb)
    except Exception as e:
        bot.send_message(message.chat.id, "Xatolik yuz berdi, iltimos qaytadan urinib ko'ring.")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        data = call.data.split("|")
        cat, lat, lon = data[0], float(data[1]), float(data[2])

        # Область поиска 2км
        delta = 0.02 
        viewbox = f"{lon-delta},{lat+delta},{lon+delta},{lat-delta}"

        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': cat,
            'format': 'json',
            'limit': 5,
            'viewbox': viewbox,
            'bounded': 1
        }

        resp = requests.get(url, headers={'User-Agent': 'GeoBot-App'}, params=params)
        results = resp.json()

        if not results:
            bot.send_message(call.message.chat.id, "Hech narsa topilmadi 😕")
            return

        text = f"🗺 <b>Eng yaqin joylar ({cat}):</b>\n\n"
        for place in results:
            name = place.get('display_name', 'Noma’lum joy').split(',')[0]
            plat, plon = place['lat'], place['lon']
            # Твоя ссылка на карты
            map_link = f"https://www.google.com/maps?q={plat},{plon}"
            text += f"📍 <b>{name}</b>\n<a href='{map_link}'>Xaritada ko‘rish</a>\n\n"

        bot.send_message(call.message.chat.id, text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        bot.answer_callback_query(call.id, "Xatolik yuz berdi.")

# --- Запуск ---
if __name__ == "__main__":
    # Запускаем сервер порта в фоновом потоке
    Thread(target=run_health_check_server, daemon=True).start()
    
    print("Бот запущен...")
    # Бесконечный цикл с защитой от вылетов
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=5)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(15)
