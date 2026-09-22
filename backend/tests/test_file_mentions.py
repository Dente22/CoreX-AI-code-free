import pytest

from core.file_mentions import expand_file_mentions, extract_mention_paths
from core.file_service import FileService


def test_extract_folder_mention():
    assert extract_mention_paths("создай змейку с игровым окном /test") == ["test"]
    assert extract_mention_paths("создай змейку /test`") == ["test"]
    assert extract_mention_paths("что делает /main.py") == ["main.py"]
    assert extract_mention_paths("create snake in /arcade/snake.py") == ["arcade/snake.py"]


@pytest.mark.asyncio
async def test_folder_mention_is_write_dest_not_attachment(tmp_path):
    (tmp_path / "test").mkdir()
    (tmp_path / "main.py").write_text("mines = 8\n", encoding="utf-8")
    fs = FileService(None, str(tmp_path))
    task = "создай змейку с игровым окном /test"
    expanded, attached = await expand_file_mentions(task, fs)
    assert attached == []
    assert expanded == task
    assert "ошибка чтения" not in expanded
    assert "mines" not in expanded


@pytest.mark.asyncio
async def test_edit_mention_attaches_existing_file(tmp_path):
    (tmp_path / "main.py").write_text("mines = 8\n", encoding="utf-8")
    fs = FileService(None, str(tmp_path))
    expanded, attached = await expand_file_mentions("исправь /main.py", fs)
    assert attached == ["main.py"]
    assert "mines = 8" in expanded


@pytest.mark.asyncio
async def test_read_mention_attaches_existing_file(tmp_path):
    (tmp_path / "main.py").write_text("print('hi')\n", encoding="utf-8")
    fs = FileService(None, str(tmp_path))
    expanded, attached = await expand_file_mentions("что делает /main.py", fs)
    assert attached == ["main.py"]
    assert "print('hi')" in expanded


@pytest.mark.asyncio
async def test_create_in_folder_does_not_attach_other_file(tmp_path):
    (tmp_path / "test1").mkdir()
    (tmp_path / "snake.py").write_text("import pygame\n", encoding="utf-8")
    fs = FileService(None, str(tmp_path))
    task = "/snake.py создай мне сапёра с игровым окном в /test1"
    expanded, attached = await expand_file_mentions(task, fs)
    assert attached == []
    assert "import pygame" not in expanded
    assert expanded == task
