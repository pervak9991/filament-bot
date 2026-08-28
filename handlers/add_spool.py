"""
Добавление новой катушки — пошаговый мастер (п.4.2 ТЗ).

Быстрые кнопки на шагах бренда/типа/цвета/температур подтягивают недавно
использованные значения из базы (чем быстрее заполняете — тем актуальнее
подсказки). Если истории ещё нет — показываются стандартные варианты.
Каждый шаг также поддерживает ручной ввод текстом/числом.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
import keyboards as kb
from states import AddSpoolStates
from utils import parse_float

router = Router()

MAX_PHOTOS = 3

# Показываются, только пока в базе ещё нет истории по соответствующему полю.
DEFAULT_BRANDS = ["Bambu Lab", "eSUN", "REC", "Plexiwire", "Filamentarno", "U3Print"]
DEFAULT_MATERIALS = ["PLA", "PETG", "ABS", "ASA", "TPU", "PC"]
DEFAULT_COLORS = ["Чёрный", "Белый", "Серый", "Красный", "Синий", "Зелёный", "Жёлтый", "Оранжевый"]
DEFAULT_NOZZLE_TEMPS = ["190", "200", "210", "220", "230", "250"]
DEFAULT_BED_TEMPS = ["0", "50", "60", "70", "80", "100"]


async def start_wizard(message: Message, state: FSMContext):
    await state.set_state(AddSpoolStates.brand)
    brands = await db.get_recent_brands()
    await message.answer(
        "<b>Добавление новой катушки (шаг 1/8)</b>\nВыберите бренд:",
        reply_markup=kb.choices_kb(brands or DEFAULT_BRANDS, "asb"),
    )


# --- Бренд ---

@router.callback_query(AddSpoolStates.brand, F.data.startswith("asb:"))
async def brand_choice(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    if value == "manual":
        await callback.message.answer("Введите название бренда текстом:")
        await callback.answer()
        return
    await _set_brand(callback.message, state, value)
    await callback.answer()


@router.message(AddSpoolStates.brand)
async def brand_manual(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Введите название бренда текстом.")
        return
    await _set_brand(message, state, message.text.strip())


async def _set_brand(message: Message, state: FSMContext, value: str):
    await state.update_data(brand=value)
    await state.set_state(AddSpoolStates.plastic_type)
    materials = await db.get_recent_materials()
    await message.answer(
        f"Бренд: <b>{value}</b>\n\n<b>Шаг 2/8.</b> Выберите тип пластика:",
        reply_markup=kb.choices_kb(materials or DEFAULT_MATERIALS, "asm"),
    )


# --- Тип пластика ---

@router.callback_query(AddSpoolStates.plastic_type, F.data.startswith("asm:"))
async def material_choice(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    if value == "manual":
        await callback.message.answer("Введите тип пластика текстом (например, PLA+):")
        await callback.answer()
        return
    await _set_material(callback.message, state, value)
    await callback.answer()


@router.message(AddSpoolStates.plastic_type)
async def material_manual(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Введите тип пластика текстом.")
        return
    await _set_material(message, state, message.text.strip())


async def _set_material(message: Message, state: FSMContext, value: str):
    await state.update_data(plastic_type=value)
    await state.set_state(AddSpoolStates.color)
    colors = await db.get_recent_colors()
    await message.answer(
        f"Тип: <b>{value}</b>\n\n<b>Шаг 3/8.</b> Выберите цвет:",
        reply_markup=kb.choices_kb(colors or DEFAULT_COLORS, "asc"),
    )


# --- Цвет ---

@router.callback_query(AddSpoolStates.color, F.data.startswith("asc:"))
async def color_choice(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    if value == "manual":
        await callback.message.answer("Введите цвет текстом:")
        await callback.answer()
        return
    await _set_color(callback.message, state, value)
    await callback.answer()


@router.message(AddSpoolStates.color)
async def color_manual(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Введите цвет текстом.")
        return
    await _set_color(message, state, message.text.strip())


async def _set_color(message: Message, state: FSMContext, value: str):
    await state.update_data(color=value)
    await state.set_state(AddSpoolStates.weight)
    await message.answer(
        f"Цвет: <b>{value}</b>\n\n<b>Шаг 4/8.</b> Введите чистый вес пластика на катушке (в граммах):"
    )


# --- Вес ---

@router.message(AddSpoolStates.weight)
async def weight_input(message: Message, state: FSMContext):
    value = parse_float(message.text or "")
    if value is None or value <= 0:
        await message.answer("⚠️ Введите положительное число, например: 1000 или 750,5")
        return
    await state.update_data(weight_g=value)
    await state.set_state(AddSpoolStates.nozzle_temp)
    nozzle_temps = await db.get_recent_nozzle_temps()
    await message.answer(
        f"Вес: <b>{value:.0f} г</b>\n\n<b>Шаг 5/8.</b> Выберите температуру сопла (°C):",
        reply_markup=kb.choices_kb(nozzle_temps or DEFAULT_NOZZLE_TEMPS, "asn", columns=3),
    )


# --- Температура сопла ---

@router.callback_query(AddSpoolStates.nozzle_temp, F.data.startswith("asn:"))
async def nozzle_choice(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    if value == "manual":
        await callback.message.answer("Введите температуру сопла текстом (например: 200-210):")
        await callback.answer()
        return
    await _set_nozzle(callback.message, state, value)
    await callback.answer()


@router.message(AddSpoolStates.nozzle_temp)
async def nozzle_manual(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Введите температуру сопла текстом.")
        return
    await _set_nozzle(message, state, message.text.strip())


async def _set_nozzle(message: Message, state: FSMContext, value: str):
    await state.update_data(nozzle_temp=value)
    await state.set_state(AddSpoolStates.bed_temp)
    bed_temps = await db.get_recent_bed_temps()
    await message.answer(
        f"Темп. сопла: <b>{value}°C</b>\n\n<b>Шаг 6/8.</b> Выберите температуру стола (°C):",
        reply_markup=kb.choices_kb(bed_temps or DEFAULT_BED_TEMPS, "asd", columns=3),
    )


# --- Температура стола ---

@router.callback_query(AddSpoolStates.bed_temp, F.data.startswith("asd:"))
async def bed_choice(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    if value == "manual":
        await callback.message.answer("Введите температуру стола текстом:")
        await callback.answer()
        return
    await _set_bed(callback.message, state, value)
    await callback.answer()


@router.message(AddSpoolStates.bed_temp)
async def bed_manual(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("⚠️ Введите температуру стола текстом.")
        return
    await _set_bed(message, state, message.text.strip())


async def _set_bed(message: Message, state: FSMContext, value: str):
    await state.update_data(bed_temp=value)
    await state.set_state(AddSpoolStates.price)
    await message.answer(
        f"Темп. стола: <b>{value}°C</b>\n\n"
        f"<b>Шаг 7/8.</b> Введите стоимость катушки в рублях (необязательно):",
        reply_markup=kb.skip_kb("asp"),
    )


# --- Цена (опционально) ---

@router.callback_query(AddSpoolStates.price, F.data == "asp:skip")
async def price_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(price=None)
    await callback.answer()
    await _ask_photo(callback.message, state)


@router.message(AddSpoolStates.price)
async def price_input(message: Message, state: FSMContext):
    value = parse_float(message.text or "")
    if value is None or value < 0:
        await message.answer("⚠️ Введите число, например: 1990, или нажмите «Пропустить».")
        return
    await state.update_data(price=value)
    await _ask_photo(message, state)


async def _ask_photo(message: Message, state: FSMContext):
    await state.set_state(AddSpoolStates.photo)
    await state.update_data(photos=[])
    await message.answer(
        f"<b>Шаг 8/8.</b> Пришлите до {MAX_PHOTOS} фото катушки (можно пропустить):",
        reply_markup=kb.skip_kb("asf"),
    )


# --- Фото: до MAX_PHOTOS штук, опционально ---

@router.callback_query(AddSpoolStates.photo, F.data == "asf:skip")
async def photo_done(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _save(callback.message, state, callback.from_user)


@router.message(AddSpoolStates.photo, F.photo)
async def photo_input(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)

    if len(photos) >= MAX_PHOTOS:
        await message.answer(f"✅ Получено {MAX_PHOTOS}/{MAX_PHOTOS} фото — этого достаточно.")
        await _save(message, state, message.from_user)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text=f"✅ Готово ({len(photos)}/{MAX_PHOTOS})", callback_data="asf:skip")
    await message.answer(
        f"Фото {len(photos)}/{MAX_PHOTOS} добавлено. Пришлите ещё или нажмите «Готово».",
        reply_markup=builder.as_markup(),
    )


@router.message(AddSpoolStates.photo)
async def photo_invalid(message: Message, state: FSMContext):
    await message.answer("⚠️ Пришлите фотографию или нажмите «Пропустить»/«Готово».")


async def _save(message: Message, state: FSMContext, user):
    data = await state.get_data()
    spool_id = await db.add_spool(
        brand=data["brand"],
        plastic_type=data["plastic_type"],
        color=data["color"],
        weight_g=data["weight_g"],
        nozzle_temp=data.get("nozzle_temp"),
        bed_temp=data.get("bed_temp"),
        price=data.get("price"),
        photo_file_ids=data.get("photos", []),
        added_by=user.username or user.full_name,
    )
    await db.log_operation(
        spool_id, "add",
        f"Добавлена катушка: {data['weight_g']:.0f} г",
        user.username or user.full_name,
    )
    await state.clear()
    text = (
        f"✅ <b>Катушка #{spool_id} добавлена на склад!</b>\n\n"
        f"Бренд: {data['brand']}\n"
        f"Тип: {data['plastic_type']}\n"
        f"Цвет: {data['color']}\n"
        f"Вес: <b>{data['weight_g']:.0f} г</b>"
    )
    await message.answer(text, reply_markup=kb.main_menu_kb())
