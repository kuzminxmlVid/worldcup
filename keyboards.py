from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Сегодня"), KeyboardButton(text="Завтра")],
            [KeyboardButton(text="Следующий матч"), KeyboardButton(text="7 дней")],
            [KeyboardButton(text="Обновить"), KeyboardButton(text="Меню")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие",
    )


def nav_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня", callback_data="nav:today"),
                InlineKeyboardButton(text="Завтра", callback_data="nav:tomorrow"),
            ],
            [
                InlineKeyboardButton(text="Следующий", callback_data="nav:next"),
                InlineKeyboardButton(text="7 дней", callback_data="nav:week"),
            ],
            [
                InlineKeyboardButton(text="Обновить", callback_data="nav:sync"),
                InlineKeyboardButton(text="Меню", callback_data="nav:menu"),
            ],
        ]
    )
