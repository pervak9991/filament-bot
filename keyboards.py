from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Названия пунктов главного меню (п.5 ТЗ: 4 базовые функции).
# Вынесены в константы, чтобы на них ссылались и клавиатура, и роутер команд.
MENU_VIEW = "📋 Остатки"
MENU_ADD = "➕ Добавить катушку"
MENU_WRITEOFF = "➖ Списание"
MENU_CALC = "🧮 Расчёт себестоимости"

ALL_MENU_TEXTS = {MENU_VIEW, MENU_ADD, MENU_WRITEOFF, MENU_CALC}


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Постоянное главное меню (п.5 ТЗ)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_VIEW), KeyboardButton(text=MENU_ADD)],
            [KeyboardButton(text=MENU_WRITEOFF), KeyboardButton(text=MENU_CALC)],
        ],
        resize_keyboard=True,
    )


def choices_kb(options: list, prefix: str, columns: int = 2) -> InlineKeyboardMarkup:
    """Быстрые кнопки + кнопка ручного ввода (используется в мастере добавления)."""
    builder = InlineKeyboardBuilder()
    for opt in options:
        builder.button(text=opt, callback_data=f"{prefix}:{opt}")
    builder.button(text="✏️ Ввести вручную", callback_data=f"{prefix}:manual")
    builder.adjust(columns)
    return builder.as_markup()


def skip_kb(prefix: str) -> InlineKeyboardMarkup:
    """Кнопка пропуска необязательного поля (цена, фото)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Пропустить", callback_data=f"{prefix}:skip")
    return builder.as_markup()


def spool_list_kb(
    spools: list,
    prefix: str,
    low_stock_threshold: float = None,
    show_archive_link: bool = False,
    show_summary_link: bool = False,
) -> InlineKeyboardMarkup:
    """Список катушек кнопками — краткая карточка: ID, бренд, тип, цвет, остаток (п.4.1).
    Если задан low_stock_threshold, катушки с остатком не выше него помечаются ⚠️.
    show_archive_link добавляет кнопку перехода в архив, show_summary_link — кнопку сводки по складу."""
    builder = InlineKeyboardBuilder()
    for s in spools:
        warn = "⚠️ " if low_stock_threshold is not None and s["weight_g"] <= low_stock_threshold else ""
        label = f"{warn}#{s['id']} {s['brand']} {s['plastic_type']} {s['color']} — {s['weight_g']:.0f} г"
        builder.button(text=label, callback_data=f"{prefix}:{s['id']}")
    if spools:
        builder.adjust(1)
    if show_summary_link:
        builder.button(text="📊 Сводка по складу", callback_data="summary:show")
        builder.adjust(1)
    if show_archive_link:
        builder.button(text="📦 Архив (использованные)", callback_data="archive:list")
        builder.adjust(1)
    return builder.as_markup()
