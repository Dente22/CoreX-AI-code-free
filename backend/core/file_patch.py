"""Построчное редактирование файлов с diff-подсветкой."""

from __future__ import annotations

from typing import Any

VALID_OPS = frozenset(
    {
        "replace",
        "replace_line",
        "insert_after",
        "insert_before",
        "delete",
        "delete_line",
    }
)


def number_file_content(content: str) -> str:
    lines = content.splitlines()
    if not lines:
        return "    1| "
    return "\n".join(f"{index + 1:4d}| {line}" for index, line in enumerate(lines))


def _split_lines(content: str) -> list[str]:
    if not content:
        return []
    return content.splitlines()


def _join_lines(lines: list[str]) -> str:
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _normalize_op_type(raw: str) -> str:
    value = (raw or "").strip().lower()
    if value in {"replace", "replace_line"}:
        return "replace"
    if value in {"delete", "delete_line"}:
        return "delete"
    return value


def apply_file_patch(content: str, operations: list[dict[str, Any]]) -> tuple[str, list[dict], list[str]]:
    """
    Применить операции (лучше по одной за вызов).
    Возвращает: новый текст, highlights для UI, список ошибок.
    """
    lines = _split_lines(content)
    highlights: list[dict] = []
    errors: list[str] = []

    if not operations:
        return content, highlights, ["Нет операций patch"]

    indexed_ops: list[tuple[int, dict]] = []
    for index, op in enumerate(operations):
        if not isinstance(op, dict):
            errors.append(f"Операция {index + 1}: неверный формат")
            continue
        op_type = _normalize_op_type(str(op.get("op") or op.get("operation") or ""))
        if op_type not in VALID_OPS:
            errors.append(f"Операция {index + 1}: неизвестный op '{op_type}'")
            continue
        try:
            line_no = int(op.get("line", 0))
        except (TypeError, ValueError):
            errors.append(f"Операция {index + 1}: line должен быть числом")
            continue
        indexed_ops.append((line_no, {**op, "_type": op_type}))

    for line_no, op in sorted(indexed_ops, key=lambda item: item[0], reverse=True):
        op_type = op["_type"]
        new_text = str(op.get("content", ""))

        try:
            if op_type == "replace":
                if line_no < 1 or line_no > len(lines):
                    errors.append(f"replace: строка {line_no} вне диапазона 1..{len(lines)}")
                    continue
                idx = line_no - 1
                old_line = lines[idx]
                new_line = new_text.rstrip("\r")
                lines[idx] = new_line
                if old_line != new_line:
                    highlights.append(
                        {
                            "line": line_no,
                            "type": "modify",
                            "old": old_line,
                            "new": new_line,
                        }
                    )

            elif op_type == "insert_after":
                insert_idx = line_no if line_no >= 1 else 0
                if line_no >= 1 and line_no > len(lines):
                    errors.append(f"insert_after: строка {line_no} вне диапазона")
                    continue
                if line_no >= 1:
                    insert_idx = line_no
                for offset, piece in enumerate(new_text.splitlines() or [""]):
                    lines.insert(insert_idx + offset, piece.rstrip("\r"))
                    highlights.append(
                        {
                            "line": insert_idx + offset + 1,
                            "type": "add",
                            "new": piece.rstrip("\r"),
                        }
                    )

            elif op_type == "insert_before":
                if line_no < 1:
                    insert_idx = 0
                elif line_no > len(lines) + 1:
                    errors.append(f"insert_before: строка {line_no} вне диапазона")
                    continue
                else:
                    insert_idx = line_no - 1
                for offset, piece in enumerate(new_text.splitlines() or [""]):
                    lines.insert(insert_idx + offset, piece.rstrip("\r"))
                    highlights.append(
                        {
                            "line": insert_idx + offset + 1,
                            "type": "add",
                            "new": piece.rstrip("\r"),
                        }
                    )

            elif op_type == "delete":
                if line_no < 1 or line_no > len(lines):
                    errors.append(f"delete: строка {line_no} вне диапазона 1..{len(lines)}")
                    continue
                idx = line_no - 1
                old_line = lines[idx]
                del lines[idx]
                highlights.append(
                    {
                        "line": min(line_no, max(len(lines), 1)),
                        "type": "delete",
                        "old": old_line,
                        "displayLine": min(line_no, max(len(lines), 1)),
                    }
                )
        except Exception as exc:
            errors.append(f"{op_type} @ {line_no}: {exc}")

    if errors and not highlights:
        return content, highlights, errors

    new_content = _join_lines(lines) if lines else ""
    if highlights:
        highlights.sort(key=lambda item: item.get("line", 0))
    return new_content, highlights, errors
