from core.file_outline import (
    dedupe_top_level_defs,
    drop_duplicate_top_level_blocks,
    duplicate_def_names,
    edit_guidance_after_write,
    idle_stop_chat,
    is_stub_python,
    line_map_for_prompt,
    looks_like_truncated_source,
    numbered_snapshot,
    numbered_window,
    prepare_source_write,
)
from core.staged_write import merge_append


SNAKE_HEAD = """import pygame

def our_snake(snake_block, snake_list):
    pass

def gameLoop():
    game_over = False
    pygame.quit()

gameLoop()
"""


def test_line_map_lists_defs_and_calls_with_line_numbers():
    text = line_map_for_prompt(SNAKE_HEAD, path="main.py")
    assert "def our_snake" in text or "our_snake" in text
    assert "gameLoop" in text
    assert "patch_file" in text
    assert "delete" in text
    assert "3" in text  # def our_snake
    assert "6" in text  # def gameLoop


def test_line_map_marks_duplicate_def():
    blob = SNAKE_HEAD + "\ndef gameLoop():\n    return\n"
    text = line_map_for_prompt(blob, path="main.py")
    assert "ПОВТОР" in text
    dups = duplicate_def_names(blob)
    assert dups["gameLoop"][0] == 6
    assert dups["gameLoop"][1] > 6


def test_numbered_window_marks_focus_line():
    window = numbered_window(SNAKE_HEAD, 6, radius=2)
    assert "6|" in window
    assert "<<" in window
    assert "gameLoop" in window


def test_complete_file_is_not_truncated():
    assert looks_like_truncated_source(SNAKE_HEAD) is False
    assert looks_like_truncated_source("import pygame\npygame.init()\n") is False


def test_unterminated_input_is_truncated():
    src = (
        'if __name__ == "__main__":\n'
        "    while True:\n"
        '        y = int(input("Enter row: "))\n'
        '        x = int(input("Enter col\n'
    )
    assert looks_like_truncated_source(src) is True


def test_cut_off_if_last_line_is_truncated():
    src = "class Game:\n    def reveal(self, y, x):\n        if self\n"
    assert looks_like_truncated_source(src) is True


def test_syntax_error_in_middle_is_not_truncation():
    src = "def foo():\n    return 1\nif self\nprint(1)\n"
    assert looks_like_truncated_source(src) is False


def test_drop_duplicate_gameloop_from_append():
    chunk = (
        "def gameLoop():\n"
        "    dis.fill(white)\n"
        "    pygame.quit()\n"
        "\n"
        "gameLoop()\n"
    )
    cleaned = drop_duplicate_top_level_blocks(SNAKE_HEAD, chunk)
    assert "def gameLoop" not in cleaned
    assert "dis.fill" not in cleaned


def test_merge_append_rejects_second_gameloop():
    chunk = "def gameLoop():\n    dis.fill(white)\n"
    merged = merge_append(SNAKE_HEAD, chunk)
    assert merged.count("def gameLoop") == 1
    assert "dis.fill(white)" not in merged


def test_merge_append_keeps_new_function():
    merged = merge_append(SNAKE_HEAD, "def show_score(n):\n    print(n)\n")
    assert "def show_score" in merged
    assert "def gameLoop" in merged


def test_guidance_after_complete_write_says_patch_not_append():
    text = edit_guidance_after_write("main.py", SNAKE_HEAD, truncated=False)
    assert "append_file" not in text
    assert "patch_file" in text
    assert "done" in text.lower() or "полн" in text.lower()
    assert "Карта" in text


def test_guidance_after_truncated_write_allows_append_tail():
    text = edit_guidance_after_write(
        "main.py",
        "import pygame\nclass Snake:\n",
        truncated=True,
    )
    assert "append_file" in text
    assert "Карта" in text


def test_numbered_snapshot_uses_real_line_numbers():
    snap = numbered_snapshot(SNAKE_HEAD, path="main.py")
    assert "    6|" in snap or "   6|" in snap
    assert "Карта" in snap


def test_idle_stop_after_write_is_status_not_error():
    channel, message = idle_stop_chat(["main.py"])
    assert channel == "CoreX Status"
    assert "main.py" in message
    assert "строк" in message.lower() or "строк" in message


def test_idle_stop_without_write_is_error():
    channel, message = idle_stop_chat([])
    assert channel == "CoreX Error"
    assert "не записала" in message


def test_two_prints_is_stub_snake_is_not():
    assert is_stub_python('print("a")\nprint("b")\n') is True
    assert is_stub_python('print("CoreX stub")\n') is True
    assert is_stub_python('print("hello")\n') is False
    assert is_stub_python(SNAKE_HEAD) is False
    assert is_stub_python("def main():\n    pass\n") is True
    assert is_stub_python("def main():\n    pass\n\nif __name__ == '__main__':\n    main()\n") is True


