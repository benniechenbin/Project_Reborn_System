from reborn_core.interfaces.streamlit.runtime import (
    CachedRebornApp,
    is_cached_app_valid,
    register_cached_app,
)


class FakeRebornApp:
    def __init__(self) -> None:
        self.started = True
        self.shutdown_calls = 0

    def shutdown(self) -> None:
        self.shutdown_calls += 1
        self.started = False


def test_cached_app_validation_keeps_matching_token_alive():
    app = FakeRebornApp()
    cached = CachedRebornApp(app=app, token="same")

    assert is_cached_app_valid(cached, token_factory=lambda: "same")
    assert app.shutdown_calls == 0


def test_cached_app_validation_closes_stale_token():
    app = FakeRebornApp()
    cached = CachedRebornApp(app=app, token="old")

    assert not is_cached_app_valid(cached, token_factory=lambda: "new")
    assert app.shutdown_calls == 1
    assert not app.started


def test_register_cached_app_closes_previous_active_app():
    first_app = FakeRebornApp()
    second_app = FakeRebornApp()
    first = CachedRebornApp(app=first_app, token="one")
    second = CachedRebornApp(app=second_app, token="two")

    register_cached_app(first)
    register_cached_app(second)

    assert first_app.shutdown_calls == 1
    assert second_app.shutdown_calls == 0
    second.shutdown()
