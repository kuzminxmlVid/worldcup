from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Сегодня"), KeyboardButton(text="Завтра")],
            [KeyboardButton(text="7 дней"), KeyboardButton(text="Обновить")],
            [KeyboardButton(text="Источник"), KeyboardButton(text="Debug")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие",
    )
