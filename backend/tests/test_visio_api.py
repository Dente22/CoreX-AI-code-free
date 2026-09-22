from core import visio_service, ws_server


def test_ws_server_imports_visio_payload():
    assert ws_server.get_visio_payload is visio_service.get_visio_payload


def test_visio_payload_for_empty_project(tmp_path):
    payload = visio_service.get_visio_payload(tmp_path)
    assert payload["success"] is True
    assert "diagrams" in payload
    assert payload["project_name"] == tmp_path.name


def test_visio_payload_does_not_expose_chat_paths(tmp_path):
    visio = tmp_path / "chat" / "visio"
    visio.mkdir(parents=True)
    (visio / "workflow.mmd").write_text("flowchart TB\n    a[A]\n", encoding="utf-8")
    (tmp_path / "chat" / "project_memory.md").write_text("# Архитектура\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print(1)\n", encoding="utf-8")

    payload = visio_service.get_visio_payload(tmp_path)
    blob = str(payload)
    assert "chat/" not in blob
    assert payload["paths"]["directory"] == ""
    memory = next(item for item in payload["diagrams"] if item["id"] == "memory")
    assert memory["path"] == ""
    assert "Память проекта" in memory["source"]
