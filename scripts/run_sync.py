from reborn_core.lifecycle import lifespan


def execute_full_sync() -> dict[str, float | int | str | None]:
    with lifespan(show_startup_banner=False) as app:
        return app.container.run_sync().as_dict()


if __name__ == "__main__":
    print(execute_full_sync())
