"""Проверка условия «первый опрос после сброса»."""


def is_first_poll_window(*, watermark: int | None, last_polled_at) -> bool:
    return watermark is None and last_polled_at is None


def test_first_run_after_reset_ignores_seen_cache():
    assert is_first_poll_window(watermark=None, last_polled_at=None) is True


def test_not_first_run_when_watermark_set():
    assert is_first_poll_window(watermark=123, last_polled_at=None) is False


def test_not_first_run_when_last_polled_set():
    from datetime import UTC, datetime

    assert (
        is_first_poll_window(
            watermark=None,
            last_polled_at=datetime.now(UTC),
        )
        is False
    )
