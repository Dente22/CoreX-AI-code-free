---
name: ui-ux-stack-patterns
description: Стек-специфичные UI-паттерны из UI/UX Pro Max — React, Next.js, Vue, Flutter, SwiftUI, Tailwind, shadcn и 15+ стеков.
---

# UI/UX Stack Patterns

Скилл для **реализации UI на конкретном стеке** с best practices из базы ui-ux-pro-max.

**Скрипт:** `core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py`

## Поиск по стеку

```bash
python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "list performance navigation" --stack react-native

python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "app router server components" --stack nextjs

python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "utility responsive layout" --stack html-tailwind

python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "composition primitives" --stack shadcn
```

## Доступные стеки

| Stack | Фокус |
|-------|-------|
| `react` | Components, performance, memo, suspense |
| `nextjs` | App Router, RSC, Server Actions |
| `vue` | Composition API, components |
| `nuxtjs` / `nuxt-ui` | SSR, Nuxt UI patterns |
| `svelte` | Stores, transitions |
| `astro` | Islands, partial hydration |
| `shadcn` | Primitives, composition |
| `html-tailwind` | Utility-first layout |
| `angular` | Signals, services |
| `swiftui` | Views, navigation, state |
| `flutter` | Widgets, navigation |
| `jetpack-compose` | Composables, state |
| `react-native` | Navigation, lists, a11y |
| `javafx` / `wpf` / `winui` | Desktop enterprise UI |
| `threejs` | 3D scenes, performance |

## React / Next.js performance

Дополнительный domain-поиск:
```bash
python core_x_skills/design/ui_ux/ui-ux-pro-max/scripts/search.py "waterfall bundle suspense memo" --domain react
```

## Правила реализации

1. Сначала получи design system (скилл `ui-ux-design-system`).
2. Затем stack search для implementation patterns.
3. Применяй токены из design system, не hardcoded values.
4. Проверь stack-specific a11y (например `accessibilityLabel` в React Native).
