import ast

from core.game_gui_upgrade import (
    GUI_APP_WINDOW_HINT,
    GUI_GAME_WINDOW_HINT,
    GUI_WINDOW_HINT,
    INCOMPLETE_GUI_ERROR,
    build_tkinter_minesweeper,
    looks_like_console_minesweeper,
    looks_like_incomplete_gui_game,
    looks_like_minesweeper_task,
    maybe_upgrade_console_game_to_window,
    should_use_gui_game_bites_plan,
    window_hint_for_task,
)
from core.task_routing import looks_like_gui_window_request


CONSOLE_MINES = """
import random

def create_minefield(rows, cols, mines):
    minefield = [['.' for _ in range(cols)] for _ in range(rows)]
    return minefield

def play_minefield():
    rows = int(input("rows: "))
    print(rows)

if __name__ == "__main__":
    play_minefield()
"""


def test_gui_window_phrases():
    assert looks_like_gui_window_request("добавь игровое окно") is True
    assert looks_like_gui_window_request(
        "добавь к сапёру окно игры, что бы не в консоли а в отдельном игровом окне"
    ) is True
    assert looks_like_gui_window_request("создай змейку на pygame") is False
    assert looks_like_gui_window_request("создай сапёра на питоне") is False
    assert looks_like_gui_window_request("сделай сапера с игровым окном") is True
    assert looks_like_minesweeper_task("сделай сапера с игровым окном") is True
    assert looks_like_minesweeper_task("создай змейку") is False
    assert looks_like_minesweeper_task("создай змейку с игровым окном в /test") is False
    assert looks_like_minesweeper_task("создай телеграм бота") is False
    assert looks_like_minesweeper_task("сделай сайт-визитку") is False


def test_console_minesweeper_detected():
    assert looks_like_console_minesweeper(CONSOLE_MINES) is True
    assert looks_like_console_minesweeper("print('hi')\n") is False
    gui = build_tkinter_minesweeper(CONSOLE_MINES)
    assert looks_like_console_minesweeper(gui) is False


def test_tkinter_minesweeper_compiles_and_is_a_game():
    src = build_tkinter_minesweeper(CONSOLE_MINES)
    ast.parse(src)
    assert "import tkinter" in src
    assert "tk.Button" in src
    assert "mainloop" in src
    assert "create_minefield" in src
    assert "input(" not in src


def test_upgrade_only_when_user_asks_for_window():
    assert maybe_upgrade_console_game_to_window(
        user_task="создай сапёра",
        source=CONSOLE_MINES,
    ) is None
    upgrade = maybe_upgrade_console_game_to_window(
        user_task="добавь игровое окно",
        source=CONSOLE_MINES,
    )
    assert upgrade is not None
    assert upgrade["path"] == "main.py"
    ast.parse(upgrade["content"])
    assert "tkinter" in upgrade["content"]


INCOMPLETE_TK_MINES = '''
import random
import tkinter as tk
from tkinter import messagebox

class Minesweeper:
    def __init__(self, rows, cols, mines):
        self.rows = rows
        self.cols = cols
        self.mines = mines
        self.board = [[0 for _ in range(cols)] for _ in range(rows)]
        self.create_board()
        self.create_window()

    def create_board(self):
        mines_placed = 0
        while mines_placed < self.mines:
            row = random.randint(0, self.rows - 1)
            col = random.randint(0, self.cols - 1)
            if self.board[row][col] == 0:
                self.board[row][col] = -1
                mines_placed += 1

    def create_window(self):
        self.window = tk.Tk()
        self.window.title("Minesweeper")
        self.buttons = [[None for _ in range(self.cols)] for _ in range(self.rows)]
        for row in range(self.rows):
            for col in range(self.cols):
                button = tk.Button(
                    self.window,
                    text="?",
                    width=2,
                    height=1,
                    command=lambda r=row, c=col: self.click(r, c),
                )
                button.grid(row=row, column=col)
                self.buttons[row][col] = button

    def click(self, row, col):
        if self.board[row][col] == -1:
            messagebox.showinfo("Game Over", "You hit a mine!")
            self.window.destroy()
        elif self.board[row][col] == 0:
            self.reveal_zeroes(row, col)
        else:
            self.buttons[row][col].config(text=str(self.board[row][col]))

    def reveal_zeroes(self, row, col):
        pass
'''


