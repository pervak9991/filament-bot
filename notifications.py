"""Уведомление о низком остатке — рассылается всем пользователям из белого списка."""

import logging

from aiogram import Bot

from config import LOW_STOCK_THRESHOLD_G, WHITELIST


async def check_low_stock(bot: Bot, spool: dict, old_weight: float, new_weight: float) -> None:
    """
    Шлёт уведомление, только если остаток ТОЛЬКО ЧТО пересёк порог сверху вниз
    (был выше порога, стал равен ему или ниже) — чтобы не спамить при каждом
    следующем списании с уже низкой катушки.
    """
    if not (old_weight > LOW_STOCK_THRESHOLD_G >= new_weight):
        return

    text = (
        f"⚠️ <b>Мало пластика!</b>\n"
        f"Катушка #{spool['id']} ({spool['brand']}, {spool['plastic_type']}, {spool['color']})\n"
        f"Остаток: <b>{new_weight:.0f} г</b> (порог: {LOW_STOCK_THRESHOLD_G:.0f} г)"
    )
    for user_id in WHITELIST:
        try:
            await bot.send_message(user_id, text)
        except Exception:
            logging.warning(f"Не удалось отправить уведомление об остатке пользователю {user_id}")
