"""TDD: design handoff дизайнер → разработчик."""

from __future__ import annotations

from core.design_handoff import (
    collect_design_bundle,
    ensure_design_scaffold,
    format_design_bundle_for_prompt,
    starter_master_md,
    validate_design_handoff,
)


def test_validate_fails_when_design_files_missing(tmp_path):
    result = validate_design_handoff(tmp_path, app_root=tmp_path)
    assert result.ok is False
    assert any("MASTER.md" in path for path in result.missing)
    assert any("pages/index.md" in path for path in result.missing)


def test_ensure_scaffold_creates_required_files(tmp_path):
    created = ensure_design_scaffold(tmp_path, user_task="Сайт компьютерного клуба", app_root=tmp_path)
    assert any("MASTER.md" in path for path in created)
    assert any("pages/index.md" in path for path in created)
    result = validate_design_handoff(tmp_path, app_root=tmp_path)
    assert result.ok is True


def test_collect_and_format_bundle(tmp_path):
    ensure_design_scaffold(tmp_path, user_task="Landing page", app_root=tmp_path)
    bundle = collect_design_bundle(tmp_path, app_root=tmp_path)
    assert any("MASTER.md" in key for key in bundle)
    prompt = format_design_bundle_for_prompt(bundle)
    assert "FILE:" in prompt
    assert "Design Spec" in prompt


def test_starter_master_has_brand_colors():
    text = starter_master_md(user_task="Test site")
    assert "#9A5EFF" in text
    assert "#00D2FF" in text
