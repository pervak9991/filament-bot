"""
Импорт катушек из Excel-файла — срабатывает на присланный .xlsx документ,
в любой момент (прерывает текущий незавершённый сценарий, как и кнопки меню).
Формат ожидаемых колонок и их синонимы — см. excel_import.py.
"""

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
import keyboards as kb
from excel_import import parse_excel
from states import ImportStates

router = Router()


@router.message(F.document)
async def handle_document(message: Message, state: FSMContext, bot: Bot):
    filename = message.document.file_name or ""
    if not filename.lower().endswith((".xlsx", ".xls")):
        return  # не Excel — не наш случай, дальше решит запасной обработчик

    await state.clear()

    tg_file = await bot.get_file(message.document.file_id)
    file_io = await bot.download_file(tg_file.file_path)
    rows, errors = parse_excel(file_io.read())

    if not rows:
        error_text = "\n".join(errors) if errors else "В файле не найдено ни одной подходящей строки."
        await message.answer("⚠️ " + error_text)
        return

    await state.set_state(ImportStates.confirming)
    await state.update_data(import_rows=rows)

    preview = "\n".join(
        f"• {r['brand']} {r['plastic_type']} {r['color']} — {r['weight_g']:.0f} г"
        for r in rows[:5]
    )
    more = f"\n… и ещё {len(rows) - 5}" if len(rows) > 5 else ""
    error_note = f"\n\n⚠️ Пропущено строк с ошибками: {len(errors)}" if errors else ""

    builder = InlineKeyboardBuilder()
    builder.button(text=f"✅ Импортировать {len(rows)}", callback_data="imp:confirm")
    builder.button(text="❌ Отмена", callback_data="imp:cancel")
    builder.adjust(1)
    await message.answer(
        f"Найдено катушек для импорта: <b>{len(rows)}</b>\n\n{preview}{more}{error_note}\n\n"
        f"Фото при импорте не добавляются — их можно будет прикрепить позже через "
        f"«Остатки» → карточка → «Редактировать» → «Фото».\n\nИмпортировать?",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(ImportStates.confirming, F.data == "imp:confirm")
async def confirm_import(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    rows = data.get("import_rows", [])
    user = callback.from_user

    added = 0
    for r in rows:
        spool_id = await db.add_spool(
            brand=r["brand"],
            plastic_type=r["plastic_type"],
            color=r["color"],
            weight_g=r["weight_g"],
            nozzle_temp=r["nozzle_temp"],
            bed_temp=r["bed_temp"],
            price=r["price"],
            photo_file_ids=[],
            added_by=user.username or user.full_name,
        )
        await db.log_operation(
            spool_id, "import",
            f"Импортирована из Excel: {r['weight_g']:.0f} г",
            user.username or user.full_name,
        )
        added += 1

    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"✅ Импортировано катушек: <b>{added}</b>.",
        reply_markup=kb.main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(ImportStates.confirming, F.data == "imp:cancel")
async def cancel_import(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Импорт отменён.", reply_markup=kb.main_menu_kb())
    await callback.answer()
