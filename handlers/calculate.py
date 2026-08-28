"""
Расчёт себестоимости 3D-печати (п.4.4 ТЗ).

Формулы взяты из ТЗ дословно:
- Пластик = Вес детали (г) * (Цена катушки / 1000); без цены — базовая ставка 1500 руб/кг.
- Электроэнергия = Время (ч) * 0.35 кВт * 7.0 руб/кВт*ч.
- Амортизация = Время (ч) * 30.0 руб/час.
"""

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
import keyboards as kb
from config import BASE_RATE_PER_KG, LOW_STOCK_THRESHOLD_G
from notifications import check_low_stock
from states import CalculateStates
from utils import parse_float

router = Router()

POWER_KW = 0.35              # мощность принтера, кВт
ELECTRICITY_RATE = 7.0       # руб/кВт*ч
DEPRECIATION_RATE = 30.0     # руб/час


async def start_calc(message: Message, state: FSMContext):
    spools = await db.get_active_spools()
    if not spools:
        await message.answer("Нет активных катушек для расчёта.")
        return
    await state.set_state(CalculateStates.choosing_spool)
    await message.answer(
        "Выберите катушку кнопкой или введите её ID текстом:",
        reply_markup=kb.spool_list_kb(spools, "cas", low_stock_threshold=LOW_STOCK_THRESHOLD_G),
    )


@router.callback_query(CalculateStates.choosing_spool, F.data.startswith("cas:"))
async def choose_by_button(callback: CallbackQuery, state: FSMContext):
    spool_id = int(callback.data.split(":", 1)[1])
    await _select(callback.message, state, spool_id)
    await callback.answer()


@router.callback_query(F.data.startswith("qc:"))
async def quick_calc(callback: CallbackQuery, state: FSMContext):
    """Быстрый расчёт прямо с детальной карточки катушки — без повторного выбора."""
    spool_id = int(callback.data.split(":", 1)[1])
    await state.clear()
    await _select(callback.message, state, spool_id)
    await callback.answer()


@router.message(CalculateStates.choosing_spool)
async def choose_by_text(message: Message, state: FSMContext):
    raw = (message.text or "").strip().lstrip("#")
    if not raw.isdigit():
        await message.answer("⚠️ Введите корректный числовой ID катушки.")
        return
    await _select(message, state, int(raw))


async def _select(message: Message, state: FSMContext, spool_id: int):
    s = await db.get_spool_by_id(spool_id)
    if not s:
        await message.answer("⚠️ Катушка не найдена.")
        return
    await state.update_data(spool_id=spool_id)
    await state.set_state(CalculateStates.entering_weight)
    await message.answer(
        f"Катушка #{s['id']} ({s['brand']}, {s['color']})\n\n"
        f"Введите фактический вес готовой модели с учётом поддержек (в граммах):"
    )


@router.message(CalculateStates.entering_weight)
async def enter_weight(message: Message, state: FSMContext):
    weight = parse_float(message.text or "")
    if weight is None or weight <= 0:
        await message.answer("⚠️ Введите корректное положительное число.")
        return
    await state.update_data(model_weight=weight)
    await state.set_state(CalculateStates.entering_time)
    await message.answer(
        f"Вес модели: <b>{weight:.0f} г</b>\n\nВведите продолжительность печати (в часах, например: 3.5):"
    )


@router.message(CalculateStates.entering_time)
async def enter_time(message: Message, state: FSMContext):
    hours = parse_float(message.text or "")
    if hours is None or hours <= 0:
        await message.answer("⚠️ Введите корректное положительное число часов.")
        return

    data = await state.get_data()
    s = await db.get_spool_by_id(data["spool_id"])
    if not s:
        await message.answer("⚠️ Катушка больше не найдена.")
        await state.clear()
        return

    model_weight = data["model_weight"]
    price_basis = s["price"] if s["price"] is not None else BASE_RATE_PER_KG
    plastic_cost = model_weight * (price_basis / 1000)
    electricity_cost = hours * POWER_KW * ELECTRICITY_RATE
    depreciation_cost = hours * DEPRECIATION_RATE
    total_cost = plastic_cost + electricity_cost + depreciation_cost

    await state.clear()

    text = (
        f"<b>📊 Расчёт себестоимости — катушка #{s['id']}</b>\n"
        f"{s['brand']}, {s['plastic_type']}, {s['color']}\n\n"
        f"Вес модели: {model_weight:.0f} г · Время печати: {hours:g} ч\n\n"
        f"Пластик: {plastic_cost:.2f} руб.\n"
        f"Электроэнергия: {electricity_cost:.2f} руб.\n"
        f"Амортизация оборудования: {depreciation_cost:.2f} руб.\n\n"
        f"<b>Итого: {total_cost:.2f} руб.</b>"
    )

    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"📦 Списать {model_weight:.0f} г с катушки #{s['id']}",
        callback_data=f"caw:{s['id']}:{model_weight:.2f}",
    )
    await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("caw:"))
async def writeoff_from_calc(callback: CallbackQuery, bot: Bot):
    _, spool_id_str, mass_str = callback.data.split(":")
    spool_id, mass = int(spool_id_str), float(mass_str)

    s = await db.get_spool_by_id(spool_id)
    if not s:
        await callback.answer("Катушка не найдена.", show_alert=True)
        return
    if mass > s["weight_g"]:
        await callback.answer(f"Недостаточно остатка: {s['weight_g']:.0f} г.", show_alert=True)
        return

    old_weight = s["weight_g"]
    new_weight = old_weight - mass
    await db.update_spool_weight(spool_id, new_weight)
    await db.log_operation(
        spool_id, "writeoff",
        f"Списано {mass:.0f} г через расчёт себестоимости ({old_weight:.0f} → {new_weight:.0f} г)",
        callback.from_user.username or callback.from_user.full_name,
    )
    await check_low_stock(bot, s, old_weight, new_weight)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"✅ Списано <b>{mass:.0f} г</b> с катушки #{spool_id}.\nНовый остаток: <b>{new_weight:.0f} г</b>"
    )
    await callback.answer("Списано ✅")
