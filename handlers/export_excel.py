"""
Экспорт всех катушек (активные + архив) в .xlsx по команде /export.

Формат колонок совпадает с тем, что понимает импорт (excel_import.py) —
это одновременно и отчёт для чтения, и резервная копия: при необходимости
данные можно будет перенести обратно через импорт. Фото не восстанавливаются
через импорт автоматически, но их file_id сохраняются в отдельной колонке
на случай ручного восстановления.
"""

from datetime import datetime
from io import BytesIO

import openpyxl
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

import database as db

router = Router()


@router.message(Command("export"))
async def export_spools(message: Message):
    active = await db.get_active_spools()
    archived = await db.get_archived_spools()
    all_spools = active + archived

    if not all_spools:
        await message.answer("В базе пока нет ни одной катушки — экспортировать нечего.")
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Катушки"
    ws.append([
        "ID", "Бренд", "Тип", "Цвет", "Остаток (г)",
        "Темп. сопла", "Темп. стола", "Цена", "Добавил", "Статус",
        "Фото (ID, для бэкапа)",
    ])
    for s in all_spools:
        status = "использована" if s["weight_g"] <= 0 else "активна"
        ws.append([
            s["id"], s["brand"], s["plastic_type"], s["color"], s["weight_g"],
            s["nozzle_temp"] or "", s["bed_temp"] or "",
            s["price"] if s["price"] is not None else "",
            s["added_by"] or "", status,
            ", ".join(s["photo_file_ids"] or []),
        ])
    for col in "ABCDEFGHIJK":
        ws.column_dimensions[col].width = 16

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"spools_export_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    await message.answer_document(
        BufferedInputFile(buf.read(), filename=filename),
        caption=(
            f"Экспорт склада: {len(all_spools)} катушек "
            f"({len(active)} активных, {len(archived)} в архиве)."
        ),
    )
