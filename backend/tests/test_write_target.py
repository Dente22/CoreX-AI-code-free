from pathlib import Path

from core.write_target import (
    classify_mention_kind,
    filename_has_extension,
    infer_task_write_path,
    mention_intent,
    mention_prompt_hint,
    remap_write_path,
    resolve_gui_fallback_path,
    suggest_created_filename,
)


def test_filename_requires_extension():
    assert filename_has_extension("snake.py") is True
    assert filename_has_extension("test1/minesweeper.py") is True
    assert filename_has_extension(".env") is True
    assert filename_has_extension("test") is False
    assert filename_has_extension("test1") is False
    assert filename_has_extension("readme.") is False


def test_suggest_filename_from_task():
    assert suggest_created_filename("создай змейку на питоне") == "snake.py"
    assert suggest_created_filename("напиши калькулятор") == "calculator.py"
    assert suggest_created_filename("создай телеграм бота") == "bot.py"
    assert suggest_created_filename("создай скрипт") == "script.py"
    assert suggest_created_filename("сделай игру") == "game.py"
    assert suggest_created_filename("сделай сайт-визитку") == "index.html"
    assert suggest_created_filename("напиши что-нибудь") == "app.py"
    assert suggest_created_filename("создай 1 версию doom с игровым окном") == "doom.py"


def test_slash_folder_gets_suggested_name_not_main():
    assert infer_task_write_path("создай змейку на питоне в /test1") == "test1/snake.py"
    assert infer_task_write_path("сделай игру в папке games") == "games/game.py"
    assert infer_task_write_path("create snake in /arcade/snake.py") == "arcade/snake.py"
    assert infer_task_write_path("создай змейку с игровым окном в /test`") == "test/snake.py"
    assert infer_task_write_path("создай змейку с игровым окном /test") == "test/snake.py"
    assert infer_task_write_path("создай телеграм бота /bots") == "bots/bot.py"
    assert infer_task_write_path("создай скрипт в /test") == "test/script.py"
    assert infer_task_write_path("создай 1 версию doom с игровым окном в /test22") == "test22/doom.py"


def test_create_without_path_uses_suggested_name():
    assert infer_task_write_path("создай змейку на питоне") == "snake.py"
    assert infer_task_write_path("напиши на python калькулятор") == "calculator.py"
    assert infer_task_write_path("добавь игровое окно") is None


def test_mention_read_does_not_set_write_path():
    assert mention_intent("что делает /main.py") == "read"
    assert infer_task_write_path("что делает /main.py") is None
    assert mention_intent("посмотри /utils.py") == "read"
    assert infer_task_write_path("посмотри /utils.py") is None
    hint = mention_prompt_hint("что делает /main.py", None)
    assert "READ" in hint
    assert "WRITE TO" not in hint


def test_mention_edit_targets_that_file():
    assert mention_intent("исправь /main.py") == "edit"
    assert infer_task_write_path("исправь /main.py") == "main.py"
    assert mention_intent("добавь функцию factorial в /utils.py") == "edit"
    assert infer_task_write_path("добавь функцию factorial в /utils.py") == "utils.py"
    hint = mention_prompt_hint("исправь /main.py", "main.py")
    assert "EDIT main.py" in hint


def test_mention_create_targets_folder_or_file():
    assert mention_intent("создай змейку /test") == "create"
    assert infer_task_write_path("создай змейку /test") == "test/snake.py"
    assert mention_intent("создай телеграм бота /bot.py") == "create"
    assert infer_task_write_path("создай телеграм бота /bot.py") == "bot.py"
    hint = mention_prompt_hint("создай змейку /test", "test/snake.py")
    assert "inside test/" in hint
    assert "main.py just because" in hint


def test_extensionless_path_is_always_a_folder(tmp_path: Path):
    (tmp_path / "test1").write_text("oops\n", encoding="utf-8")
    assert classify_mention_kind("test1", tmp_path) == "folder"
    assert infer_task_write_path("создай сапёра в /test1", tmp_path) == "test1/minesweeper.py"
    assert classify_mention_kind("missing", tmp_path) == "folder"
    assert infer_task_write_path("создай скрипт в /missing", tmp_path) == "missing/script.py"


def test_remap_honors_agent_name_inside_folder():
    assert remap_write_path(
        "main.py",
        "test1/snake.py",
        user_task="создай змейку /test1",
    ) == "test1/snake.py"
    assert remap_write_path(
        "snake.py",
        "test1/snake.py",
        user_task="создай змейку /test1",
    ) == "test1/snake.py"
    assert remap_write_path(
        "test1/game.py",
        "test1/snake.py",
        user_task="создай змейку /test1",
    ) == "test1/game.py"
    assert remap_write_path(
        "other/x.py",
        "test1/snake.py",
        user_task="создай змейку /test1",
    ) == "test1/x.py"
    assert remap_write_path(
        "test",
        "test/script.py",
        user_task="создай скрипт в /test",
    ) == "test/script.py"
    assert remap_write_path(
        "chat/project_memory.md",
        "test1/snake.py",
    ) == "chat/project_memory.md"
    assert remap_write_path("main.py", None) == "main.py"
    assert remap_write_path(
        "main.py",
        "snake.py",
        user_task="создай змейку",
    ) == "snake.py"
    assert remap_write_path(
        "game.py",
        "snake.py",
        user_task="создай змейку",
    ) == "game.py"


def test_continue_doom_in_file_stays_in_test22():
    task = "продолжи делать doom в /test22/doom.py"
    assert mention_intent(task) == "edit"
    assert infer_task_write_path(task) == "test22/doom.py"
    assert remap_write_path("doom.py", "test22/doom.py", user_task=task) == "test22/doom.py"
    assert resolve_gui_fallback_path(task, None) == "test22/doom.py"
    assert remap_write_path(
        "utils.py",
        "main.py",
        user_task="исправь /main.py",
    ) == "main.py"


def test_create_in_folder_ignores_attached_other_file():
    task = "/snake.py создай мне сапёра с игровым окном в /test1"
    assert mention_intent(task) == "create"
    assert infer_task_write_path(task) == "test1/minesweeper.py"
    assert resolve_gui_fallback_path(task, "snake.py") == "test1/minesweeper.py"
    assert resolve_gui_fallback_path(
        "создай мне сапёра с игровым окном в /test1",
        None,
    ) == "test1/minesweeper.py"
