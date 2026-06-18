from kufar_bot.services.poll_cancel import PollCancelRegistry


def test_poll_cancel_flow():
    registry = PollCancelRegistry()
    registry.start(1)
    assert registry.is_active(1)
    assert not registry.is_cancelled(1)
    assert registry.request_cancel(1)
    assert registry.is_cancelled(1)
    registry.clear(1)
    assert not registry.is_active(1)
    assert not registry.request_cancel(1)
