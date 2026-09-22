from core.file_plan import (
    parse_file_plan,
    sanitize_file_plan,
    should_ask_file_plan,
    steps_from_file_plan,
)
from core.step_execution import current_write_target, mark_step_completed


def test_parse_json_and_junk_list():
    assert parse_file_plan('{"files":["shop.py","db.py","README.md","extra.py"]}') == [
        "shop.py",
        "db.py",
        "README.md",
        "extra.py",
    ]
    assert parse_file_plan("```json\n{\"files\": [\"app.py\"]}\n```") == ["app.py"]
    assert "main.py" in parse_file_plan('files: "main.py" and "utils.py"')


def test_sanitize_caps_to_three_and_drops_garbage():
    names = sanitize_file_plan(
        [
            "src/a.py",
            "src/b.py",
            "src/c.py",
            "src/d.py",
            "chat/secret.py",
            "C:/abs/x.py",
            "noext",
            "../hack.py",
        ],
        user_task="создай проект магазина",
    )
    assert names == ["src/a.py", "src/b.py", "src/c.py"]


def test_sanitize_fallback_and_rename_main():
    assert sanitize_file_plan([], user_task="создай калькулятор") == ["calculator.py"]
    assert sanitize_file_plan(["main.py"], user_task="создай змейку") == ["snake.py"]
    assert sanitize_file_plan(
        ["app.py"],
        user_task="создай змейку в /test",
        folder_hint="test",
    ) == ["test/snake.py"]


def test_folder_hint_from_slash_folder():
    from core.file_plan import folder_hint_for_plan

    assert folder_hint_for_plan("создай змейку в /test") == "test"
    assert folder_hint_for_plan("создай калькулятор") is None
    assert should_ask_file_plan("создай интернет-магазин") is True
    assert should_ask_file_plan("сделай сайт клуба", is_web=True) is False
    assert should_ask_file_plan("исправь calculator.py") is False
    assert should_ask_file_plan(
        "перепиши /calc.py",
        write_dest="calc.py",
    ) is False
    assert should_ask_file_plan("макет лендинга", persona_id="designer") is False
    assert should_ask_file_plan("создай 1 версию doom с игровым окном в /test22") is False


def test_steps_one_file_per_turn():
    steps = steps_from_file_plan(["shop.py", "db.py", "README.md"])
    assert [step.id for step in steps] == ["write_0", "write_1", "write_2"]
    assert current_write_target(steps, set()) == "shop.py"
    done = mark_step_completed(steps, set(), tool="write_file", path="shop.py", success=True)
    assert "write_0" in done
    assert current_write_target(steps, done) == "db.py"
    assert "list_directory" in steps[0].instruction
