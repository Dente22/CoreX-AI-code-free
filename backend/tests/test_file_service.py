import pytest

from core.file_service import FileService


@pytest.mark.asyncio
async def test_list_directory_hides_chat_folder(tmp_path):
    (tmp_path / "chat").mkdir()
    (tmp_path / "chat" / "project_memory.md").write_text("secret\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "chat").mkdir()
    (tmp_path / "src" / "chat" / "notes.md").write_text("ok\n", encoding="utf-8")

    service = FileService(None, str(tmp_path), use_mcp=False)
    root = await service.list_directory(".")
    names = {item["name"] for item in root["contents"]}
    assert "chat" not in names
    assert "app.py" in names
    assert "src" in names

    nested = await service.list_directory("chat")
    assert nested["contents"] == []

    src = await service.list_directory("src")
    src_names = {item["name"] for item in src["contents"]}
    assert "chat" in src_names


@pytest.mark.asyncio
async def test_append_file_creates_then_extends(tmp_path):
    service = FileService(None, str(tmp_path), use_mcp=False)
    first = await service.append_file("main.py", "import pygame\n")
    assert first.get("success") is True
    second = await service.append_file("main.py", "pygame.init()\n")
    assert second.get("success") is True
    data = await service.read_file("main.py")
    assert data["content"] == "import pygame\npygame.init()\n"


@pytest.mark.asyncio
async def test_append_file_rejects_protocol_instruction(tmp_path):
    service = FileService(None, str(tmp_path), use_mcp=False)
    await service.write_file("main.py", "import pygame\n")
    result = await service.append_file("main.py", "fence with the NEXT chunk only.\n")
    assert result.get("error")
    data = await service.read_file("main.py")
    assert "NEXT chunk" not in data["content"]


@pytest.mark.asyncio
async def test_write_file_rejects_two_print_stub(tmp_path):
    service = FileService(None, str(tmp_path), use_mcp=False)
    result = await service.write_file("main.py", 'print("a")\nprint("b")\n')
    assert result.get("error")
    assert "Заглушка" in result["error"]
    assert not (tmp_path / "main.py").exists()


@pytest.mark.asyncio
async def test_write_file_drops_second_gameloop(tmp_path):
    service = FileService(None, str(tmp_path), use_mcp=False)
    body = (
        "import pygame\n\n"
        "def gameLoop():\n"
        "    game_over = False\n"
        "    pygame.quit()\n\n"
        "gameLoop()\n\n"
        "def gameLoop():\n"
        "    return\n"
    )
    result = await service.write_file("main.py", body)
    assert result.get("success") is True
    data = await service.read_file("main.py")
    assert data["content"].count("def gameLoop") == 1


@pytest.mark.asyncio
async def test_write_file_refuses_project_root(tmp_path):
    service = FileService(None, str(tmp_path), use_mcp=False)
    result = await service.write_file(".", "# oops\n")
    assert result.get("error")
    assert "directory" in result["error"].lower()


@pytest.mark.asyncio
async def test_write_file_refuses_existing_directory(tmp_path):
    (tmp_path / "src").mkdir()
    service = FileService(None, str(tmp_path), use_mcp=False)
    result = await service.write_file("src", "print(1)\n")
    assert result.get("error")
    assert "directory" in result["error"].lower()


@pytest.mark.asyncio
async def test_write_file_refuses_name_without_extension(tmp_path):
    service = FileService(None, str(tmp_path), use_mcp=False)
    result = await service.write_file("test1", "print(1)\n")
    assert result.get("error")
    assert "без расширения" in result["error"]
    assert not (tmp_path / "test1").exists()
    ok = await service.write_file("test1/app.py", "print(1)\n")
    assert ok.get("success") is True
    assert (tmp_path / "test1" / "app.py").is_file()


@pytest.mark.asyncio
async def test_write_inside_folder_replaces_extensionless_file(tmp_path):
    (tmp_path / "test1").write_text("oops\n", encoding="utf-8")
    service = FileService(None, str(tmp_path), use_mcp=False)
    result = await service.write_file("test1/minesweeper.py", "print(1)\n")
    assert result.get("success") is True
    assert (tmp_path / "test1").is_dir()
    assert (tmp_path / "test1" / "minesweeper.py").read_text(encoding="utf-8") == "print(1)\n"
