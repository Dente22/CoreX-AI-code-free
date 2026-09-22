from core.python_deps import (
    ensure_requirements_line,
    extract_missing_module,
    is_missing_dependency_error,
    parse_top_level_imports,
    pip_package_name,
    probe_missing_modules,
)
import re


def test_extract_missing_does_not_treat_tk_as_pip():
    from core.python_deps import is_pip_installable_module, rewrite_tkinter_comma_import

    detail = "Error: No module named 'Tk'\nКод выхода: 1"
    assert extract_missing_module(detail) is None
    assert is_missing_dependency_error(detail) is False
    assert is_pip_installable_module("Tk") is False
    assert is_pip_installable_module("pygame") is True
    src = 'import tkinter, Tk, Canvas\nroot = Tk()\n'
    fixed = rewrite_tkinter_comma_import(src)
    assert "import tkinter, Tk" not in fixed
    assert "from tkinter import Tk, Canvas" in fixed
    assert "import tkinter\n" in fixed
    detail = "Error: No module named 'pygame'\nКод выхода: 1"
    assert extract_missing_module(detail) == "pygame"
    assert is_missing_dependency_error(detail)


def test_rewrite_tkinter_winfo_keysym_uses_bind():
    from core.python_deps import rewrite_tkinter_gui_mistakes

    src = '''import tkinter as tk
root = tk.Tk()
canvas = tk.Canvas(root, width=640, height=400)
player = canvas.create_rectangle(10, 10, 20, 20)
def tick():
    if root.winfo_keysym("Left"):
        canvas.move(player, -5, 0)
    root.after(100, tick)
    root.bind("<KeyPress>", lambda event: root.event_generate(f"<Key-{event.keysym}>"))
tick()
root.mainloop()
'''
    fixed = rewrite_tkinter_gui_mistakes(src)
    assert "winfo_keysym" not in fixed
    assert "pressed_keys" in fixed
    assert "if \"Left\" in pressed_keys:" in fixed
    assert "event_generate" not in fixed
    assert "bind('<KeyPress>'" in fixed or 'bind("<KeyPress>"' in fixed
    compile(fixed, "<t>", "exec")


def test_rewrite_bare_after_call():
    from core.python_deps import rewrite_bare_after_call

    src = "import tkinter as tk\nroot = tk.Tk()\ndef tick():\n    after(100, tick)\ntick()\n"
    fixed = rewrite_bare_after_call(src)
    assert "root.after(100, tick)" in fixed
    assert re.search(r"(?<![.\w])after\s*\(", fixed) is None


def test_extract_missing_from_module_not_found():
    detail = "ModuleNotFoundError: No module named 'requests'"
    assert extract_missing_module(detail) == "requests"


def test_pip_package_pillow_alias():
    assert pip_package_name("PIL") == "Pillow"
    assert pip_package_name("pygame") == "pygame-ce"


def test_ensure_requirements_line_creates_file(tmp_path):
    assert ensure_requirements_line(tmp_path, "pygame") is True
    text = (tmp_path / "requirements.txt").read_text(encoding="utf-8")
    assert "pygame" in text
    assert ensure_requirements_line(tmp_path, "pygame") is False


def test_parse_top_level_imports():
    src = "import pygame\nfrom random import randint\nimport os\n"
    assert parse_top_level_imports(src) == ["pygame", "random", "os"]


def test_probe_skips_stdlib_and_finds_missing(tmp_path):
    src = "import os\nimport corex_no_such_pkg_xyz\n"
    missing = probe_missing_modules(src, __import__("sys").executable, tmp_path)
    assert "os" not in missing
    assert "corex_no_such_pkg_xyz" in missing