def test_prepare_write_rejects_pass_only_main():
    gated = prepare_source_write("main.py", "def main():\n    pass\n")
    assert gated.get("error")
    assert "Заглушка" in gated["error"]


def test_dedupe_keeps_first_gameloop():
    blob = SNAKE_HEAD + "\ndef gameLoop():\n    dis.fill(white)\n    return\n"
    cleaned = dedupe_top_level_defs(blob)
    assert cleaned.count("def gameLoop") == 1
    assert "dis.fill" not in cleaned
    assert "def our_snake" in cleaned


def test_prepare_write_keeps_working_file_if_incoming_is_broken():
    working = (
        "import tkinter as tk\n"
        "root = tk.Tk()\n"
        "tk.Button(root, text='1').pack()\n"
        "root.mainloop()\n"
    )
    gated = prepare_source_write(
        "calculator.py",
        working + "\n(Blocked done attempt 2/3)\n",
        existing=working,
    )
    assert "error" not in gated
    assert "Blocked done" not in gated["content"]
    assert "mainloop" in gated["content"]

    rejected = prepare_source_write(
        "calculator.py",
        "(Blocked done attempt 1/3)\n",
        existing=working,
    )
    assert rejected.get("error")
    assert "Не затираю" in rejected["error"]


def test_prepare_write_rejects_stub():
    gated = prepare_source_write("main.py", 'print(1)\nprint(2)\n')
    assert gated.get("error")
    assert "Заглушка" in gated["error"]


def test_prepare_write_strips_duplicate_def():
    gated = prepare_source_write("main.py", SNAKE_HEAD + "\ndef gameLoop():\n    return\n")
    assert "error" not in gated
    assert gated["content"].count("def gameLoop") == 1
    assert gated.get("stripped_duplicates") is True


EMPTY_PYGAME = """import pygame
import pygame
pygame.init()
pygame.init()
width, height = 800, 600
screen = pygame.display.set_mode((width, height))
pygame.display.set_caption("Игра")
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    screen.fill((0, 0, 0))
    pygame.display.flip()
pygame.quit()
"""

CONSOLE_MINES = """import random

SIZE = 5
mines = {(1, 2), (0, 4)}
board = [["." for _ in range(SIZE)] for _ in range(SIZE)]

def play():
    row = int(input("Enter row (0 to 4): "))
    col = int(input("Enter column (0 to 4): "))
    if (row, col) in mines:
        print("boom")
    else:
        board[row][col] = str(len(mines))

play()
"""

PYGAME_MINES = """import pygame
pygame.init()
screen = pygame.display.set_mode((400, 400))
mines = {(1, 1), (2, 3)}
cell = 40
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.MOUSEBUTTONDOWN:
            x, y = event.pos
            if (y // cell, x // cell) in mines:
                print("boom")
    pygame.draw.rect(screen, (80, 80, 80), (0, 0, cell, cell))
    pygame.display.flip()
pygame.quit()
"""


def test_empty_pygame_window_is_stub():
    from core.file_outline import looks_like_empty_window_skeleton

    assert looks_like_empty_window_skeleton(EMPTY_PYGAME) is True
    assert is_stub_python(EMPTY_PYGAME) is True
    assert looks_like_empty_window_skeleton(PYGAME_MINES) is False
    assert is_stub_python(PYGAME_MINES) is False
    assert is_stub_python(SNAKE_HEAD) is False


def test_prepare_write_rejects_empty_pygame():
    gated = prepare_source_write("main.py", EMPTY_PYGAME)
    assert gated.get("error")
    assert "пустое окно" in gated["error"].lower() or "Пустое окно" in gated["error"]


def test_prepare_write_rejects_overwrite_mines_with_empty_window():
    gated = prepare_source_write("main.py", EMPTY_PYGAME, existing=CONSOLE_MINES)
    assert gated.get("error")


def test_prepare_write_rejects_losing_game_tokens():
    other = "import math\n" + "\n".join(f"value_{i} = {i} * 2" for i in range(40))
    gated = prepare_source_write("main.py", other, existing=CONSOLE_MINES)
    assert gated.get("error")
    assert "пустым окном" in gated["error"].lower()


def test_prepare_write_allows_pygame_minesweeper():
    gated = prepare_source_write("main.py", PYGAME_MINES, existing=CONSOLE_MINES)
    assert "error" not in gated
    assert "MOUSEBUTTONDOWN" in gated["content"]
    assert "mines" in gated["content"]
