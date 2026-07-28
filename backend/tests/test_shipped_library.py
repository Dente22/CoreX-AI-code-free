"""TDD: библиотека агентов/команд должна быть в установке CoreX."""

from core.core_x_library import (
    AGENTS_ROOT,
    COREX_ROOT,
    TEAMS_ROOT,
    list_library_agents,
    list_library_teams,
    resolve_corex_root,
)


def test_resolve_corex_root_finds_agents_folder():
    root = resolve_corex_root()
    assert (root / "core_x_agents").is_dir()


def test_agents_library_not_empty():
    agents = list_library_agents()
    assert len(agents) >= 5
    assert any(agent["id"] == "agent:qa-engineer" for agent in agents)


def test_teams_library_not_empty():
    teams = list_library_teams()
    assert len(teams) >= 2
    assert any(team.get("id") == "lib-team:dev-team" for team in teams)


def test_roots_under_corex_root():
    assert AGENTS_ROOT == COREX_ROOT / "core_x_agents"
    assert TEAMS_ROOT == AGENTS_ROOT / "teams"
    assert TEAMS_ROOT.is_dir()
