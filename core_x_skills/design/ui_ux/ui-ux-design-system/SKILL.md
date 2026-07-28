---
name: ui-ux-design-system
description: Генератор design system из UI/UX Pro Max — палитры, типографика, стили, anti-patterns с reasoning. Сохранение MASTER.md + page overrides.
---

# UI/UX Design System Generator

Скилл для **создания полной дизайн-системы** под продукт. Использует reasoning engine из `ui-ux-pro-max`.

**Скрипт:** `core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py`

## Workflow

1. Извлеки: тип продукта, индустрию, аудиторию, ключевые слова стиля, целевой стек.
2. Запусти design system:

```bash
python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "<product> <industry> <style keywords>" --design-system -p "<Project Name>"
```

3. Для markdown-формата добавь `-f markdown`.
4. Настрой «дизайн-ручки» при необходимости:

```bash
python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "analytics dashboard enterprise" --design-system --variance 5 --motion 4 --density 8 -p "Ops Console"
```

5. Сохрани в проект для иерархического использования:

```bash
python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "<query>" --design-system --persist -p "<Project Name>"
```

Для страницы:
```bash
python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "<query>" --design-system --persist -p "<Project>" --page "dashboard"
```

## Иерархия Master + Overrides

При реализации страницы:
1. Проверь `design-system/pages/<page>.md` — если есть, его правила **перекрывают** MASTER.
2. Иначе используй только `design-system/MASTER.md`.

## Выход агента

Передай разработчику:
- Pattern и style с обоснованием
- Color tokens (primary, secondary, accent, surface, text)
- Typography (heading + body fonts)
- Spacing scale и effects
- Anti-patterns — что **не** делать
- Ссылку на MASTER.md если использовал `--persist`
