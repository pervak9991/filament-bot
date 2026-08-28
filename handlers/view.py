"""Просмотр и контроль остатков (п.4.1 ТЗ) + архив, сводка по складу, история операций."""

from aiogram import F, Router
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
import keyboards as kb
from config import ADMIN_IDS, BASE_RATE_PER_KG, LOW_STOCK_THRESHOLD_G

router = Router()


async def show_spool_list(message: Message):
    spools = await db.get_active_spools()
    markup = kb.spool_list_kb(
        spools, "view",
        low_stock_threshold=LOW_STOCK_THRESHOLD_G,
        show_archive_link=True,
        show_summary_link=True,
    )
    text = (
        "<b>Активные катушки на складе:</b>\nСначала заканчивающиеся. Нажмите на катушку, чтобы увидеть подробную карточку."
        if spools else
        "На складе нет катушек с ненулевым остатком."
    )
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "summary:show")
async def show_summary(callback: CallbackQuery):
    spools = await db.get_active_spools()
    if not spools:
        await callback.answer("На складе нет активных катушек.", show_alert=True)
        return

    total_weight = sum(s["weight_g"] for s in spools)
    total_value = 0.0
    by_type = {}
    for s in spools:
        price_basis = s["price"] if s["price"] is not None else BASE_RATE_PER_KG
        total_value += s["weight_g"] * (price_basis / 1000)
        by_type[s["plastic_type"]] = by_type.get(s["plastic_type"], 0) + s["weight_g"]

    breakdown = "\n".join(
        f"  {t}: {w:.0f} г" for t, w in sorted(by_type.items(), key=lambda x: -x[1])
    )
    text = (
        f"<b>📊 Сводка по складу</b>\n\n"
        f"Активных катушек: {len(spools)}\n"
        f"Общий остаток: <b>{total_weight:.0f} г</b> ({total_weight / 1000:.2f} кг)\n"
        f"Примерная стоимость остатков: <b>{total_value:.2f} руб.</b>\n"
        f"<i>(по цене катушки, а если не указана — по базовой ставке {BASE_RATE_PER_KG:.0f} руб/кг)</i>\n\n"
        f"<b>По типам пластика:</b>\n{breakdown}"
    )
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "archive:list")
async def show_archive_list(callback: CallbackQuery):
    spools = await db.get_archived_spools()
    if not spools:
        await callback.answer("Архив пуст — использованных катушек пока нет.", show_alert=True)
        return
    builder = InlineKeyboardBuilder()
    for s in spools:
        builder.button(
            text=f"🗑 #{s['id']} {s['brand']} {s['plastic_type']} {s['color']}",
            callback_data=f"view:{s['id']}",
        )
    builder.adjust(1)
    await callback.message.answer(
        "<b>Архив — использованные катушки:</b>\n"
        "Остаток 0 г, карточки сохранены. Откройте, чтобы посмотреть детали.",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("view:"))
async def view_spool_detail(callback: CallbackQuery):
    spool_id = int(callback.data.split(":", 1)[1])
    s = await db.get_spool_by_id(spool_id)
    if not s:
        await callback.answer("Катушка не найдена", show_alert=True)
        return

    price_text = f"{s['price']:.2f} руб." if s["price"] is not None else "не указана"
    if s["weight_g"] <= 0:
        status_mark = " 🗑 использована полностью"
    elif s["weight_g"] <= LOW_STOCK_THRESHOLD_G:
        status_mark = " ⚠️ мало!"
    else:
        status_mark = ""
    text = (
        f"<b>Катушка #{s['id']}</b>\n"
        f"Бренд: {s['brand']}\n"
        f"Тип пластика: {s['plastic_type']}\n"
        f"Цвет: {s['color']}\n"
        f"Остаток: <b>{s['weight_g']:.0f} г</b>{status_mark}\n"
        f"Температура сопла: {s['nozzle_temp'] or '—'}°C\n"
        f"Температура стола: {s['bed_temp'] or '—'}°C\n"
        f"Цена катушки: {price_text}\n"
        f"Добавил: {s['added_by'] or '—'}"
    )

    action_kb = InlineKeyboardBuilder()
    if s["weight_g"] > 0:
        action_kb.button(text="➖ Списать", callback_data=f"qw:{s['id']}")
        action_kb.button(text="🧮 Рассчитать", callback_data=f"qc:{s['id']}")
    if callback.from_user.id in ADMIN_IDS:
        action_kb.button(text="✏️ Редактировать", callback_data=f"edit:{s['id']}")
    action_kb.button(text="📜 История", callback_data=f"hist:{s['id']}")
    action_kb.adjust(2, 1, 1)
    markup = action_kb.as_markup()

    photos = s["photo_file_ids"] or []
    if not photos:
        await callback.message.answer(text, reply_markup=markup)
    elif len(photos) == 1:
        await callback.message.answer_photo(photo=photos[0], caption=text, reply_markup=markup)
    else:
        media = [
            InputMediaPhoto(media=fid, caption=text if i == 0 else None)
            for i, fid in enumerate(photos)
        ]
        await callback.message.answer_media_group(media)
        # send_media_group не поддерживает reply_markup — кнопки отдельным сообщением
        await callback.message.answer("Действия:", reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("hist:"))
async def show_history(callback: CallbackQuery):
    spool_id = int(callback.data.split(":", 1)[1])
    history = await db.get_spool_history(spool_id)
    if not history:
        await callback.answer("По этой катушке пока нет записей в истории.", show_alert=True)
        return
    lines = []
    for h in history:
        when = h["created_at"].strftime("%d.%m.%Y %H:%M")
        who = h["performed_by"] or "—"
        lines.append(f"• {when} — {h['details']} ({who})")
    text = f"<b>📜 История катушки #{spool_id}</b>\n\n" + "\n".join(lines)
    await callback.message.answer(text)
    await callback.answer()
