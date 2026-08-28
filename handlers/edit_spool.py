"""Редактирование существующей карточки катушки — вход через кнопку в детальной карточке."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
import keyboards as kb
from config import ADMIN_IDS
from states import EditSpoolStates
from utils import parse_float

router = Router()

MAX_PHOTOS = 3

_FIELD_LABELS = {
    "brand": "Бренд",
    "material": "Тип пластика",
    "color": "Цвет",
    "weight": "Остаток (г)",
    "nozzle": "Темп. сопла",
    "bed": "Темп. стола",
    "price": "Цена",
}
_FIELD_TO_COLUMN = {
    "brand": "brand",
    "material": "plastic_type",
    "color": "color",
    "weight": "weight_g",
    "nozzle": "nozzle_temp",
    "bed": "bed_temp",
    "price": "price",
}
_FIELD_TO_STATE = {
    "brand": EditSpoolStates.editing_brand,
    "material": EditSpoolStates.editing_material,
    "color": EditSpoolStates.editing_color,
    "weight": EditSpoolStates.editing_weight,
    "nozzle": EditSpoolStates.editing_nozzle,
    "bed": EditSpoolStates.editing_bed,
    "price": EditSpoolStates.editing_price,
}
_FIELD_PROMPTS = {
    "brand": "Введите новый бренд:",
    "material": "Введите новый тип пластика:",
    "color": "Введите новый цвет:",
    "weight": "Введите новый остаток в граммах:",
    "nozzle": "Введите новую температуру сопла:",
    "bed": "Введите новую температуру стола:",
    "price": "Введите новую цену в рублях (или «-», чтобы очистить):",
}


def _field_menu_kb(spool_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for field, label in _FIELD_LABELS.items():
        builder.button(text=label, callback_data=f"ef:{field}:{spool_id}")
    builder.button(text="📷 Фото", callback_data=f"ef:photos:{spool_id}")
    builder.button(text="✅ Готово", callback_data=f"ef:done:{spool_id}")
    builder.adjust(2)
    return builder.as_markup()


@router.callback_query(F.data.startswith("edit:"))
async def start_edit(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Редактирование доступно только администраторам.", show_alert=True)
        return
    spool_id = int(callback.data.split(":", 1)[1])
    s = await db.get_spool_by_id(spool_id)
    if not s:
        await callback.answer("Катушка не найдена", show_alert=True)
        return
    await state.set_state(EditSpoolStates.choosing_field)
    await state.update_data(spool_id=spool_id)
    await callback.message.answer(
        f"<b>Редактирование катушки #{spool_id}</b>\nЧто изменить?",
        reply_markup=_field_menu_kb(spool_id),
    )
    await callback.answer()


@router.callback_query(EditSpoolStates.choosing_field, F.data.startswith("ef:"))
async def choose_field(callback: CallbackQuery, state: FSMContext):
    _, field, spool_id_str = callback.data.split(":")
    spool_id = int(spool_id_str)

    if field == "done":
        await state.clear()
        await callback.message.answer("Готово.", reply_markup=kb.main_menu_kb())
        await callback.answer()
        return

    if field == "photos":
        await _show_photos_menu(callback.message, state, spool_id)
        await callback.answer()
        return

    await state.set_state(_FIELD_TO_STATE[field])
    await callback.message.answer(_FIELD_PROMPTS[field])
    await callback.answer()


async def _save_field(message: Message, state: FSMContext, field_key: str, value) -> None:
    data = await state.get_data()
    spool_id = data["spool_id"]
    column = _FIELD_TO_COLUMN[field_key]

    old_spool = await db.get_spool_by_id(spool_id)
    old_value = old_spool[column] if old_spool else None

    await db.update_spool_field(spool_id, column, value)
    await db.log_operation(
        spool_id, "edit",
        f"{_FIELD_LABELS[field_key]}: {old_value} → {value}",
        message.from_user.username or message.from_user.full_name,
    )

    await state.set_state(EditSpoolStates.choosing_field)
    await message.answer("✅ Обновлено.\n\nЧто ещё изменить?", reply_markup=_field_menu_kb(spool_id))


@router.message(EditSpoolStates.editing_brand)
async def edit_brand(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Введите текст.")
        return
    await _save_field(message, state, "brand", message.text.strip())


@router.message(EditSpoolStates.editing_material)
async def edit_material(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Введите текст.")
        return
    await _save_field(message, state, "material", message.text.strip())


@router.message(EditSpoolStates.editing_color)
async def edit_color(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Введите текст.")
        return
    await _save_field(message, state, "color", message.text.strip())


@router.message(EditSpoolStates.editing_weight)
async def edit_weight(message: Message, state: FSMContext):
    value = parse_float(message.text or "")
    if value is None or value < 0:
        await message.answer("⚠️ Введите неотрицательное число.")
        return
    await _save_field(message, state, "weight", value)


@router.message(EditSpoolStates.editing_nozzle)
async def edit_nozzle(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Введите текст.")
        return
    await _save_field(message, state, "nozzle", message.text.strip())


@router.message(EditSpoolStates.editing_bed)
async def edit_bed(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Введите текст.")
        return
    await _save_field(message, state, "bed", message.text.strip())


@router.message(EditSpoolStates.editing_price)
async def edit_price(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text == "-":
        await _save_field(message, state, "price", None)
        return
    value = parse_float(text)
    if value is None or value < 0:
        await message.answer("⚠️ Введите неотрицательное число или «-», чтобы очистить.")
        return
    await _save_field(message, state, "price", value)


# --- Фото: добавить (до MAX_PHOTOS) или очистить все ---

async def _show_photos_menu(message: Message, state: FSMContext, spool_id: int):
    s = await db.get_spool_by_id(spool_id)
    count = len(s["photo_file_ids"] or [])
    builder = InlineKeyboardBuilder()
    if count < MAX_PHOTOS:
        builder.button(text="➕ Добавить фото", callback_data=f"efp:add:{spool_id}")
    if count > 0:
        builder.button(text="🗑 Очистить все фото", callback_data=f"efp:clear:{spool_id}")
    builder.button(text="◀️ Назад к полям", callback_data=f"efp:back:{spool_id}")
    builder.adjust(1)
    await state.set_state(EditSpoolStates.photos_menu)
    await state.update_data(spool_id=spool_id)
    await message.answer(f"Сейчас у катушки {count}/{MAX_PHOTOS} фото.", reply_markup=builder.as_markup())


@router.callback_query(EditSpoolStates.photos_menu, F.data.startswith("efp:"))
async def photos_menu_action(callback: CallbackQuery, state: FSMContext):
    _, action, spool_id_str = callback.data.split(":")
    spool_id = int(spool_id_str)
    await callback.answer()

    if action == "back":
        await state.set_state(EditSpoolStates.choosing_field)
        await callback.message.answer("Что ещё изменить?", reply_markup=_field_menu_kb(spool_id))
        return

    if action == "clear":
        await db.update_spool_field(spool_id, "photo_file_ids", [])
        await db.log_operation(
            spool_id, "edit", "Фото: очищены все",
            callback.from_user.username or callback.from_user.full_name,
        )
        await _show_photos_menu(callback.message, state, spool_id)
        return

    if action == "add":
        await state.set_state(EditSpoolStates.photos_input)
        await state.update_data(spool_id=spool_id)
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Готово", callback_data=f"efp:finish:{spool_id}")
        await callback.message.answer(
            f"Присылайте фото (всего не больше {MAX_PHOTOS}). Когда закончите — «Готово».",
            reply_markup=builder.as_markup(),
        )


@router.message(EditSpoolStates.photos_input, F.photo)
async def photos_add_one(message: Message, state: FSMContext):
    data = await state.get_data()
    spool_id = data["spool_id"]
    s = await db.get_spool_by_id(spool_id)
    photos = list(s["photo_file_ids"] or [])

    if len(photos) >= MAX_PHOTOS:
        await message.answer(f"Уже {MAX_PHOTOS}/{MAX_PHOTOS} — больше нельзя. Нажмите «Готово».")
        return

    photos.append(message.photo[-1].file_id)
    await db.update_spool_field(spool_id, "photo_file_ids", photos)
    await db.log_operation(
        spool_id, "edit", f"Фото: добавлено (всего {len(photos)}/{MAX_PHOTOS})",
        message.from_user.username or message.from_user.full_name,
    )

    if len(photos) >= MAX_PHOTOS:
        await message.answer(f"✅ Фото {MAX_PHOTOS}/{MAX_PHOTOS} — достигнут максимум.")
        await _show_photos_menu(message, state, spool_id)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Готово", callback_data=f"efp:finish:{spool_id}")
    await message.answer(f"Фото {len(photos)}/{MAX_PHOTOS} добавлено.", reply_markup=builder.as_markup())


@router.message(EditSpoolStates.photos_input)
async def photos_input_invalid(message: Message):
    await message.answer("⚠️ Пришлите фотографию или нажмите «Готово».")


@router.callback_query(EditSpoolStates.photos_input, F.data.startswith("efp:finish:"))
async def photos_finish(callback: CallbackQuery, state: FSMContext):
    spool_id = int(callback.data.split(":")[2])
    await callback.answer()
    await _show_photos_menu(callback.message, state, spool_id)
