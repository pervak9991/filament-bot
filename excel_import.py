"""
Разбор Excel-файла для массового импорта катушек.

Ожидаемые заголовки колонок (регистр не важен, порядок колонок любой):
Бренд / Производитель / Марка — обязательно
Тип / Тип пластика / Материал — обязательно
Цвет — обязательно
Остаток / Вес / Масса (в граммах) — обязательно
Темп. сопла / Температура сопла / Сопло — необязательно
Темп. стола / Температура стола / Стол — необязательно
Цена / Стоимость — необязательно

Если заголовки в реальном файле называются иначе — можно прислать файл
и попросить подстроить список алиасов в COLUMN_ALIASES под него.
"""

from io import BytesIO

import openpyxl

REQUIRED_FIELDS = {"brand", "plastic_type", "color", "weight_g"}

COLUMN_ALIASES = {
    "brand": ["бренд", "производитель", "марка"],
    "plastic_type": ["тип", "тип пластика", "материал"],
    "color": ["цвет"],
    "weight_g": ["остаток", "остаток (г)", "остаток, г", "вес", "вес (г)", "масса", "масса (г)"],
    "nozzle_temp": ["темп. сопла", "температура сопла", "сопло"],
    "bed_temp": ["темп. стола", "температура стола", "стол"],
    "price": ["цена", "стоимость", "цена (руб)", "цена, руб"],
}


def _match_field(header: str):
    header_norm = header.strip().lower()
    for field, aliases in COLUMN_ALIASES.items():
        if header_norm in aliases:
            return field
    return None


def _to_float(value) -> "float | None":
    if value is None or value == "":
        return None
    try:
        return float(str(value).strip().replace(",", "."))
    except ValueError:
        return None


def parse_excel(file_bytes: bytes) -> tuple:
    """Возвращает (список строк-словарей готовых к вставке, список текстов ошибок)."""
    try:
        wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    except Exception:
        return [], ["Не удалось открыть файл — убедитесь, что это .xlsx"]

    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    header_row = next(rows_iter, None)
    if not header_row:
        return [], ["Файл пустой."]

    field_by_col = {}
    for idx, header in enumerate(header_row):
        if header is None:
            continue
        field = _match_field(str(header))
        if field:
            field_by_col[idx] = field

    missing = REQUIRED_FIELDS - set(field_by_col.values())
    if missing:
        return [], [
            "Не найдены обязательные колонки: " + ", ".join(sorted(missing)) + ". "
            "Ожидаются заголовки вроде: Бренд, Тип, Цвет, Остаток (г)."
        ]

    results = []
    errors = []
    for row_num, row in enumerate(rows_iter, start=2):
        if row is None or all(cell is None for cell in row):
            continue

        record = {}
        for idx, field in field_by_col.items():
            record[field] = row[idx] if idx < len(row) else None

        brand = str(record.get("brand") or "").strip()
        plastic_type = str(record.get("plastic_type") or "").strip()
        color = str(record.get("color") or "").strip()
        if not brand or not plastic_type or not color:
            errors.append(f"Строка {row_num}: пропущено обязательное текстовое поле")
            continue

        weight_g = _to_float(record.get("weight_g"))
        if weight_g is None or weight_g < 0:
            errors.append(f"Строка {row_num}: некорректный остаток")
            continue

        nozzle_temp = str(record["nozzle_temp"]).strip() if record.get("nozzle_temp") not in (None, "") else None
        bed_temp = str(record["bed_temp"]).strip() if record.get("bed_temp") not in (None, "") else None
        price = _to_float(record.get("price"))

        results.append({
            "brand": brand,
            "plastic_type": plastic_type,
            "color": color,
            "weight_g": weight_g,
            "nozzle_temp": nozzle_temp,
            "bed_temp": bed_temp,
            "price": price,
        })

    return results, errors
