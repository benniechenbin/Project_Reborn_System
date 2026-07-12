from reborn_core.lifecycle import build_app


def test_lifecycle_is_authoritative_and_idempotent(test_settings):
    app = build_app(test_settings)

    assert not app.started
    assert app.start(show_startup_banner=False) is app
    assert app.started
    assert app.start(show_startup_banner=False) is app
    assert app.settings.resolved_db_path.exists()
    with app.container.database.get_connection() as conn:
        versions = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    assert versions == 4

    app.shutdown()
    assert not app.started
