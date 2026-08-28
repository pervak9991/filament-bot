"""
/start, /cancel и единая точка входа для всех 4 пунктов главного меню.

Обработчики пунктов меню намеренно собраны здесь, в первом регистрируемом
роутере, а не в файлах своих сценариев. Так нажатие любой кнопки меню
гарантированно перехватывается раньше хендлеров конкретного шага мастера
и сбрасывает текущий незавершённый ввод (п.5 ТЗ — изоляция сессий),
независимо от того, в каком состоянии сейчас находится пользователь.
"""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import keyboards as kb

from . import add_spool, calculate, view, writeoff

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Добро пожаловать в систему учёта 3D-пластика и расчёта себестоимости печати!\n\n"
        "Выберите действие в меню ниже.",
        reply_markup=kb.main_menu_kb(),
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=kb.main_menu_kb())


@router.message(F.text == kb.MENU_VIEW)
async def menu_view(message: Message, state: FSMContext):
    await state.clear()
    await view.show_spool_list(message)


@router.message(F.text == kb.MENU_ADD)
async def menu_add(message: Message, state: FSMContext):
    await state.clear()
    await add_spool.start_wizard(message, state)


@router.message(F.text == kb.MENU_WRITEOFF)
async def menu_writeoff(message: Message, state: FSMContext):
    await state.clear()
    await writeoff.start_writeoff(message, state)


@router.message(F.text == kb.MENU_CALC)
async def menu_calc(message: Message, state: FSMContext):
    await state.clear()
    await calculate.start_calc(message, state)
