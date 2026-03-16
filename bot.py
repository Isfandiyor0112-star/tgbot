import telebot
import requests
import os
import time
import http.server
import socketserver
from threading import Thread
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# --- Настройка порта для Render (Health Check) ---
def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    handler.log_message = lambda *args: None
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
        # Узнаем, где находится пользователь
        rev_url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=10&addressdetails=1"
        resp = requests.get(rev_url, headers={'User-Agent': 'GeoBot-App-v2'}).json()
        
        display_name = resp.get("display_name", "Joylashuv aniqlandi")

        bot.send_message(
            message.chat.id,
            f"📍 <b>Sizning joylashuvingiz:</b>\n{display_name}",
            parse_mode="HTML"
        )

        kb = InlineKeyboardMarkup()
        categories = {
            "🍴 Restoran": "restaurant",
            "💊 Dorixona": "pharmacy",
            "🏧 Bankomat": "atm",
            "⛽️ Yoqilg‘i": "fuel",
            "🛍 Do‘kon": "supermarket"
        }
        for k, v in categories.items():
            kb.add(InlineKeyboardButton(k, callback_data=f"{v}|{lat}|{lon}"))

        bot.send_message(message.chat.id, "Nima qidiramiz?", reply_markup=kb)
    except Exception as e:
        bot.send_message(message.chat.id, "Xatolik yuz berdi, iltimos qaytadan urinib ko'ring.")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        data = call.data.split("|")
        cat, lat, lon = data[0], float(data[1]), float(data[2])

        # Ограничиваем поиск квадратом ~30 км (0.25 градуса)
        delta = 0.25 
        viewbox = f"{lon-delta},{lat+delta},{lon+delta},{lat-delta}"

        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': cat,
            'format': 'json',
            'limit': 10,
            'viewbox': viewbox,
            'bounded': 1,  # СТРОГО внутри квадрата (никакой Мексики)
            'addressdetails': 1
        }

        resp = requests.get(url, headers={'User-Agent': 'GeoBot-App-v2'}, params=params).json()

        if not resp:
            bot.send_message(call.message.chat.id, "😕 Afsuski, 30 km radiusda hech narsa topilmadi.")
            return

        text = f"🗺 <b>{cat.capitalize()}lar (Yaqin atrofda):</b>\n\n"
        
        for place in resp:
            address = place.get('address', {})
            # Пытаемся найти нормальное название объекта
            name = address.get('name') or address.get('shop') or address.get('amenity') or place.get('display_name', '').split(',')[0]
            city = address.get('city') or address.get('town') or address.get('village') or ""
            
            plat, plon = place['lat'], place['lon']
            # Официальный формат ссылки Google Maps
            map_link = f"https://www.google.com/maps/search/?api=1&query={plat},{plon}"
            
            text += f"📍 <b>{name}</b> {f'({city})' if city else ''}\n"
            text += f"<a href='{map_link}'>Xaritada ko‘rish</a>\n\n"

        bot.send_message(call.message.chat.id, text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        bot.answer_callback_query(call.id, "Xatolik yuz berdi.")

# --- Запуск ---
if __name__ == "__main__":
    # Запускаем Health Check сервер для Render
    Thread(target=run_health_check_server, daemon=True).start()
    
    print("Бот запущен...")
    # Бесконечный цикл с защитой от вылетов
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=5)
        except Exception as e:
            print(f"Ошибка API: {e}")
            time.sleep(15)
