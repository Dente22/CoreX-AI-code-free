"""Авто-исправление и заготовки при ошибках проверки кода."""

from __future__ import annotations

import re
from pathlib import Path

from core.python_deps import ensure_requirements_line, extract_missing_module

NAME_ERROR_RE = re.compile(
    r"NameError:\s*name\s+['\"]([^'\"]+)['\"]\s+is not defined",
    re.IGNORECASE,
)
MODULE_ERROR_RE = re.compile(
    r"ModuleNotFoundError:\s*No module named\s+['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
FILE_MISSING_RE = re.compile(
    r"(?:FileNotFoundError|файл не найден)[:\s]*['\"]?([^\s'\":]+)['\"]?",
    re.IGNORECASE,
)
SYNTAX_LINE_RE = re.compile(
    r'File\s+"([^"]+)",\s+line\s+(\d+)',
    re.IGNORECASE,
)

# Частые имена в pygame / играх
_PYGAME_STUBS: dict[str, str] = {
    "snake_block": "snake_block = 20",
    "snake_size": "snake_block = 20",
    "block_size": "block_size = 20",
    "width": "width = 800",
    "height": "height = 600",
    "fps": "fps = 10",
    "clock": "clock = pygame.time.Clock()",
    "gameDisplay": "gameDisplay = pygame.display.set_mode((width, height))",
    "display": "display = pygame.display.set_mode((800, 600))",
    "screen": "screen = pygame.display.set_mode((800, 600))",
    "white": "white = (255, 255, 255)",
    "black": "black = (0, 0, 0)",
    "red": "red = (255, 0, 0)",
    "green": "green = (0, 255, 0)",
    "blue": "blue = (0, 0, 255)",
}


def _resolve(project_root: Path, rel_path: str) -> Path | None:
    root = project_root.resolve()
    normalized = rel_path.replace("\\", "/").lstrip("/")
    target = (root / normalized).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target


def _stub_for_name(name: str, source_text: str) -> str:
    if name in _PYGAME_STUBS:
        return _PYGAME_STUBS[name]
    if "pygame" in source_text.lower() and name.endswith("_block"):
        return f"{name} = 20"
    if name.isupper():
        return f"{name} = 0  # TODO: задайте значение"
    if name.startswith(("get_", "is_", "has_", "create_", "draw_", "update_", "run_")):
        return (
            f"def {name}(*args, **kwargs):\n"
            f"    \"\"\"TODO: CoreX заготовка — реализуйте функцию.\"\"\"\n"
            f"    raise NotImplementedError('{name}')"
        )
    return f"{name} = None  # TODO: CoreX заготовка — задайте значение"


def _insert_stub_lines(content: str, stub_lines: list[str]) -> str:
    lines = content.splitlines()
    insert_at = 0
    shebang = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if index == 0 and stripped.startswith("#!"):
            shebang = True
            continue
        if shebang and index == 1 and not stripped:
            insert_at = 2
            continue
        if stripped.startswith(("import ", "from ")) or stripped == "":
            insert_at = index + 1
            continue
        break

    block = "\n".join(stub_lines)
    if insert_at >= len(lines):
        return content.rstrip() + "\n\n# --- CoreX auto-stub ---\n" + block + "\n"
    head = lines[:insert_at]
    tail = lines[insert_at:]
    return "\n".join(head) + "\n\n# --- CoreX auto-stub ---\n" + block + "\n" + "\n".join(tail)


def _name_already_defined(content: str, name: str) -> bool:
    patterns = [
        re.compile(rf"^\s*{re.escape(name)}\s*=", re.MULTILINE),
        re.compile(rf"^\s*def\s+{re.escape(name)}\s*\(", re.MULTILINE),
        re.compile(rf"^\s*class\s+{re.escape(name)}\s*[\(:]", re.MULTILINE),
    ]
    return any(pattern.search(content) for pattern in patterns)


def _default_file_template(rel_path: str) -> str:
    name = Path(rel_path).name
    if name == "main.py":
        return (
            '"""Точка входа проекта — заготовка CoreX."""\n\n'
            "def main() -> None:\n"
            '    """TODO: реализуйте логику.\"\"\"\n'
            "    print('Hello from main.py')\n\n\n"
            'if __name__ == "__main__":\n'
            "    main()\n"
        )
    if name == "requirements.txt":
        return "# TODO: зависимости проекта\n"
    if rel_path.endswith(".py"):
        stem = Path(rel_path).stem
        return (
            f'"""Модуль {stem} — заготовка CoreX."""\n\n'
            f"# TODO: реализуйте {stem}\n"
        )
    if rel_path.endswith((".js", ".ts", ".tsx")):
        return f"// TODO: {name}\nexport {{}};\n"
    return f"// TODO: {name}\n"


def parse_error_hints(error_text: str) -> dict:
    text = error_text or ""
    missing_names = NAME_ERROR_RE.findall(text)
    missing_modules = MODULE_ERROR_RE.findall(text)
    extra_module = extract_missing_module(text)
    if extra_module and extra_module not in missing_modules:
        missing_modules.append(extra_module)
    missing_files = FILE_MISSING_RE.findall(text)
    syntax_files = SYNTAX_LINE_RE.findall(text)
    return {
        "missing_names": list(dict.fromkeys(missing_names)),
        "missing_modules": list(dict.fromkeys(missing_modules)),
        "missing_files": list(dict.fromkeys(missing_files)),
        "syntax_files": syntax_files,
    }


def remediate_python_error(
    project_root: Path,
    source_rel_path: str,
    error_text: str,
    *,
    mode: str = "auto",
) -> dict:
    """
    mode: auto | fix | stub
    - fix: попытка вставить недостающие определения
    - stub: только заготовки TODO
    """
    hints = parse_error_hints(error_text)
    source_rel = source_rel_path.replace("\\", "/").lstrip("/")
    source_path = _resolve(project_root, source_rel)

    if source_path and source_path.is_file():
        content = source_path.read_text(encoding="utf-8")
    else:
        content = ""
        if not source_path:
            source_path = _resolve(project_root, source_rel)
        if not source_path:
            return {"ok": False, "action": "none", "message": "Путь вне проекта"}

    actions: list[str] = []
    changed = False

    if source_path.is_dir() or source_rel in (".", "", "./"):
        return {
            "ok": False,
            "action": "none",
            "path": source_rel,
            "message": "Нельзя записать в папку проекта — укажите файл (например main.py)",
            "hints": hints,
        }

    if not source_path.is_file():
        template = _default_file_template(source_rel)
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(template, encoding="utf-8")
        content = template
        actions.append(f"создан файл {source_rel}")
        changed = True

    stub_lines: list[str] = []
    for name in hints["missing_names"]:
        if _name_already_defined(content, name):
            continue
        stub = _stub_for_name(name, content)
        stub_lines.append(stub)
        actions.append(f"добавлена заготовка для {name}")

    if stub_lines:
        new_content = _insert_stub_lines(content, stub_lines)
        if new_content != content:
            source_path.write_text(new_content, encoding="utf-8")
            content = new_content
            changed = True

    for module in hints["missing_modules"]:
        if ensure_requirements_line(project_root, module):
            actions.append(f"добавлен {module} в requirements.txt")
            changed = True

    for raw_missing in hints["missing_files"]:
        missing_rel = raw_missing.replace("\\", "/").lstrip("/")
        if missing_rel == source_rel or missing_rel in (".", "", "./"):
            continue
        missing_path = _resolve(project_root, missing_rel)
        if missing_path and missing_path.is_dir():
            continue
        if missing_path and not missing_path.is_file():
            missing_path.parent.mkdir(parents=True, exist_ok=True)
            missing_path.write_text(_default_file_template(missing_rel), encoding="utf-8")
            actions.append(f"создан {missing_rel}")
            changed = True

    if not changed:
        if mode == "stub" and not source_path.is_file():
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_text(_default_file_template(source_rel), encoding="utf-8")
            actions.append(f"создана заготовка {source_rel}")
            changed = True
        else:
            return {
                "ok": False,
                "action": "none",
                "path": source_rel,
                "message": "Не удалось автоматически исправить — отредактируйте вручную",
                "hints": hints,
            }

    return {
        "ok": True,
        "action": "fixed" if hints["missing_names"] else "stub_created",
        "path": source_rel,
        "message": "; ".join(actions) or f"Обновлён {source_rel}",
        "hints": hints,
    }
