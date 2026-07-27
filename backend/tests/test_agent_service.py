"""TDD: пользовательские агенты в chat/agents/."""

import pytest

from core.agent_service import (
    create_agent,
    delete_agent,
    list_agents,
    list_project_agents,
    load_project_agent,
)
from core.core_x_library import resolve_persona_prompt


def test_create_and_list_project_agent(tmp_path):
    result = create_agent(tmp_path, "QA Бот", "Ты проверяешь код и пишешь тесты.")
    assert result.get("success") is True
    agent = result["agent"]
    assert agent["id"].startswith("agent:")
    assert agent["source"] == "project"

    project = list_project_agents(tmp_path)
    assert len(project) == 1
    assert project[0]["name"] == "QA Бот"
    assert project[0]["category_ru"] == "Мои агенты"


def test_list_agents_merges_library_and_project(tmp_path):
    create_agent(tmp_path, "Мой агент", "Роль агента")
    all_agents = list_agents(tmp_path)
    library_ids = {a["id"] for a in all_agents if a.get("source") == "library"}
    project_ids = {a["id"] for a in all_agents if a.get("source") == "project"}
    assert len(library_ids) >= 5
    assert len(project_ids) == 1


def test_resolve_persona_prompt_uses_project_agent(tmp_path):
    created = create_agent(tmp_path, "Аналитик", "Собирай требования и пиши спецификации.")
    agent_id = created["agent"]["id"]
    name, body = resolve_persona_prompt(tmp_path, agent_id)
    assert name == "Аналитик"
    assert "требования" in body.lower()


def test_delete_project_agent(tmp_path):
    created = create_agent(tmp_path, "Временный", "Промпт")
    agent_id = created["agent"]["id"]
    deleted = delete_agent(tmp_path, agent_id)
    assert deleted.get("success") is True
    assert list_project_agents(tmp_path) == []


def test_cannot_delete_library_agent(tmp_path):
    result = delete_agent(tmp_path, "agent:lead-developer")
    assert result.get("error")


def test_create_agent_requires_name_and_prompt(tmp_path):
    assert create_agent(tmp_path, "", "prompt").get("error")
    assert create_agent(tmp_path, "Name", "").get("error")


def test_load_project_agent_by_stem(tmp_path):
    create_agent(tmp_path, "Dev Helper", "Пиши код аккуратно.")
    name, body = load_project_agent(tmp_path, "agent:dev_helper")
    assert name == "Dev Helper"
    assert "аккуратно" in body
