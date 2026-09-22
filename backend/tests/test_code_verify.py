import pytest

from core.code_verify import looks_like_interactive_python, verify_python_file


def test_console_snake_is_interactive():
    src = (
        "snake = [[10, 5]]\n"
        "direction = 'RIGHT'\n"
        "while True:\n"
        "    if key == 'A':\n"
        "        direction = 'LEFT'\n"
    )
    assert looks_like_interactive_python(src) is True


def test_plain_script_is_not_interactive():
    assert looks_like_interactive_python("print(1)\n") is False


def test_input_console_game_is_interactive():
    src = (
        "def play():\n"
        "    rows = int(input('Enter number of rows: '))\n"
        "    print(rows)\n"
    )
    assert looks_like_interactive_python(src) is True


@pytest.mark.asyncio
async def test_verify_skips_smoke_run_for_input_game(tmp_path):
    (tmp_path / "main.py").write_text(
        "board = [['.']]\n"
        "row = int(input('Enter row: '))\n"
        "print(row)\n",
        encoding="utf-8",
    )
    result = await verify_python_file(tmp_path, "main.py")
    assert result["ok"] is True
    assert result["phase"] == "syntax"


@pytest.mark.asyncio
async def test_verify_skips_smoke_run_for_game_loop(tmp_path):
    (tmp_path / "main.py").write_text(
        "snake = [[1, 1]]\n"
        "while True:\n"
        "    if key == 'A':\n"
        "        pass\n",
        encoding="utf-8",
    )
    result = await verify_python_file(tmp_path, "main.py")
    assert result["ok"] is True
    assert result["phase"] == "syntax"
    assert "не запускаем" in (result.get("detail") or "").lower() or "OK" in result.get("detail", "")


@pytest.mark.asyncio
async def test_verify_interactive_still_detects_missing_import(tmp_path):
    (tmp_path / "main.py").write_text(
        "import corex_no_such_pkg_xyz\n"
        "row = int(input('Enter row: '))\n",
        encoding="utf-8",
    )
    result = await verify_python_file(tmp_path, "main.py")
    assert result["ok"] is False
    assert result["phase"] == "dependency"
    assert result["missing_module"] == "corex_no_such_pkg_xyz"


@pytest.mark.asyncio
async def test_smoke_run_nameerror_is_failure(tmp_path):
    from core.code_verify import smoke_run_python

    (tmp_path / "game.py").write_text("print(definitely_missing)\n", encoding="utf-8")
    result = await smoke_run_python(tmp_path, "game.py", timeout=5)
    assert result["ok"] is False
    detail = result.get("detail") or ""
    assert "Traceback" in detail or "definitely_missing" in detail


@pytest.mark.asyncio
async def test_smoke_run_hang_without_traceback_is_ok(tmp_path):
    from core.code_verify import smoke_run_python

    (tmp_path / "game.py").write_text("while True:\n    pass\n", encoding="utf-8")
    result = await smoke_run_python(tmp_path, "game.py", timeout=1)
    assert result["ok"] is True

