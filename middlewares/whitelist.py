"""
Разграничение доступа (п.2 ТЗ): проверка уникального Telegram ID пользователя
по белому списку. Запросы от незарегистрированных пользователей отклоняются
с уведомлением, до хендлеров они не доходят.
"""

from typing import Any, Awaitable, Callable, Dict, Union

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from config import WHITELIST

ACCESS_DENIED_TEXT = "⛔ Доступ запрещён. Ваш Telegram ID не найден в списке разрешённых пользователей."


class WhitelistMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any],
    ) -> Any:
        user = event.from_user
        if user is None or user.id not in WHITELIST:
            if isinstance(event, CallbackQuery):
                await event.answer(ACCESS_DENIED_TEXT, show_alert=True)
            else:
                await event.answer(ACCESS_DENIED_TEXT)
            return  # обработка прерывается, до хендлеров запрос не доходит
        return await handler(event, data)
