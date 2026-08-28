"""Ручное списание пластика (п.4.3 ТЗ)."""

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
import keyboards as kb
from config import LOW_STOCK_THRESHOLD_G
from notifications import check_low_stock
from states import WriteoffStates
from utils import parse_float

router = Router()


async def start_writeoff(message: Message, state: FSMContext):
    spools = await db.get_active_spools()
    if not spools:
        await message.answer("Нет катушек с ненулевым остатком для списания.")
        return
    await state.set_state(WriteoffStates.choosing_spool)
    await message.answer(
        "Выберите катушку кнопкой или введите её ID текстом:",
        reply_markup=kb.spool_list_kb(spools, "wos", low_stock_threshold=LOW_STOCK_THRESHOLD_G),
    )


@router.callback_query(WriteoffStates.choosing_spool, F.data.startswith("wos:"))
async def choose_by_button(callback: CallbackQuery, state: FSMContext):
    spool_id = int(callback.data.split(":", 1)[1])
    await _select(callback.message, state, spool_id)
    await callback.answer()


@router.callback_query(F.data.startswith("qw:"))
async def quick_writeoff(callback: CallbackQuery, state: FSMContext):
    """Быстрое списание прямо с детальной карточки катушки — без повторного выбора."""
    spool_id = int(callback.data.split(":", 1)[1])
    await state.clear()
    await _select(callback.message, state, spool_id)
    await callback.answer()


@router.message(WriteoffStates.choosing_spool)
async def choose_by_text(message: Message, state: FSMContext):
    raw = (message.text or "").strip().lstrip("#")
    if not raw.isdigit():
        await message.answer("⚠️ Введите корректный числовой ID катушки.")
        return
    await _select(message, state, int(raw))


async def _select(message: Message, state: FSMContext, spool_id: int):
    s = await db.get_spool_by_id(spool_id)
    if not s or s["weight_g"] <= 0:
        await message.answer("⚠️ Катушка не найдена или остаток уже нулевой.")
        return
    await state.update_data(spool_id=spool_id)
    await state.set_state(WriteoffStates.entering_mass)
    await message.answer(
        f"Катушка #{s['id']} ({s['brand']}, {s['color']})\n"
        f"Текущий остаток: <b>{s['weight_g']:.0f} г</b>\n\n"
        f"Введите массу для списания (в граммах):"
    )


@router.message(WriteoffStates.entering_mass)
async def enter_mass(message: Message, state: FSMContext, bot: Bot):
    mass = parse_float(message.text or "")
    if mass is None or mass <= 0:
        await message.answer("⚠️ Введите корректное положительное число.")
        return

    data = await state.get_data()
    s = await db.get_spool_by_id(data["spool_id"])
    if not s:
        await message.answer("⚠️ Катушка больше не найдена.")
        await state.clear()
        return
    if mass > s["weight_g"]:
        await message.answer(
            f"⚠️ Списываемая масса ({mass:.0f} г) превышает остаток ({s['weight_g']:.0f} г). "
            f"Введите значение не больше остатка."
        )
        return

    old_weight = s["weight_g"]
    new_weight = old_weight - mass
    await db.update_spool_weight(s["id"], new_weight)
    await db.log_operation(
        s["id"], "writeoff",
        f"Списано {mass:.0f} г ({old_weight:.0f} → {new_weight:.0f} г)",
        message.from_user.username or message.from_user.full_name,
    )
    await check_low_stock(bot, s, old_weight, new_weight)
    await state.clear()
    await message.answer(
        f"✅ Списано <b>{mass:.0f} г</b> с катушки #{s['id']}.\nНовый остаток: <b>{new_weight:.0f} г</b>",
        reply_markup=kb.main_menu_kb(),
    )
