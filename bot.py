import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

import database as db
from config import BOT_TOKEN, DATABASE_URL, WHITELIST
from handlers import add_spool, calculate, common, edit_spool, export_excel, fallback, import_excel, view, writeoff
from middlewares.whitelist import WhitelistMiddleware


async def health(request: web.Request) -> web.Response:
    """
    Эндпоинт для UptimeRobot — не даёт Render усыпить free-сервис.
    Заодно делает лёгкий запрос к Supabase, чтобы не «уснула» и база.
    """
    db_ok = await db.ping()
    return web.Response(text="OK" if db_ok else "DB unavailable", status=200 if db_ok else 503)


async def start_web_server() -> None:
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Health-check сервер слушает порт {port}")


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан. Проверьте переменные окружения.")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL не задан. Проверьте переменные окружения.")
    if not WHITELIST:
        logging.warning("WHITELIST пуст — ни один пользователь не сможет пользоваться ботом.")

    await db.init_db()
    await start_web_server()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(WhitelistMiddleware())
    dp.callback_query.middleware(WhitelistMiddleware())

    # Порядок важен: common и import_excel — раньше сценариев (перехватывают
    # кнопки меню и присланные .xlsx независимо от текущего состояния),
    # fallback — последним (запасной обработчик).
    dp.include_router(common.router)
    dp.include_router(import_excel.router)
    dp.include_router(export_excel.router)
    dp.include_router(view.router)
    dp.include_router(add_spool.router)
    dp.include_router(writeoff.router)
    dp.include_router(calculate.router)
    dp.include_router(edit_spool.router)
    dp.include_router(fallback.router)

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
