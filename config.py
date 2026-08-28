import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

_raw_whitelist = os.getenv("WHITELIST", "")
WHITELIST = [
    int(uid.strip())
    for uid in _raw_whitelist.split(",")
    if uid.strip().lstrip("-").isdigit()
]

# Админы (подмножество WHITELIST) — только они могут редактировать карточки
# и управлять фото. Остальные из WHITELIST могут смотреть, добавлять,
# списывать, считать и выгружать экспорт, но не редактировать.
_raw_admin_ids = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [
    int(uid.strip())
    for uid in _raw_admin_ids.split(",")
    if uid.strip().lstrip("-").isdigit()
]

# Порог остатка (в граммах), при пересечении которого бот шлёт уведомление.
# Можно поменять без изменения кода — через переменную окружения на Render.
LOW_STOCK_THRESHOLD_G = float(os.getenv("LOW_STOCK_THRESHOLD_G", "500"))

# Базовая ставка (руб/кг), если у катушки не указана цена — используется и в
# расчёте себестоимости печати, и в сводке по складу (handlers/calculate.py, handlers/view.py).
BASE_RATE_PER_KG = float(os.getenv("BASE_RATE_PER_KG", "1500"))
