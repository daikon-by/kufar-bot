from aiogram.fsm.state import State, StatesGroup


class AddGroupStates(StatesGroup):
    name = State()
    section_label = State()
    region_label = State()
    urls = State()


class AddGroupUrlStates(StatesGroup):
    url = State()


class AddMinusStates(StatesGroup):
    phrase = State()


class AddMinusFromListingStates(StatesGroup):
    phrase = State()


class EditMinusStates(StatesGroup):
    phrase = State()


class ScheduleStates(StatesGroup):
    run_times = State()
    weekdays = State()
