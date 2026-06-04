from reborn_core.lifecycle import lifespan


def execute_full_sync() -> dict[str, float | int | str | None]:
    with lifespan(show_startup_banner=False) as app:
        task_id = app.container.task_runner.submit("memory_sync", app.container.run_sync)
        return app.container.task_runner.result(task_id).as_dict()


if __name__ == "__main__":
    print(execute_full_sync())
