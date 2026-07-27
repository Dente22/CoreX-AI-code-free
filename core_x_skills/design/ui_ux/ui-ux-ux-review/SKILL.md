---
name: ui-ux-ux-review
description: UX-ревью и чеклисты из UI/UX Pro Max — accessibility, interaction, layout, 99 UX-гайдлайнов.
---

# UI/UX Review & Guidelines

Скилл для **ревью существующего UI** и валидации перед сдачей.

**Скрипт:** `core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py`

## Поиск UX-гайдлайнов

```bash
python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "animation accessibility z-index loading" --domain ux

python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "form validation focus management" --domain ux

python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "mobile-first breakpoint" --domain ux
```

## Чеклист перед сдачей

### Visual Quality
- [ ] Нет emoji как иконок
- [ ] Единое семейство иконок и stroke width
- [ ] Pressed-state без layout jitter
- [ ] Semantic theme tokens

### Interaction
- [ ] Tap feedback 80–150ms
- [ ] Touch targets ≥44×44pt / ≥48×48dp
- [ ] Micro-interactions 150–300ms
- [ ] Disabled states явные
- [ ] Screen reader order = visual order

### Light/Dark Mode
- [ ] Contrast primary ≥4.5:1, secondary ≥3:1
- [ ] Borders видны в обеих темах
- [ ] Modal scrim 40–60%

### Layout
- [ ] Safe areas (notch, gesture bar)
- [ ] Scroll не скрыт за sticky bars
- [ ] 4/8dp spacing rhythm
- [ ] Тест: 375px phone, landscape, tablet

### Accessibility
- [ ] accessibilityLabel на иконках
- [ ] Form labels + error messages
- [ ] Color не единственный индикатор
- [ ] Reduced motion + Dynamic Type

## Формат отчёта ревью

1. **Критично** — блокирует релиз (a11y, contrast, broken interaction)
2. **Важно** — снижает perceived quality (spacing, icon inconsistency)
3. **Рекомендация** — polish (motion, micro-copy)

Для каждого пункта: что не так → где → как исправить.
