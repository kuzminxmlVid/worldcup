from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Следующий матч"), KeyboardButton(text="Поиск команды")],
            [KeyboardButton(text="Сегодня"), KeyboardButton(text="Завтра")],
            [KeyboardButton(text="7 дней"), KeyboardButton(text="Автопост")],
            [KeyboardButton(text="Обновить"), KeyboardButton(text="Меню")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие",
    )


def nav_inline_keyboard(reminders_enabled: bool | None = None) -> InlineKeyboardMarkup:
    alerts_label = "Автопост: вкл" if reminders_enabled else "Автопост: выкл"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня", callback_data="nav:today"),
                InlineKeyboardButton(text="Завтра", callback_data="nav:tomorrow"),
            ],
            [
                InlineKeyboardButton(text="Следующий", callback_data="nav:next"),
                InlineKeyboardButton(text="Поиск команды", callback_data="nav:team_search"),
            ],
            [
                InlineKeyboardButton(text="7 дней", callback_data="nav:week"),
                InlineKeyboardButton(text=alerts_label, callback_data="nav:alerts_toggle"),
            ],
            [
                InlineKeyboardButton(text="Обновить", callback_data="nav:sync"),
                InlineKeyboardButton(text="Меню", callback_data="nav:menu"),
            ],
        ]
    )


def match_inline_keyboard(
    fixture_id: int,
    reminders_enabled: bool | None = None,
    has_prediction: bool = False,
    has_note: bool = False,
) -> InlineKeyboardMarkup:
    alerts_label = "Автопост: вкл" if reminders_enabled else "Автопост: выкл"
    prediction_label = "Изменить прогноз" if has_prediction else "Сделать прогноз"
    note_label = "Изменить заметку" if has_note else "Добавить заметку"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=prediction_label, callback_data=f"match:prediction:{fixture_id}"),
                InlineKeyboardButton(text=note_label, callback_data=f"match:note:{fixture_id}"),
            ],
            [
                InlineKeyboardButton(text="Показать мои данные", callback_data=f"match:show:{fixture_id}"),
                InlineKeyboardButton(text="Очистить", callback_data=f"match:clear:{fixture_id}"),
            ],
            [
                InlineKeyboardButton(text="Сегодня", callback_data="nav:today"),
                InlineKeyboardButton(text="Следующий", callback_data="nav:next"),
            ],
            [
                InlineKeyboardButton(text="Поиск команды", callback_data="nav:team_search"),
                InlineKeyboardButton(text=alerts_label, callback_data="nav:alerts_toggle"),
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

        # Telegram кнопки лучше держать короткими.
        if len(button_text) > 60:
            button_text = button_text[:57].rstrip() + "..."

        inline_keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"open_match:{row['fixture_id']}",
            )
        ])

    alerts_label = "Автопост: вкл" if reminders_enabled else "Автопост: выкл"

    inline_keyboard.extend([
        [
            InlineKeyboardButton(text="Следующий", callback_data="nav:next"),
            InlineKeyboardButton(text="Поиск команды", callback_data="nav:team_search"),
        ],
        [
            InlineKeyboardButton(text=alerts_label, callback_data="nav:alerts_toggle"),
            InlineKeyboardButton(text="Меню", callback_data="nav:menu"),
        ],
    ])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
