---
name: ui-ux-pro-max
description: Полный гайд UI/UX для web, mobile и desktop. 67 стилей, 161 палитр, 57 пар шрифтов, 99 UX-гайдлайнов, 25 типов графиков, 22 стека. Поисковая база с приоритетными рекомендациями.
---

# UI/UX Pro Max

Комплексный дизайн-гайд для web, mobile и desktop. Содержит стили, палитры, типографику, UX-правила и стек-специфичные паттерны. Используй поисковую базу через `run_command`.

**Путь к скрипту поиска (от корня CoreX):**
`core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py`

На Windows: `python`, не `python3`.

---

## Когда активировать

| Сценарий | Примеры | С чего начать |
|----------|---------|---------------|
| Новый проект / страница | landing page, dashboard | Шаг 1 → Шаг 2 (design system) |
| Новый компонент | pricing card, modal | Шаг 3 (domain search) |
| Стиль / цвет / шрифт | «Какой стиль для fintech?» | Шаг 2 (design system) |
| Ревью UI | «Проверь UX», accessibility | Чеклист ниже |
| Баг UI | hover сломан, layout shift | Чеклист → нужная секция |
| Dark mode | «Добавь тёмную тему» | `--domain style "dark mode"` |
| Графики | analytics dashboard | `--domain chart` |
| Стек | React performance, SwiftUI | Шаг 4 (stack search) |

---

## Шаг 1: Анализ требований

Извлеки из запроса:
- **Тип продукта**: entertainment, tool, productivity или гибрид
- **Аудитория**: возраст, контекст (commute, work, leisure)
- **Ключевые слова стиля**: minimal, vibrant, dark mode, content-first
- **Стек**: React, Next.js, Vue, React Native, Flutter, Tailwind и др.

---

## Шаг 2: Design System (ОБЯЗАТЕЛЬНО)

Всегда начинай с `--design-system`:

```bash
python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "<product_type> <industry> <keywords>" --design-system -p "Project Name"
```

Возвращает: pattern, style, colors, typography, effects, anti-patterns.

**Сохранить в проект (Master + Overrides):**
```bash
python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "<query>" --design-system --persist -p "Project Name"
```

Создаёт `design-system/MASTER.md` и `design-system/pages/<page>.md`.

**Design Dials (1–10):**
```bash
python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "<query>" --design-system --variance 8 --motion 7 --density 8 -p "Ops Console"
```

| Dial | Низкий (1–3) | Средний (4–7) | Высокий (8–10) |
|------|--------------|---------------|----------------|
| `--variance` | Минимализм | Сбалансированный | Bold / asymmetric |
| `--motion` | Subtle micro | Standard scroll | Complex choreography |
| `--density` | Spacious | Standard | Dense dashboard |

---

## Шаг 3: Детальный поиск по доменам

```bash
python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "<keyword>" --domain <domain> [-n <max_results>]
```

| Нужно | Domain | Пример |
|-------|--------|--------|
| Тип продукта | `product` | `--domain product "saas fintech"` |
| Стили | `style` | `--domain style "glassmorphism dark"` |
| Палитры | `color` | `--domain color "fintech vibrant"` |
| Шрифты | `typography` | `--domain typography "modern professional"` |
| Графики | `chart` | `--domain chart "real-time dashboard"` |
| UX | `ux` | `--domain ux "animation accessibility"` |
| Landing | `landing` | `--domain landing "hero social-proof"` |
| React perf | `react` | `--domain react "memo list rerender"` |
| A11y | `web` | `--domain web "accessibility touch safe-areas"` |
| CSS keywords | `prompt` | `--domain prompt "minimalism"` |

---

## Шаг 4: Стек-гайдлайны

```bash
python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "<keyword>" --stack <stack>
```

Доступные стеки: `react`, `nextjs`, `vue`, `nuxtjs`, `nuxt-ui`, `svelte`, `astro`, `shadcn`, `html-tailwind`, `angular`, `laravel`, `swiftui`, `flutter`, `jetpack-compose`, `react-native`, `threejs`, `javafx`, `wpf`, `winui`, `avalonia`, `uno`, `uwp`.

---

## Pre-Delivery Checklist

### Visual
- [ ] Нет emoji как иконок — только SVG/vector
- [ ] Единое семейство иконок (Phosphor, Heroicons)
- [ ] Pressed-state не сдвигает layout
- [ ] Semantic color tokens, не hardcoded hex

### Interaction
- [ ] Touch targets ≥44pt (iOS) / ≥48dp (Android)
- [ ] Micro-interactions 150–300ms
- [ ] Disabled states видимы и не кликабельны
- [ ] Screen reader focus order = visual order

### Light/Dark
- [ ] Text contrast ≥4.5:1 (primary), ≥3:1 (secondary)
- [ ] Borders/states видны в обеих темах
- [ ] Modal scrim 40–60% opacity

### Layout
- [ ] Safe areas для headers/tab bars
- [ ] Scroll content не скрыт за fixed bars
- [ ] 4/8dp spacing rhythm
- [ ] Проверено на 375px, landscape, tablet

### Accessibility
- [ ] Labels на иконках и полях форм
- [ ] Color не единственный индикатор
- [ ] Reduced motion и Dynamic Type поддержаны

---

## Профессиональные правила UI

- Иконки: Phosphor (`@phosphor-icons/react`) или Heroicons — не emoji
- Vector-only assets, не raster PNG для иконок
- Стабильные interaction states без layout shift
- Token-driven theming для light/dark
- 8dp spacing rhythm, adaptive gutters по breakpoint
