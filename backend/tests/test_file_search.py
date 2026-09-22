from core.file_search import search_project_files


def test_search_finds_line_and_skips_node_modules(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.ts").write_text("export const title = 'CoreX search';\n", encoding="utf-8")
    hidden = tmp_path / "node_modules" / "pkg"
    hidden.mkdir(parents=True)
    (hidden / "index.js").write_text("export const title = 'CoreX search';\n", encoding="utf-8")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG CoreX search")

    result = search_project_files(tmp_path, "CoreX search")
    assert result["success"] is True
    assert len(result["matches"]) == 1
    hit = result["matches"][0]
    assert hit["path"] == "src/app.ts"
    assert hit["line"] == 1
    assert "CoreX search" in hit["text"]


def test_search_requires_two_characters(tmp_path):
    (tmp_path / "a.txt").write_text("ab", encoding="utf-8")
    result = search_project_files(tmp_path, "a")
    assert result["matches"] == []


def test_search_is_case_insensitive(tmp_path):
    (tmp_path / "readme.md").write_text("Hello WORLD\n", encoding="utf-8")
    result = search_project_files(tmp_path, "world")
    assert result["matches"][0]["line"] == 1


def test_search_skips_chat_folder(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.ts").write_text("export const title = 'visible hit';\n", encoding="utf-8")
    hidden = tmp_path / "chat" / "memory"
    hidden.mkdir(parents=True)
    (hidden / "project_memory.md").write_text("visible hit in memory\n", encoding="utf-8")

    result = search_project_files(tmp_path, "visible hit")
    assert result["success"] is True
    assert [hit["path"] for hit in result["matches"]] == ["src/app.ts"]