def test_incomplete_tkinter_minesweeper_is_detected():
    assert looks_like_incomplete_gui_game(INCOMPLETE_TK_MINES) is True
    complete = build_tkinter_minesweeper(INCOMPLETE_TK_MINES)
    assert looks_like_incomplete_gui_game(complete) is False
    assert "mainloop" in complete


def test_upgrade_incomplete_tkinter_stub():
    upgrade = maybe_upgrade_console_game_to_window(
        user_task="добавь игровое окно",
        source=INCOMPLETE_TK_MINES,
    )
    assert upgrade is not None
    ast.parse(upgrade["content"])
    assert "mainloop" in upgrade["content"]
    assert "<Button-3>" in upgrade["content"]


def test_incomplete_gui_write_is_rejected():
    from core.file_outline import prepare_source_write

    gated = prepare_source_write("main.py", INCOMPLETE_TK_MINES)
    assert "error" in gated
    complete = build_tkinter_minesweeper(INCOMPLETE_TK_MINES)
    ok = prepare_source_write("main.py", complete, existing=INCOMPLETE_TK_MINES)
    assert "error" not in ok
    assert "mainloop" in ok["content"]

    upgrade = maybe_upgrade_console_game_to_window(
        user_task="добавь игровое окно",
        source=CONSOLE_MINES,
    )
    gated = prepare_source_write("main.py", upgrade["content"], existing=CONSOLE_MINES)
    assert "error" not in gated
    assert "tk.Button" in gated["content"]


INCOMPLETE_SNAKE = '''
import tkinter as tk
import random

WIDTH, HEIGHT = 400, 400
CELL_SIZE = 20
snake = [[WIDTH // 2, HEIGHT // 2]]
food = [0, 0]

def draw_snake():
    canvas.delete("snake")

def update_field():
    draw_snake()
    root.after(100,)
'''


def test_incomplete_gui_is_rejected_without_swapping_program():
    from core.file_outline import prepare_source_write

    assert looks_like_incomplete_gui_game(INCOMPLETE_SNAKE) is True
    assert maybe_upgrade_console_game_to_window(
        user_task="добавь игровое окно",
        source=INCOMPLETE_SNAKE,
    ) is None
    assert maybe_upgrade_console_game_to_window(
        user_task="создай змейку с игровым окном в /test",
        source="",
    ) is None
    gated = prepare_source_write("test/main.py", INCOMPLETE_SNAKE)
    assert gated.get("error") == INCOMPLETE_GUI_ERROR
    assert "сапёр" not in gated["error"].lower()
    assert "minesweeper" not in gated["error"].lower()
    assert "змейк" not in gated["error"].lower()


def test_window_hint_does_not_name_a_specific_program():
    for task in (
        "создай змейку с игровым окном в /test",
    ):
        hint = window_hint_for_task(task)
        assert hint == GUI_GAME_WINDOW_HINT
        assert "Minesweeper" not in hint
        assert "flood-fill" not in hint
    for task in (
        "сделай сапера с игровым окном",
        "калькулятор с окном tkinter",
        "сделай калькулятор с отдельным окном",
    ):
        hint = window_hint_for_task(task)
        assert hint == GUI_APP_WINDOW_HINT
        assert "Canvas game" in hint or "NOT a Canvas" in hint
        assert "create_rectangle" not in hint.lower() or "NO create_rectangle" in hint
    assert window_hint_for_task("создай телеграм бота") == ""
    assert window_hint_for_task("сделай сайт на html") == ""


def test_calculator_window_uses_app_plan_not_game_bites():
    from core.step_execution import gui_app_window_plan, gui_window_bites_plan

    task = "сделай калькулятор с отдельным окном"
    assert should_use_gui_game_bites_plan(task) is False
    app_steps = gui_app_window_plan(path="calculator.py", user_task=task)
    assert [s.id for s in app_steps] == ["gui_app", "verify"]
    assert "калькулятор" in app_steps[0].instruction.lower()
    assert "create_rectangle" in app_steps[0].instruction
    game_steps = gui_window_bites_plan(path="calculator.py", user_task=task)
    assert [s.id for s in game_steps] == ["gui_window", "gui_move", "gui_world"]
    doom_task = "создай 1 версию doom с игровым окном в /test22"
    assert should_use_gui_game_bites_plan(doom_task) is True


