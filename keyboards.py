from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Следующий матч")],
            [KeyboardButton(text="Сегодня"), KeyboardButton(text="Завтра")],
            [KeyboardButton(text="7 дней"), KeyboardButton(text="Меню")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие",
    )


def nav_inline_keyboard(reminders_enabled: bool | None = None) -> InlineKeyboardMarkup:
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
                InlineKeyboardButton(text="Меню", callback_data="nav:menu"),
            ],
        ]
    )


def match_inline_keyboard(
    fixture_id: int,
    reminders_enabled: bool | None = None,
    has_prediction: bool = False,
    has_note: bool = False,
    has_post_thoughts: bool = False,
) -> InlineKeyboardMarkup:
    prediction_label = "Изменить прогноз" if has_prediction else "Сделать прогноз"
    expectation_label = "Изменить ожидания" if has_note else "Ожидания от матча"
    thoughts_label = "Изменить мысли" if has_post_thoughts else "Мысли после матча"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=prediction_label, callback_data=f"match:prediction:{fixture_id}"),
                InlineKeyboardButton(text=expectation_label, callback_data=f"match:note:{fixture_id}"),
            ],
            [
                InlineKeyboardButton(text=thoughts_label, callback_data=f"match:post_thoughts:{fixture_id}"),
                InlineKeyboardButton(text="Показать мои данные", callback_data=f"match:show:{fixture_id}"),
            ],
            [
                InlineKeyboardButton(text="Сегодня", callback_data="nav:today"),
                InlineKeyboardButton(text="Следующий", callback_data="nav:next"),
            ],
            [
                InlineKeyboardButton(text="Меню", callback_data="nav:menu"),
            ],
        ]
    )


def match_list_keyboard(rows, tz, reminders_enabled: bool | None = None) -> InlineKeyboardMarkup:
    inline_keyboard = []

    for row in rows:
        kickoff = row["kickoff_utc"].astimezone(tz)
        button_text = (
            f"{kickoff.strftime('%d.%m %H:%M')} · "
            f"{row['home_team']} — {row['away_team']}"
        )

        if len(button_text) > 60:
            button_text = button_text[:57].rstrip() + "..."

        inline_keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"open_match:{row['fixture_id']}",
            )
        ])

    inline_keyboard.extend([
        [
            InlineKeyboardButton(text="Следующий", callback_data="nav:next"),
            InlineKeyboardButton(text="Меню", callback_data="nav:menu"),
        ],
    ])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
