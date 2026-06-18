from __future__ import annotations

import asyncio


class PollCancelRegistry:
    def __init__(self) -> None:
        self._events: dict[int, asyncio.Event] = {}

    def start(self, user_id: int) -> None:
        self._events[user_id] = asyncio.Event()

    def is_active(self, user_id: int) -> bool:
        return user_id in self._events

    def is_cancelled(self, user_id: int) -> bool:
        event = self._events.get(user_id)
        return event is not None and event.is_set()

    def request_cancel(self, user_id: int) -> bool:
        event = self._events.get(user_id)
        if event is None:
            return False
        event.set()
        return True

    def clear(self, user_id: int) -> None:
        self._events.pop(user_id, None)


poll_cancel = PollCancelRegistry()