def test_other_tasks_do_not_get_minesweeper_template():
    for task in (
        "создай змейку с игровым окном в /test",
        "создай телеграм бота",
        "сделай сайт-визитку",
        "напиши функцию factorial",
    ):
        assert maybe_upgrade_console_game_to_window(user_task=task, source="") is None


def test_calculator_window_gets_tkinter_template():
    upgrade = maybe_upgrade_console_game_to_window(
        user_task="создай мне калькулятор с окном",
        source="",
        rel_path="calculator.py",
    )
    assert upgrade is not None
    assert upgrade["path"] == "calculator.py"
    ast.parse(upgrade["content"])
    assert "tkinter" in upgrade["content"]
    assert "eval(" in upgrade["content"]
    assert "Minesweeper" not in upgrade["content"]
    good = maybe_upgrade_console_game_to_window(
        user_task="создай калькулятор с окном",
        source=upgrade["content"],
        rel_path="calculator.py",
    )
    assert good is None


def test_calculator_game_skeleton_gets_template():
    game_calc = '''import tkinter as tk
root = tk.Tk()
canvas = tk.Canvas(root, width=300, height=200)
canvas.pack()
player = canvas.create_rectangle(100, 100, 200, 200, fill="blue")
def tick():
    after(100, tick)
tick()
root.mainloop()
'''
    upgrade = maybe_upgrade_console_game_to_window(
        user_task="сделай калькулятор с отдельным окном",
        source=game_calc,
        rel_path="calculator.py",
    )
    assert upgrade is not None
    assert "Entry" in upgrade["content"]
    assert "create_rectangle" not in upgrade["content"]


def test_create_minesweeper_in_folder_uses_that_path():
    from core.write_target import resolve_gui_fallback_path

    task = "создай мне сапёра с игровым окном в /test1"
    path = resolve_gui_fallback_path(task, None)
    assert path == "test1/minesweeper.py"
    upgrade = maybe_upgrade_console_game_to_window(
        user_task=task,
        source="",
        rel_path=path,
    )
    assert upgrade is not None
    assert upgrade["path"] == "test1/minesweeper.py"
    ast.parse(upgrade["content"])


def test_create_minesweeper_window_from_empty_project():
    upgrade = maybe_upgrade_console_game_to_window(
        user_task="сделай сапера с игровым окном",
        source="",
    )
    assert upgrade is not None
    ast.parse(upgrade["content"])
    assert "mainloop" in upgrade["content"]
    assert "tk.Button" in upgrade["content"]
    from core.file_outline import prepare_source_write

    gated = prepare_source_write("main.py", upgrade["content"])
    assert "error" not in gated


def test_window_request_without_minesweeper_does_not_fill_empty():
    assert maybe_upgrade_console_game_to_window(
        user_task="добавь игровое окно",
        source="",
    ) is None


COMPLETE_TINY_WINDOW = """
import tkinter as tk

root = tk.Tk()
root.title("Calc")
tk.Button(root, text="1", command=lambda: None).pack()
root.mainloop()
"""


def test_complete_non_game_window_is_allowed():
    from core.file_outline import prepare_source_write

    assert looks_like_incomplete_gui_game(COMPLETE_TINY_WINDOW) is False
    gated = prepare_source_write("main.py", COMPLETE_TINY_WINDOW)
    assert "error" not in gated
    assert maybe_upgrade_console_game_to_window(
        user_task="калькулятор с окном tkinter",
        source=COMPLETE_TINY_WINDOW,
    ) is None


