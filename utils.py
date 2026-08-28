from typing import Optional


def parse_float(text: str) -> Optional[float]:
    """
    Преобразует текст в число, поддерживая и точку, и запятую как разделитель
    дробной части (п.5 ТЗ — устойчивость к вводу данных).
    Возвращает None, если строка не является корректным числом.
    """
    if not text:
        return None
    cleaned = text.strip().replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None
