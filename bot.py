import telebot
import requests
import os
import time
import http.server
import socketserver
from threading import Thread
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# --- 1. Настройка порта для Render (Health Check) ---
def run_health_check_server():
    # Render дает порт через переменную окружения PORT
    port = int(os.environ.get("PORT", 8080))
    handler = http.server.SimpleHTTPRequestHandler
    handler.log_message = lambda *args: None  # Чтобы не спамить логами
    with socketserver.TCPServer(("", port), handler) as httpd:
        httpd.serve_forever()

# --- 2. Инициализация бота ---
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
        # Узнаем адрес пользователя
        rev_url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14&addressdetails=1"
        resp = requests.get(rev_url, headers={'User-Agent': 'Uzbek_GeoBot_v4'}).json()
        
        display_name = resp.get("display_name", "Joylashuv aniqlandi")

        bot.send_message(
            message.chat.id,
            f"📍 <b>Sizning joylashuvingiz:</b>\n{display_name}",
            parse_mode="HTML"
        )

        kb = InlineKeyboardMarkup()
        # Категории поиска
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
        bot.send_message(message.chat.id, "Xatolik yuz berdi. Qayta urinib ko'ring.")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        data = call.data.split("|")
        cat, lat, lon = data[0], float(data[1]), float(data[2])

        # СТРОГАЯ РАМКА: ~35 км вокруг пользователя
        delta = 0.3 
        viewbox = f"{lon-delta},{lat+delta},{lon+delta},{lat-delta}"

        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': cat,
            'format': 'json',
            'limit': 10,
            'viewbox': viewbox,
            'bounded': 1,      # СТРОГО: Искать только внутри этой рамки
            'addressdetails': 1,
            'accept-language': 'uz,ru'
        }

        resp = requests.get(url, headers={'User-Agent': 'Uzbek_GeoBot_v4'}, params=params).json()

        if not resp:
            bot.send_message(call.message.chat.id, "😕 Afsuski, yaqin atrofda hech narsa topilmadi.")
            return

        text = f"🗺 <b>Yaqin atrofdagi {cat}lar:</b>\n\n"
        
        for place in resp:
            addr = place.get('address', {})
            # Берем самое адекватное имя объекта
            name = addr.get('name') or addr.get('shop') or addr.get('amenity') or place.get('display_name', '').split(',')[0]
            # Город или район
            village = addr.get('village') or addr.get('town') or addr.get('city') or ""
            
            plat, plon = place['lat'], place['lon']
            # Ссылка на Google Maps
            map_link = f"https://www.google.com/maps/search/?api=1&query={plat},{plon}"
            
            text += f"📍 <b>{name}</b> {f'({village})' if village else ''}\n"
            text += f"<a href='{map_link}'>Xaritada ko‘rish</a>\n\n"

        bot.send_message(call.message.chat.id, text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        bot.answer_callback_query(call.id, "Xatolik!")

# --- 3. Запуск ---
if __name__ == "__main__":
    # Поток для порта (чтобы Render не вырубал бота)
    Thread(target=run_health_check_server, daemon=True).start()
    
    print("Бот запущен...")
    # Бесконечный цикл работы
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=5)
        except Exception as e:
            print(f"Ошибка API: {e}")
            time.sleep(15)
