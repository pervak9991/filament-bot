"""
Слой работы с базой данных: PostgreSQL (Supabase) через asyncpg.

Хранит катушки пластика (п.3 ТЗ) плюс до 3 фото на катушку.
Подключение — через Supabase Session Pooler (порт 5432), подробности в DEPLOY.md.
"""

from typing import Optional

import asyncpg

from config import DATABASE_URL

_pool: Optional[asyncpg.Pool] = None


async def init_db() -> None:
    global _pool
    _pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=5,
        statement_cache_size=0,  # официальная рекомендация Supabase для работы через pooler
        ssl="require",
    )
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS spools (
                id SERIAL PRIMARY KEY,
                brand TEXT NOT NULL,
                plastic_type TEXT NOT NULL,
                color TEXT NOT NULL,
                weight_g REAL NOT NULL,
                nozzle_temp TEXT,
                bed_temp TEXT,
                price REAL,
                photo_file_ids TEXT[],
                added_by TEXT,
                created_at TIMESTAMPTZ DEFAULT now()
            )
            """
        )
        # На случай, если таблица уже существовала со старой схемой (один photo_file_id).
        await conn.execute("ALTER TABLE spools ADD COLUMN IF NOT EXISTS photo_file_ids TEXT[]")
        await conn.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'spools' AND column_name = 'photo_file_id'
                ) THEN
                    UPDATE spools
                    SET photo_file_ids = ARRAY[photo_file_id]
                    WHERE photo_file_id IS NOT NULL
                      AND (photo_file_ids IS NULL OR photo_file_ids = '{}');

                    ALTER TABLE spools DROP COLUMN photo_file_id;
                END IF;
            END $$;
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS operations_log (
                id SERIAL PRIMARY KEY,
                spool_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                performed_by TEXT,
                created_at TIMESTAMPTZ DEFAULT now()
            )
            """
        )


async def ping() -> bool:
    """Лёгкий запрос к БД. Используется health-check эндпоинтом (см. bot.py) —
    заодно не даёт Supabase приостановить проект от бездействия."""
    try:
        async with _pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception:
        return False


async def add_spool(
    brand: str,
    plastic_type: str,
    color: str,
    weight_g: float,
    nozzle_temp: Optional[str],
    bed_temp: Optional[str],
    price: Optional[float],
    photo_file_ids: Optional[list],
    added_by: str,
) -> int:
    async with _pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO spools
                (brand, plastic_type, color, weight_g, nozzle_temp, bed_temp,
                 price, photo_file_ids, added_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
            """,
            brand, plastic_type, color, weight_g, nozzle_temp, bed_temp,
            price, photo_file_ids or [], added_by,
        )


async def get_active_spools() -> list:
    """Катушки с ненулевым остатком (п.4.1 ТЗ). Сортировка — сначала заканчивающиеся."""
    async with _pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM spools WHERE weight_g > 0 ORDER BY weight_g ASC, id ASC")
        return [dict(row) for row in rows]


async def get_archived_spools() -> list:
    """Архив — катушки с нулевым остатком. Данные не удаляются: как только
    остаток снова становится больше 0 (например, после редактирования),
    катушка автоматически возвращается в активный список."""
    async with _pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM spools WHERE weight_g <= 0 ORDER BY id DESC")
        return [dict(row) for row in rows]


async def get_spool_by_id(spool_id: int) -> Optional[dict]:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM spools WHERE id = $1", spool_id)
        return dict(row) if row else None


async def update_spool_weight(spool_id: int, new_weight_g: float) -> None:
    async with _pool.acquire() as conn:
        await conn.execute(
            "UPDATE spools SET weight_g = $1 WHERE id = $2",
            max(new_weight_g, 0), spool_id,
        )


_EDITABLE_FIELDS = {
    "brand", "plastic_type", "color", "weight_g",
    "nozzle_temp", "bed_temp", "price", "photo_file_ids",
}


async def update_spool_field(spool_id: int, field: str, value) -> None:
    """Точечное обновление одного поля карточки (редактирование).
    field проверяется по белому списку — вызывается только из кода бота, не из ввода пользователя."""
    if field not in _EDITABLE_FIELDS:
        raise ValueError(f"Недопустимое поле для редактирования: {field}")
    async with _pool.acquire() as conn:
        await conn.execute(f"UPDATE spools SET {field} = $1 WHERE id = $2", value, spool_id)


async def _get_recent_distinct(column: str, limit: int = 8) -> list:
    """Недавно использованные значения колонки — для кнопок быстрого ввода.
    column задаётся только внутри кода (см. функции ниже), не из пользовательского ввода."""
    query = (
        f"SELECT {column} FROM spools WHERE {column} IS NOT NULL "
        f"GROUP BY {column} ORDER BY MAX(created_at) DESC LIMIT $1"
    )
    async with _pool.acquire() as conn:
        rows = await conn.fetch(query, limit)
        return [r[column] for r in rows]


async def get_recent_brands(limit: int = 8) -> list:
    return await _get_recent_distinct("brand", limit)


async def get_recent_materials(limit: int = 8) -> list:
    return await _get_recent_distinct("plastic_type", limit)


async def get_recent_colors(limit: int = 8) -> list:
    return await _get_recent_distinct("color", limit)


async def get_recent_nozzle_temps(limit: int = 8) -> list:
    return await _get_recent_distinct("nozzle_temp", limit)


async def get_recent_bed_temps(limit: int = 8) -> list:
    return await _get_recent_distinct("bed_temp", limit)


async def log_operation(spool_id: int, action: str, details: str, performed_by: str) -> None:
    """Запись в историю операций (добавление/списание/редактирование/импорт)."""
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO operations_log (spool_id, action, details, performed_by) VALUES ($1, $2, $3, $4)",
            spool_id, action, details, performed_by,
        )


async def get_spool_history(spool_id: int, limit: int = 10) -> list:
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM operations_log WHERE spool_id = $1 ORDER BY created_at DESC LIMIT $2",
            spool_id, limit,
        )
        return [dict(row) for row in rows]
