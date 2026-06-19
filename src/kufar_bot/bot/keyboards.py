from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

WEEKDAY_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="📁 Группы"), KeyboardButton(text="⛔ Минус-слова")],
        [KeyboardButton(text="⏰ Расписание"), KeyboardButton(text="⭐ Избранное")],
        [KeyboardButton(text="▶️ Опрос сейчас"), KeyboardButton(text="⏹ Остановить опрос")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="👥 Пользователи")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def groups_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить группу"), KeyboardButton(text="📋 Список групп")],
            [KeyboardButton(text="🔗 Мои ссылки"), KeyboardButton(text="◀️ Назад")],
        ],
        resize_keyboard=True,
    )


def minus_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить фразу"), KeyboardButton(text="📋 Список фраз")],
            [KeyboardButton(text="◀️ Назад")],
        ],
        resize_keyboard=True,
    )


def schedule_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🕐 Времена"), KeyboardButton(text="📅 Дни недели")],
            [KeyboardButton(text="✅ Вкл/Выкл расписание"), KeyboardButton(text="📋 Текущее")],
            [KeyboardButton(text="◀️ Назад")],
        ],
        resize_keyboard=True,
    )


def back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="◀️ Назад")]], resize_keyboard=True)


def group_actions(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Ссылки", callback_data=f"group:urls:{group_id}")],
            [InlineKeyboardButton(text="➕ Ссылка", callback_data=f"group:url:add:{group_id}")],
            [
                InlineKeyboardButton(
                    text="🔄 Сбросить опрос",
                    callback_data=f"group:reset_poll:{group_id}",
                ),
            ],
            [InlineKeyboardButton(text="🗑 Удалить группу", callback_data=f"group:del:{group_id}")],
        ]
    )


def group_urls_keyboard(group_id: int, urls) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, item in enumerate(urls, start=1):
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{idx}. 🔄 Сброс",
                    callback_data=f"group:url:reset:{item.id}:{group_id}",
                ),
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"group:url:del:{item.id}:{group_id}",
                ),
            ]
        )
    rows.append([InlineKeyboardButton(text="➕ Ссылка", callback_data=f"group:url:add:{group_id}")])
    rows.append(
        [
            InlineKeyboardButton(
                text="🔄 Сбросить опрос (вся группа)",
                callback_data=f"group:reset_poll:{group_id}",
            ),
        ]
    )
    rows.append([InlineKeyboardButton(text="🗑 Удалить группу", callback_data=f"group:del:{group_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def group_url_actions(url_id: int, group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Сбросить опрос",
                    callback_data=f"group:url:reset:{url_id}:{group_id}",
                ),
            ],
            [InlineKeyboardButton(text="🗑 Удалить ссылку", callback_data=f"group:url:del:{url_id}:{group_id}")],
        ]
    )


def minus_phrase_actions(phrase_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Изменить", callback_data=f"minus:edit:{phrase_id}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"minus:del:{phrase_id}"),
            ],
        ]
    )


def minus_suggest_keyboard(suggestions: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for idx, word in enumerate(suggestions):
        label = word if len(word) <= 24 else word[:21] + "…"
        row.append(InlineKeyboardButton(text=label, callback_data=f"minus:hint:{idx}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="↩️ К объявлению", callback_data="minus:back_listing")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="minus:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def minus_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Сохранить", callback_data="minus:save"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="minus:cancel"),
            ],
            [InlineKeyboardButton(text="↩️ К объявлению", callback_data="minus:back_listing")],
        ]
    )


def poll_stop_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏹ Остановить опрос", callback_data="poll:stop")],
        ]
    )


def weekday_keyboard(selected: set[int]) -> InlineKeyboardMarkup:
    row: list[InlineKeyboardButton] = []
    rows: list[list[InlineKeyboardButton]] = []
    for idx, label in enumerate(WEEKDAY_LABELS):
        mark = "✅" if idx in selected else "⬜"
        row.append(InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"sched:wd:{idx}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="💾 Сохранить дни", callback_data="sched:wd:save")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
