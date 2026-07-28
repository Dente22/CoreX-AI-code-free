---
name: ui-ux-style-colors
description: Подбор стилей, цветовых палитр и типографики из UI/UX Pro Max — 67 стилей, 161 палитра, 57 пар шрифтов.
---

# UI/UX Style, Colors & Typography

Скилл для **выбора визуального языка**: стиль, палитра, шрифты.

**Скрипт:** `core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py`

## Поиск по доменам

```bash
# Стили (glassmorphism, minimalism, brutalism, dark mode)
python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "fintech minimal dark" --domain style

# Палитры по типу продукта
python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "saas healthcare" --domain color

# Пары шрифтов
python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "elegant professional" --domain typography

# CSS/AI prompt keywords для стиля
python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "glassmorphism" --domain prompt
```

## Правила выбора

- Комбинируй **product + industry + tone**: `"entertainment social vibrant"` лучше чем просто `"app"`.
- Для dark mode — отдельный поиск `--domain style "dark mode"` и проверка contrast pairs.
- Палитра должна включать semantic tokens: primary, on-primary, surface, muted, destructive, border.
- Типографика: heading font + body font, не более 2 семейств.

## Dark Mode

- Primary text contrast ≥4.5:1 на тёмных surface
- Secondary text ≥3:1
- Borders и dividers видны в обеих темах
- Не копируй light-mode hex в dark без пересчёта

## Иконки

- Phosphor (`@phosphor-icons/react`) — основная библиотека
- Heroicons — запасной вариант, сохраняй stroke/style consistency
- Никаких emoji как structural icons
