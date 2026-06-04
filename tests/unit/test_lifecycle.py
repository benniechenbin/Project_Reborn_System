from reborn_core.lifecycle import build_app


def test_lifecycle_is_authoritative_and_idempotent(test_settings):
    app = build_app(test_settings)

    assert not app.started
    assert app.start(show_startup_banner=False) is app
    assert app.started
    assert app.start(show_startup_banner=False) is app
    assert app.settings.resolved_db_path.exists()

    app.shutdown()
    assert not app.started
