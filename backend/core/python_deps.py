"""Зависимости Python: ModuleNotFoundError ≠ ошибка синтаксиса."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

MODULE_ERROR_RE = re.compile(
    r"(?:ModuleNotFoundError:\s*)?No module named\s+['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)

_PIP_NAME = {
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "pillow": "Pillow",
    "sklearn": "scikit-learn",
    "yaml": "PyYAML",
    "bs4": "beautifulsoup4",
    "wx": "wxPython",
    "pygame": "pygame-ce",
}

# Имена из tkinter (классы/подмодули), 3B пишет «import tkinter, Tk, Canvas».
_NOT_PIP_MODULES = frozenset(
    {
        "Tk",
        "Tcl",
        "Canvas",
        "Button",
        "Frame",
        "Label",
        "Entry",
        "Text",
        "Listbox",
        "Menu",
        "Menubutton",
        "Message",
        "Radiobutton",
        "Checkbutton",
        "Scale",
        "Scrollbar",
        "Spinbox",
        "PanedWindow",
        "LabelFrame",
        "Toplevel",
        "ttk",
        "messagebox",
        "simpledialog",
        "filedialog",
        "colorchooser",
        "font",
        "constants",
        "commondialog",
    }
)

_TKINTER_COMMA_IMPORT = re.compile(
    r"^import tkinter\s*,\s*(.+)$",
    re.MULTILINE,
)


def extract_missing_module(detail: str) -> str | None:
    match = MODULE_ERROR_RE.search(detail or "")
    if not match:
        return None
    name = match.group(1).strip()
    if not name or "/" in name or "\\" in name:
        return None
    key = name.split(".")[0]
    if not is_pip_installable_module(key):
        return None
    return key


def is_pip_installable_module(module: str) -> bool:
    key = (module or "").split(".")[0].strip()
    if not key:
        return False
    if key in _NOT_PIP_MODULES:
        return False
    if is_stdlib_module(key):
        return False
    return True


def rewrite_tkinter_comma_import(source: str) -> str:
    """import tkinter, Tk, Canvas → import tkinter + from tkinter import Tk, Canvas."""

    def repl(match: re.Match) -> str:
        names: list[str] = []
        for part in match.group(1).split(","):
            token = (part or "").strip()
            if not token:
                continue
            token = token.split()[0]
            if token in {"tkinter", "as"}:
                continue
            if token not in names:
                names.append(token)
        if not names:
            return "import tkinter"
        return "import tkinter\nfrom tkinter import " + ", ".join(names)

    return _TKINTER_COMMA_IMPORT.sub(repl, source or "")


_WINFO_KEYSYM_IF = re.compile(
    r"if\s+\w+\.winfo_keysym\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\s*:",
)


def rewrite_tkinter_winfo_keysym(source: str) -> str:
    """3B выдумывает root.winfo_keysym('Left') — такого метода нет, нужен bind + set клавиш."""
    text = source or ""
    if "winfo_keysym" not in text:
        return text

    need_helper = "pressed_keys = set()" not in text
    text = _WINFO_KEYSYM_IF.sub(r'if "\1" in pressed_keys:', text)
    text = "\n".join(
        line
        for line in text.splitlines()
        if not (".bind(" in line and "event_generate" in line)
    ) + "\n"

    root = "root"
    match = re.search(r"^([A-Za-z_]\w*)\s*=\s*(?:tk\.)?Tk\s*\(", text, re.MULTILINE)
    if match:
        root = match.group(1)

    if need_helper:
        helper = (
            "pressed_keys = set()\n"
            "def _on_key_press(event):\n"
            "    pressed_keys.add(event.keysym)\n"
            "def _on_key_release(event):\n"
            "    pressed_keys.discard(event.keysym)\n"
            f"{root}.bind('<KeyPress>', _on_key_press)\n"
            f"{root}.bind('<KeyRelease>', _on_key_release)\n"
            f"{root}.focus_set()\n"
        )
        if re.search(r"^def tick\s*\(", text, re.MULTILINE):
            text = re.sub(r"^def tick\s*\(", helper + "\ndef tick(", text, count=1, flags=re.M)
        else:
            text = re.sub(
                r"^([ \t]*\w+\.mainloop\s*\()",
                helper + r"\n\1",
                text,
                count=1,
                flags=re.M,
            )
    return text


def rewrite_bare_after_call(source: str) -> str:
    """3B пишет after(100, tick) вместо root.after(100, tick)."""
    text = source or ""
    if not re.search(r"(?<![.\w])after\s*\(", text):
        return text
    root = "root"
    match = re.search(r"^([A-Za-z_]\w*)\s*=\s*(?:tk\.)?Tk\s*\(", text, re.MULTILINE)
    if match:
        root = match.group(1)
    return re.sub(r"(?<![.\w])after\s*\(", f"{root}.after(", text)


def rewrite_tkinter_gui_mistakes(source: str) -> str:
    text = rewrite_tkinter_comma_import(source)
    text = rewrite_tkinter_winfo_keysym(text)
    return rewrite_bare_after_call(text)


def pip_package_name(module: str) -> str:
    key = (module or "").strip()
    return _PIP_NAME.get(key, key)


def is_missing_dependency_error(detail: str) -> bool:
    return extract_missing_module(detail) is not None


def ensure_requirements_line(project_root: Path, module: str) -> bool:
    package = pip_package_name(module)
    if not package or package.startswith("-"):
        return False
    path = project_root / "requirements.txt"
    line = f"{package}\n"
    if path.is_file():
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(rf"^{re.escape(package)}\b", text, re.I | re.M):
            return False
        path.write_text(text.rstrip() + "\n" + line, encoding="utf-8")
        return True
    path.write_text(f"# CoreX\n{line}", encoding="utf-8")
    return True


_IMPORT_RE = re.compile(
    r"^(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


def parse_top_level_imports(source: str) -> list[str]:
    names: list[str] = []
    for match in _IMPORT_RE.finditer(source or ""):
        name = match.group(1)
        if name and name not in names:
            names.append(name)
    return names


def is_stdlib_module(name: str) -> bool:
    key = (name or "").split(".")[0]
    if not key:
        return True
    stdlib = getattr(sys, "stdlib_module_names", None)
    if stdlib and key in stdlib:
        return True
    return key in {
        "builtins",
        "__future__",
        "tkinter",
        "turtle",
        "sqlite3",
    }


def _is_local_module(project_root: Path | None, name: str) -> bool:
    if not project_root or not name:
        return False
    root = Path(project_root)
    if (root / f"{name}.py").is_file():
        return True
    if (root / name / "__init__.py").is_file():
        return True
    return False


def probe_missing_modules(
    source: str,
    python_exe: str,
    project_root: Path | None = None,
    *,
    timeout: int = 20,
) -> list[str]:
    """Модули из import, которых нет в python_exe (не stdlib, не файлы проекта)."""
    py = (python_exe or "").strip() or sys.executable
    missing: list[str] = []
    for module in parse_top_level_imports(source):
        if is_stdlib_module(module) or _is_local_module(project_root, module):
            continue
        argv = [py, "-c", f"import {module}"]
        kwargs: dict = {
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": timeout,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            completed = subprocess.run(argv, **kwargs)
        except (OSError, subprocess.TimeoutExpired):
            continue
        err = f"{completed.stdout or ''}\n{completed.stderr or ''}"
        if completed.returncode != 0 and (
            extract_missing_module(err) == module or "No module named" in err
        ):
            missing.append(module)
    return missing


def ensure_source_imports(
    project_root: Path,
    source: str,
    *,
    python_exe: str | None = None,
) -> str:
    """Поставить недостающие pip-пакеты. Текст для консоли (может быть пустым)."""
    py = python_exe or sys.executable
    missing = probe_missing_modules(source, py, project_root)
    if not missing:
        return ""
    lines: list[str] = []
    for module in missing:
        package = pip_package_name(module)
        lines.append(f"Ставлю пакет {package} в {py}…\n")
        result = install_module(project_root, module, python_exe=py)
        if result.get("ok"):
            lines.append(f"Установлен {result.get('package')}\n")
        else:
            err = (result.get("error") or "ошибка pip")[:500]
            lines.append(f"Не удалось установить {package}: {err}\n")
    return "".join(lines)


def install_module(
    project_root: Path,
    module: str,
    *,
    python_exe: str | None = None,
    timeout: int = 180,
) -> dict:
    package = pip_package_name(module)
    if not package:
        return {"ok": False, "error": "Пустое имя пакета"}
    py = (python_exe or "").strip() or sys.executable
    argv = [py, "-m", "pip", "install", package]
    kwargs: dict = {
        "cwd": str(project_root),
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
        "env": os.environ.copy(),
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(argv, **kwargs)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc), "package": package}
    output = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
    if completed.returncode != 0:
        return {
            "ok": False,
            "error": output[:1500] or f"pip install {package} failed",
            "package": package,
        }
    return {"ok": True, "package": package, "output": output[:1500]}
