"""Консольную игру → окно tkinter, если модель не смогла переписать файл."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from core.task_routing import looks_like_gui_window_request

_MINE_HINTS = re.compile(
    r"minefield|minesweeper|create_mine|сап[её]р|play_minefield|\bmines\b",
    re.I,
)
_CALC_HINTS = re.compile(r"калькулятор|\bcalculator\b", re.I)
_DOOM_HINTS = re.compile(r"doom|wolfenstein|\bдум\b", re.I)

TKINTER_CALCULATOR = '''"""Калькулятор. Введите выражение и нажмите Вычислить."""
import tkinter as tk
from tkinter import messagebox


def calculate():
    try:
        result = eval(entry.get(), {"__builtins__": {}}, {})
        messagebox.showinfo("Результат", str(result))
    except Exception as exc:
        messagebox.showerror("Ошибка", str(exc))


root = tk.Tk()
root.title("Калькулятор")
entry = tk.Entry(root, width=28)
entry.pack(padx=12, pady=10)
tk.Button(root, text="Вычислить", command=calculate).pack(pady=(0, 12))
root.mainloop()
'''

TKINTER_MINESWEEPER = '''"""Сапёр. ЛКМ — открыть клетку, ПКМ — флаг."""
import random
import tkinter as tk
from tkinter import messagebox

ROWS = {rows}
COLS = {cols}
MINES = {mines}
CELL = 32


def create_minefield(rows, cols, mines):
    field = [[0 for _ in range(cols)] for _ in range(rows)]
    placed = 0
    while placed < mines:
        y = random.randint(0, rows - 1)
        x = random.randint(0, cols - 1)
        if field[y][x] == -1:
            continue
        field[y][x] = -1
        placed += 1
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ny, nx = y + dy, x + dx
                if 0 <= ny < rows and 0 <= nx < cols and field[ny][nx] != -1:
                    field[ny][nx] += 1
    return field


class Minesweeper:
    def __init__(self, root):
        self.root = root
        self.root.title("Сапёр")
        self.frame = tk.Frame(root)
        self.frame.pack(padx=8, pady=8)
        tk.Button(root, text="Новая игра", command=self.reset).pack(pady=(0, 8))
        self.buttons = []
        self.reset()

    def reset(self):
        for child in self.frame.winfo_children():
            child.destroy()
        self.field = create_minefield(ROWS, COLS, MINES)
        self.opened = [[False] * COLS for _ in range(ROWS)]
        self.flags = [[False] * COLS for _ in range(ROWS)]
        self.alive = True
        self.buttons = []
        for y in range(ROWS):
            row = []
            for x in range(COLS):
                btn = tk.Button(
                    self.frame,
                    width=2,
                    height=1,
                    font=("Segoe UI", 11, "bold"),
                    command=lambda r=y, c=x: self.reveal(r, c),
                )
                btn.grid(row=y, column=x, ipadx=4, ipady=4)
                btn.bind("<Button-3>", lambda e, r=y, c=x: self.toggle_flag(r, c))
                row.append(btn)
            self.buttons.append(row)

    def toggle_flag(self, y, x):
        if not self.alive or self.opened[y][x]:
            return
        self.flags[y][x] = not self.flags[y][x]
        self.buttons[y][x].config(text="F" if self.flags[y][x] else "")

    def reveal(self, y, x):
        if not self.alive or self.flags[y][x] or self.opened[y][x]:
            return
        if self.field[y][x] == -1:
            self.boom()
            return
        stack = [(y, x)]
        while stack:
            cy, cx = stack.pop()
            if self.opened[cy][cx] or self.flags[cy][cx]:
                continue
            self.opened[cy][cx] = True
            value = self.field[cy][cx]
            btn = self.buttons[cy][cx]
            btn.config(
                text="" if value == 0 else str(value),
                relief=tk.SUNKEN,
                state=tk.DISABLED,
                disabledforeground="#1a1a1a",
            )
            if value == 0:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < ROWS and 0 <= nx < COLS and not self.opened[ny][nx]:
                            stack.append((ny, nx))
        if self.won():
            self.alive = False
            messagebox.showinfo("Сапёр", "Победа!")

    def boom(self):
        self.alive = False
        for y in range(ROWS):
            for x in range(COLS):
                if self.field[y][x] == -1:
                    self.buttons[y][x].config(text="*", disabledforeground="#b00020")
        messagebox.showerror("Сапёр", "Мина!")

    def won(self):
        for y in range(ROWS):
            for x in range(COLS):
                if self.field[y][x] != -1 and not self.opened[y][x]:
                    return False
        return True


def main():
    root = tk.Tk()
    root.resizable(False, False)
    Minesweeper(root)
    root.mainloop()


if __name__ == "__main__":
    main()
'''

GUI_GAME_WINDOW_HINT = (
    "CRITICAL GUI game (Canvas): only the current plan step.\n"
    "tkinter Canvas + player shape + mainloop. Movement only when the plan says so.\n"
    "Use root.after(ms, fn) — never bare after(). No raycasting.\n"
    "JSON optional. A ```python fence is enough.\n"
)

GUI_APP_WINDOW_HINT = (
    "CRITICAL GUI app (calculator, timer, utility): tkinter Entry + Button/Label.\n"
    "NOT a Canvas game. NO create_rectangle player. NO tick loop. NO bare after().\n"
    "One window with controls, then mainloop.\n"
)

# Back-compat alias
GUI_WINDOW_HINT = GUI_GAME_WINDOW_HINT

INCOMPLETE_GUI_ERROR = (
    "Недописанная программа с окном отклонена: нужен запуск (mainloop / игровой цикл), "
    "не пустой after() и не pass вместо логики. Пришлите полный файл под текущую задачу."
)


def looks_like_minesweeper_task(user_task: str) -> bool:
    return bool(_MINE_HINTS.search(user_task or ""))


def looks_like_calculator_task(user_task: str) -> bool:
    return bool(_CALC_HINTS.search(user_task or ""))


def looks_like_doom_task(user_task: str) -> bool:
    return bool(_DOOM_HINTS.search(user_task or ""))


_UTIL_APP_HINTS = re.compile(
    r"калькулятор|\bcalculator\b|таймер|\btimer\b|todo|список\s+дел|конвертер|\bconverter\b",
    re.I,
)
_GAME_CANVAS_HINTS = re.compile(
    r"doom|wolfenstein|\bдум\b|змейк|\bsnake\b|тетрис|\btetris\b|"
    r"pong|\bping\b|platformer|platform|\bигр[ауы]\b|\bgame\b|"
    r"игров\w*\s+окн|canvas.*игр",
    re.I,
)


def looks_like_util_gui_app_task(user_task: str) -> bool:
    """Окно-приложение (калькулятор, таймер), не Canvas-игра."""
    task = user_task or ""
    if looks_like_calculator_task(task):
        return True
    if looks_like_minesweeper_task(task):
        return True
    return bool(_UTIL_APP_HINTS.search(task))


def should_use_gui_game_bites_plan(user_task: str) -> bool:
    """План Окно→Ходьба→Мир только для Canvas-игр, не для калькулятора и утилит."""
    task = user_task or ""
    if looks_like_util_gui_app_task(task):
        return False
    if looks_like_doom_task(task):
        return True
    if _GAME_CANVAS_HINTS.search(task):
        return True
    return False


def window_hint_for_task(user_task: str, source: str = "") -> str:
    del source
    if should_use_gui_game_bites_plan(user_task):
        return GUI_GAME_WINDOW_HINT
    if looks_like_gui_window_request(user_task):
        return GUI_APP_WINDOW_HINT
    return ""


def _is_placeholder_stmt(node: ast.AST) -> bool:
    if isinstance(node, ast.Pass):
        return True
    if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant):
        return node.value.value is Ellipsis
    return False


def _docstring_or_empty(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(getattr(node, "value", None), ast.Constant)
        and isinstance(node.value.value, str)
    )


def _pass_only_function_names(source: str) -> list[str]:
    try:
        tree = ast.parse(source or "")
    except SyntaxError:
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        stmts = [item for item in node.body if not _docstring_or_empty(item)]
        if stmts and all(_is_placeholder_stmt(item) for item in stmts):
            names.append(node.name)
    return names


def _looks_like_tk_gui(source: str) -> bool:
    blob = source or ""
    if "tkinter" not in blob.lower():
        return False
    return bool(
        re.search(
            r"\b(Tk|Button|Canvas|Frame|Label|Entry|Text)\s*\("
            r"|mainloop|\.after\s*\(|\bcanvas\.|\broot\.",
            blob,
            re.I,
        )
    )


def looks_like_incomplete_gui_game(source: str) -> bool:
    """Любое tk-окно без запуска, с оборванным after() или с pass вместо логики."""
    blob = source or ""
    if not blob.strip() or not _looks_like_tk_gui(blob):
        return False
    lowered = blob.lower()
    if "mainloop" not in lowered:
        return True
    if re.search(r"\.after\(\s*\d+\s*,\s*\)", blob):
        return True
    return bool(_pass_only_function_names(blob))


def looks_like_incomplete_minesweeper_gui(source: str) -> bool:
    blob = source or ""
    if not (_MINE_HINTS.search(blob) or "minesweeper" in blob.lower()):
        return False
    return looks_like_incomplete_gui_game(blob)


def looks_like_console_minesweeper(source: str) -> bool:
    blob = source or ""
    if not blob.strip():
        return False
    lowered = blob.lower()
    if "tkinter" in lowered:
        return False
    if "pygame" in lowered and ("set_mode" in lowered or "display." in lowered):
        return False
    if not _MINE_HINTS.search(blob):
        return False
    return "input(" in blob or "print(" in blob


def _parse_size(source: str, names: tuple[str, ...], default: int, lo: int, hi: int) -> int:
    for name in names:
        match = re.search(rf"^{name}\s*=\s*(\d+)\s*$", source or "", re.I | re.M)
        if match:
            value = int(match.group(1))
            return max(lo, min(hi, value))
    return default


def build_tkinter_minesweeper(source: str = "") -> str:
    rows = _parse_size(source, ("ROWS", "rows", "SIZE"), 9, 5, 16)
    cols = _parse_size(source, ("COLS", "cols"), rows, 5, 16)
    cells = rows * cols
    mines = _parse_size(source, ("MINES", "mines"), max(8, cells // 8), 3, cells - 1)
    return TKINTER_MINESWEEPER.format(rows=rows, cols=cols, mines=mines)


def maybe_upgrade_console_game_to_window(
    *,
    user_task: str,
    source: str,
    rel_path: str = "main.py",
) -> dict | None:
    """Шаблон сапёра — только если просили сапёра или в файле уже сапёр."""
    if not looks_like_gui_window_request(user_task):
        return None
    if not (rel_path or "").lower().endswith(".py"):
        return None
    blob = source or ""
    if looks_like_calculator_task(user_task):
        from core.step_execution import gui_app_satisfied

        if gui_app_satisfied(blob):
            return None
        try:
            ast.parse(TKINTER_CALCULATOR)
        except SyntaxError:
            return None
        return {
            "path": rel_path.replace("\\", "/"),
            "content": TKINTER_CALCULATOR,
            "message": (
                "Собрал калькулятор в окне tkinter. "
                "Введите выражение и нажмите Вычислить. Запусти кнопку Run."
            ),
        }
    mine_task = looks_like_minesweeper_task(user_task)
    incomplete_mines = looks_like_incomplete_minesweeper_gui(blob)
    console = looks_like_console_minesweeper(blob)
    empty = not blob.strip()
    stub = False
    if blob.strip() and not incomplete_mines and not console:
        from core.file_outline import is_stub_python

        stub = is_stub_python(blob)
    if not (incomplete_mines or console or (mine_task and (empty or stub))):
        return None
    content = build_tkinter_minesweeper(blob)
    try:
        ast.parse(content)
    except SyntaxError:
        return None
    if incomplete_mines:
        reason = "модель оставила заглушку без запуска окна"
    elif empty or stub:
        reason = "модель не собрала полный файл"
    else:
        reason = "модель не переписала файл"
    return {
        "path": rel_path.replace("\\", "/"),
        "content": content,
        "message": (
            f"Собрал сапёра в окне tkinter ({reason}). "
            "ЛКМ — открыть, ПКМ — флаг. Запусти ▶."
        ),
    }


def read_entry_source(project_root: Path, rel_path: str = "main.py") -> str:
    target = (project_root / rel_path).resolve()
    try:
        target.relative_to(project_root.resolve())
    except ValueError:
        return ""
    if not target.is_file():
        return ""
    try:
        return target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
