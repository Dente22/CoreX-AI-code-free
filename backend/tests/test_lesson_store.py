from core.lesson_store import (
    format_lessons_for_prompt,
    remember_task_outcome,
    similar_lessons,
)


def test_remember_and_retrieve(tmp_path):
    store = tmp_path / "lessons.json"
    remember_task_outcome(
        task="создай калькулятор с окном",
        ok=True,
        how="gui_template",
        files=["calculator.py"],
        path=store,
    )
    remember_task_outcome(
        task="создай калькулятор с окном",
        ok=False,
        how="syntax_loop",
        files=["calculator.py"],
        error="Blocked done attempt",
        path=store,
    )
    hits = similar_lessons("сделай калькулятор в окне tkinter", path=store)
    assert hits
    assert hits[0]["ok"] is True
    prompt = format_lessons_for_prompt("калькулятор с окном", path=store)
    assert "calculator.py" in prompt
    assert prompt.startswith("Lessons")


def test_skip_hello_and_dedupe(tmp_path):
    store = tmp_path / "lessons.json"
    assert remember_task_outcome(task="привет", ok=True, how="chat", path=store) is None
    first = remember_task_outcome(
        task="создай змейку",
        ok=True,
        how="model",
        files=["snake.py"],
        path=store,
    )
    second = remember_task_outcome(
        task="создай змейку",
        ok=True,
        how="model",
        files=["snake.py"],
        path=store,
    )
    assert first is not None
    assert second == first
    data = store.read_text(encoding="utf-8")
    assert data.count("snake.py") == 1


def test_lessons_path_env(tmp_path, monkeypatch):
    store = tmp_path / "custom-lessons.json"
    monkeypatch.setenv("COREX_LESSONS_PATH", str(store))
    from core.lesson_store import resolve_lessons_path

    assert resolve_lessons_path() == store.resolve()


def test_prompt_stays_compact(tmp_path):
    store = tmp_path / "lessons.json"
    remember_task_outcome(
        task="создай калькулятор с окном и кнопками и историей",
        ok=False,
        how="syntax_loop",
        files=["calculator.py"],
        error="Blocked done attempt 2/3 ```json unchanged",
        path=store,
    )
    prompt = format_lessons_for_prompt("калькулятор с окном", path=store)
    assert "Lessons" in prompt
    assert "```" not in prompt
    assert "import " not in prompt
    assert len(prompt) < 400
