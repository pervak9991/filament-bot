from aiogram.fsm.state import State, StatesGroup


class AddSpoolStates(StatesGroup):
    """Мастер добавления новой катушки (п.4.2 ТЗ)."""
    brand = State()
    plastic_type = State()
    color = State()
    weight = State()
    nozzle_temp = State()
    bed_temp = State()
    price = State()
    photo = State()


class WriteoffStates(StatesGroup):
    """Ручное списание (п.4.3 ТЗ)."""
    choosing_spool = State()
    entering_mass = State()


class CalculateStates(StatesGroup):
    """Расчёт себестоимости печати (п.4.4 ТЗ)."""
    choosing_spool = State()
    entering_weight = State()
    entering_time = State()


class EditSpoolStates(StatesGroup):
    """Редактирование существующей карточки катушки."""
    choosing_field = State()
    editing_brand = State()
    editing_material = State()
    editing_color = State()
    editing_weight = State()
    editing_nozzle = State()
    editing_bed = State()
    editing_price = State()
    photos_menu = State()
    photos_input = State()


class ImportStates(StatesGroup):
    """Импорт катушек из Excel-файла."""
    confirming = State()