def test_doom_window_has_no_ready_template_only_bites():
    from core.game_gui_upgrade import looks_like_doom_task
    from core.step_execution import current_write_target, gui_window_bites_plan, mark_step_completed
    from core.write_target import resolve_gui_fallback_path, suggest_created_filename

    task = "создай 1 версию doom с игровым окном в /test22"
    assert looks_like_doom_task(task) is True
    assert looks_like_gui_window_request(task) is True
    assert suggest_created_filename(task) == "doom.py"
    path = resolve_gui_fallback_path(task, None)
    assert path == "test22/doom.py"
    assert maybe_upgrade_console_game_to_window(
        user_task=task,
        source="",
        rel_path=path,
    ) is None
    steps = gui_window_bites_plan(path=path, user_task=task)
    assert [step.id for step in steps] == ["gui_window", "gui_move", "gui_world"]
    assert "raycast" in steps[0].instruction.lower() or "raycast" in steps[2].instruction.lower()
    assert current_write_target(steps, set()) == path
    done = mark_step_completed(steps, set(), tool="write_file", path=path, success=True)
    assert "gui_window" not in done
    assert "gui_move" not in done
    assert "gui_world" not in done
    again = mark_step_completed(steps, done, tool="write_file", path=path, success=True)
    assert again == done
    assert current_write_target(steps, done) == path
    assert "test22/doom.py" in steps[0].tool_hint
    assert "import tkinter, Tk" not in steps[0].instruction
    assert "tk.Tk" in steps[0].instruction or "tkinter as tk" in steps[0].instruction


SKELETON_DOOM = """
import tkinter as tk
from tkinter import Canvas
root = tk.Tk()
root.title("Doom Clone")
canvas = Canvas(root, width=640, height=400)
canvas.pack()
player = canvas.create_rectangle(100, 100, 150, 150, fill="blue")
root.mainloop()
"""

MOVE_DOOM = """
import tkinter as tk
from tkinter import Canvas
root = tk.Tk()
root.title("Doom Clone")
canvas = Canvas(root, width=640, height=400)
canvas.pack()
player = canvas.create_rectangle(100, 100, 150, 150, fill="blue")
root.bind("<KeyPress>", lambda e: None)
def tick():
    root.after(16, tick)
tick()
root.mainloop()
"""


def test_gui_bites_follow_file_contents_not_write_count():
    from core.step_execution import (
        gui_bite_satisfied,
        gui_partial_stop_message,
        gui_window_bites_plan,
        should_block_done_for_plan,
        sync_gui_bites_from_source,
    )

    steps = gui_window_bites_plan(path="test22/doom.py", user_task="doom окно")
    assert gui_bite_satisfied("gui_window", SKELETON_DOOM) is True
    assert gui_bite_satisfied("gui_move", SKELETON_DOOM) is False
    assert gui_bite_satisfied("gui_world", SKELETON_DOOM) is False
    done = sync_gui_bites_from_source(steps, set(), SKELETON_DOOM)
    assert done == {"gui_window"}
    done = sync_gui_bites_from_source(steps, done, SKELETON_DOOM)
    assert done == {"gui_window"}
    assert gui_bite_satisfied("gui_move", MOVE_DOOM) is True
    broken_keys = "root.winfo_keysym('Left')\nroot.bind('<KeyPress>', lambda e: None)\n"
    assert gui_bite_satisfied("gui_move", broken_keys) is False
    assert "gui_world" not in done
    msg = gui_partial_stop_message(steps, {"gui_window"}, "test22/doom.py")
    assert "WASD" in msg
    assert "test22/doom.py" in msg
    assert should_block_done_for_plan(steps, {"gui_window"}, is_web=False) is True
    assert (
        should_block_done_for_plan(
            steps, {"gui_window", "gui_move", "gui_world"}, is_web=False
        )
        is False
    )


def test_needs_runtime_blocker_until_self_test(tmp_path):
    from unittest.mock import MagicMock

    from core.orchestrator import CoreXOrchestrator

    orch = CoreXOrchestrator(
        ollama_client=MagicMock(),
        mcp_manager=MagicMock(),
        gui=MagicMock(),
    )
    orch.project_root = tmp_path
    dest = tmp_path / "test22"
    dest.mkdir()
    (dest / "doom.py").write_text(SKELETON_DOOM, encoding="utf-8")
    assert orch._needs_runtime_blocker(
        require_verification=True,
        py_files_written={"test22/doom.py"},
        verified_py_files={"test22/doom.py"},
        terminal_checks_ok=0,
        confirmed_writes=["test22/doom.py"],
    ) is True
    assert orch._pick_smoke_script(["test22/doom.py"], {"test22/doom.py"}) == "test22/doom.py"
    assert orch._needs_runtime_blocker(
        require_verification=True,
        py_files_written={"test22/doom.py"},
        verified_py_files={"test22/doom.py"},
        terminal_checks_ok=1,
        confirmed_writes=["test22/doom.py"],
    ) is False
