"""TDD: прозрачный фон иконки."""

from pathlib import Path

import pytest

pytest.importorskip("PIL")

from PIL import Image

# scripts лежит в frontend/scripts
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "frontend" / "scripts" / "icon_transparent.py"


@pytest.fixture
def icon_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("icon_transparent", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_remove_white_matte_makes_corners_transparent(icon_module):
    image = Image.new("RGB", (64, 64), (255, 255, 255))
    for x in range(20, 44):
        for y in range(20, 44):
            image.putpixel((x, y), (12, 22, 46))

    result = icon_module.remove_white_matte(image)
    assert result.getpixel((0, 0))[3] == 0
    assert result.getpixel((32, 32))[3] == 255
