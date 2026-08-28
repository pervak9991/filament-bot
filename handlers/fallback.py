"""
Запасной обработчик. Регистрируется последним, поэтому срабатывает только
если ни один из предыдущих роутеров не подошёл — например, после перезапуска
бота посреди мастера (память состояний сбрасывается) или по устаревшей кнопке.
"""

from aiogram import Router
from aiogram.types import CallbackQuery, Message

import keyboards as kb

router = Router()


@router.message()
async def fallback_message(message: Message):
    await message.answer(
        "Не удалось распознать команду. Воспользуйтесь кнопками меню ниже.",
        reply_markup=kb.main_menu_kb(),
    )


@router.callback_query()
async def fallback_callback(callback: CallbackQuery):
    await callback.answer("Действие устарело. Начните заново через меню.", show_alert=True)
