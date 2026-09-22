from core.pipeline_runner import clip_pipeline_summary, compact_pipeline_final


def test_clip_pipeline_summary_drops_html_dump():
    dumped = (
        "Старший разработчик: Can't initialize prompt toolkit\n"
        "```html\n<!DOCTYPE html>\n<html lang=\"ru\">\n"
    )
    assert clip_pipeline_summary(dumped) == "Старший разработчик: готово"


def test_compact_pipeline_final_is_short():
    final = compact_pipeline_final(
        [
            "UI/UX-дизайнер: Design сохранён на диск (design-system/MASTER.md)",
            "Старший разработчик:\n```html\n<!DOCTYPE html>",
            "QA-инженер: этап завершён",
        ]
    )
    assert final.startswith("Конвейер готов.")
    assert "<!DOCTYPE" not in final
    assert "```" not in final
    assert "Нагрузка" not in final
    assert "QA-инженер" in final
