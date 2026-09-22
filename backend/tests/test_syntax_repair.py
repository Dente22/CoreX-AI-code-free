from core.syntax_repair import auto_repair_python_source, repair_file_on_disk


SNAKE_WITH_BAD_INDENT = '''import sys

    print("Змейка запущена!")
import random

def create_snake():
    return [(10, 5), (9, 5), (8, 5)]

def move_snake(snake, direction):
    head = snake[0]
    if direction == 'up':
        new_head = (head[0], head[1] - 1)
    elif direction == 'down':
        new_head = (head[0], head[1] + 1)
    elif direction == 'left':
        new_head = (head[0] - 1, head[1])
    elif direction == 'right':
        new_head = (head[0] + 1, head[1])
    snake.insert(0, new_head)
    return snake

def check_collision(snake):
    head = snake[0]
    if head in snake[1:]:
        return True
    if head[0] < 0 or head[0] >= 20 or head[1] < 0 or head[1] >= 20:
        return True
    return False

def place_food(snake):
    food = (random.randint(0, 19), random.randint(0, 19))
    while food in snake:
        food = (random.randint(0, 19), random.randint(0, 19))
    return food

def main():
    snake = create_snake()
    direction = 'right'
    food = place_food(snake)
    while True:
        move_snake(snake, direction)
        if check_collision(snake):
            print("Game Over!")
            break
        if snake[0] == food:
            snake.append(food)
            food = place_food(snake)

if __name__ == "__main__":
    main()
'''


def test_repair_strips_blocked_done_leak():
    src = (
        "import tkinter as tk\n"
        "root = tk.Tk()\n"
        "tk.Button(root, text='ok').pack()\n"
        "root.mainloop()\n"
        "(Blocked done attempt 2/3)\n"
    )
    result = auto_repair_python_source(src, "SyntaxError: invalid syntax (line 5)")
    assert result.get("ok") is True
    assert "Blocked done" not in result["content"]
    compile(result["content"], "calculator.py", "exec")


def test_repair_unexpected_indent_between_imports():
    result = auto_repair_python_source(
        SNAKE_WITH_BAD_INDENT,
        "Sorry: IndentationError: unexpected indent (main.py, line 3)",
    )
    assert result.get("ok") is True
    repaired = result["content"]
    assert '    print("Змейка запущена!")' not in repaired
    assert 'print("Змейка запущена!")' in repaired
    compile(repaired, "main.py", "exec")


def test_repair_nested_unexpected_indent():
    src = "def foo():\n    x = 1\n        y = 2\n    return x + y\n"
    result = auto_repair_python_source(src, "IndentationError: unexpected indent (line 3)")
    assert result.get("ok") is True
    compile(result["content"], "<t>", "exec")


def test_repair_expected_indent_inserts_pass():
    src = "def foo():\nprint(1)\n"
    result = auto_repair_python_source(src, "IndentationError: expected an indented block (line 1)")
    assert result.get("ok") is True
    compile(result["content"], "<t>", "exec")


def test_repair_file_on_disk_writes_fixed_snake(tmp_path):
    path = tmp_path / "main.py"
    path.write_text(SNAKE_WITH_BAD_INDENT, encoding="utf-8")
    result = repair_file_on_disk(tmp_path, "main.py", "IndentationError: unexpected indent")
    assert result.get("ok") is True
    compile(path.read_text(encoding="utf-8"), str(path), "exec")


def test_repair_file_refuses_to_replace_game_with_stub(tmp_path, monkeypatch):
    path = tmp_path / "main.py"
    original = "def play():\n    board = [[0] * 5 for _ in range(5)]\n    print(board)\n" * 6
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(
        "core.syntax_repair.auto_repair_python_source",
        lambda *_a, **_k: {
            "ok": True,
            "content": "def main():\n    pass\n",
            "highlights": [{"line": 1, "type": "replace"}],
            "message": "Синтаксис восстановлен (1 правок)",
        },
    )
    result = repair_file_on_disk(tmp_path, "main.py", "IndentationError")
    assert result.get("ok") is False
    assert result.get("reason") == "repair_would_stub"
    assert path.read_text(encoding="utf-8") == original


def test_valid_file_not_rewritten_on_nameerror_hint():
    src = (
        "while True:\n"
        "    if key == 'A':\n"
        "        direction = 'LEFT'\n"
    )
    result = auto_repair_python_source(
        src,
        "NameError: name 'key' is not defined",
    )
    assert result.get("ok") is False
    assert result.get("reason") == "already_valid"
    assert result["content"] == src


def test_repair_does_not_delete_non_pygame_calls():
    src = "print(1)\nscreen.fill((0, 0, 0))\n"
    result = auto_repair_python_source(src, "")
    assert result.get("ok") is False
    assert "screen.fill" in result["content"]


def test_repair_closes_unterminated_input_string():
    src = (
        "while True:\n"
        '    y = int(input("Enter row: "))\n'
        '    x = int(input("Enter col\n'
    )
    result = auto_repair_python_source(src, "SyntaxError: unterminated string literal")
    assert result.get("ok") is True
    compile(result["content"], "<t>", "exec")
    assert "Enter col" in result["content"]


def test_repair_closes_cut_off_if_on_last_line():
    src = (
        "class Minesweeper:\n"
        "    def reveal(self, y, x):\n"
        "        if self.board[y][x] == '*' and self.re\n"
    )
    result = auto_repair_python_source(src, "SyntaxError: expected ':'")
    assert result.get("ok") is True
    compile(result["content"], "<t>", "exec")


def test_repair_fixes_tkinter_comma_import(tmp_path):
    path = tmp_path / "doom.py"
    path.write_text("import tkinter, Tk, Canvas\nroot = Tk()\n", encoding="utf-8")
    result = repair_file_on_disk(tmp_path, "doom.py", "Error: No module named 'Tk'")
    assert result.get("ok") is True
    text = path.read_text(encoding="utf-8")
    assert "from tkinter import Tk, Canvas" in text
    assert "import tkinter, Tk" not in text

