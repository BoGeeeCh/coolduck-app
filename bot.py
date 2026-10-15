import logging
import asyncio
import json
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiohttp import web
import aiohttp_cors
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import os

# =====================================================================
API_TOKEN = '8601853589:AAEQZ72TGc-XW4XqKqLVbs-lJffgLZ9IcgY'
WEB_APP_URL = 'https://bogeeech.github.io/coolduck-app/'
ADMIN_USERNAME = 'Blabad'
PORT = 8080
# =====================================================================

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            nickname TEXT,
            username TEXT,
            coins INTEGER DEFAULT 300,
            rigged_color TEXT DEFAULT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Начисление +250 коинов по расписанию
async def give_scheduled_coins():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET coins = coins + 250')
    conn.commit()
    conn.close()
    logging.info("⏰ Начислено +250 DealDuck_coin всем пользователям!")

SCHEDULED_TIMES = [
    (9, 40), (10, 30), (11, 30), (12, 30), (13, 20), (14, 20), (15, 20)
]

for hour, minute in SCHEDULED_TIMES:
    scheduler.add_job(
        give_scheduled_coins,
        CronTrigger(hour=hour, minute=minute, timezone="Europe/Moscow")
    )

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Открыть DealDuck Club", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])
    await message.answer("Привет! Нажмите кнопку ниже для запуска DealDuck Club.", reply_markup=kb)

# --- HTTP API ДЛЯ МНОГОПОЛЬЗОВАТЕЛЬСКОЙ СИНХРОНИЗАЦИИ ---

async def handle_get_users(request):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, nickname, username, coins FROM users')
    rows = cursor.fetchall()
    conn.close()

    users_list = []
    for r in rows:
        users_list.append({
            "id": r[0],
            "name": r[1] or r[2] or "Игрок",
            "username": r[2] or "",
            "coins": r[3]
        })
    return web.json_response({"status": "ok", "users": users_list})

async def handle_register(request):
    data = await request.json()
    user_id = data.get("user_id")
    nickname = data.get("nickname")
    username = data.get("username", "")

    if not user_id or not nickname:
        return web.json_response({"status": "error", "message": "Invalid data"}, status=400)

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, nickname, username, coins)
        VALUES (?, ?, ?, 300)
        ON CONFLICT(user_id) DO UPDATE SET nickname = excluded.nickname, username = excluded.username
    ''', (user_id, nickname, username))
    conn.commit()
    conn.close()

    return web.json_response({"status": "ok"})

async def handle_admin_set_coins(request):
    data = await request.json()
    admin_user = data.get("admin_username", "").strip().lower()
    target_user = data.get("target_username", "").replace("@", "").strip().lower()
    new_coins = data.get("new_coins")

    if admin_user != ADMIN_USERNAME.lower():
        return web.json_response({"status": "error", "message": "Access denied"}, status=403)

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET coins = ? WHERE LOWER(username) = ?', (new_coins, target_user))
    updated_rows = cursor.rowcount
    conn.commit()
    conn.close()

    if updated_rows == 0:
        return web.json_response({"status": "error", "message": "User not found"}, status=404)

    return web.json_response({"status": "ok"})

async def handle_delete_user(request):
    data = await request.json()
    admin_user = data.get("admin_username", "")
    target_id = data.get("target_id")

    if admin_user.lower() != ADMIN_USERNAME.lower():
        return web.json_response({"status": "error", "message": "Access denied"}, status=403)

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE user_id = ?', (target_id,))
    conn.commit()
    conn.close()

    return web.json_response({"status": "ok"})

def setup_app():
    app = web.Application()
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*"
        )
    })

    r1 = app.router.add_get('/api/users', handle_get_users)
    r2 = app.router.add_post('/api/register', handle_register)
    r3 = app.router.add_post('/api/admin/set-coins', handle_admin_set_coins)
    r4 = app.router.add_post('/api/admin/delete-user', handle_delete_user)

    cors.add(r1)
    cors.add(r2)
    cors.add(r3)
    cors.add(r4)

    return app

async def main():
    logging.basicConfig(level=logging.INFO)
    scheduler.start()
    
    app = setup_app()
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render передает порт через системную переменную PORT
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"API Сервер запущен на порту {port}")
    
    # Убираем dp.start_polling(bot), так как работает aiohttp сервер!
    # Если боту нужно отправлять сообщения по расписанию, он может делать это через бота без start_polling.

    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())

if __name__ == '__main__':
    asyncio.run(main())