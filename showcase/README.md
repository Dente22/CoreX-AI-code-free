# Showcase — finished projects for the public repo / готовые проекты

Drop finished demos here so they ship with the public CoreX repository.

Сюда складываем **законченные** демо/проекты для публичного репозитория CoreX.

## How / Как

1. Copy a finished project to `showcase/<project-name>/`
2. Drafts can go to `showcase/_inbox/` (not committed)
3. Each project should include a short `README.md`

Готовый проект → `showcase/<имя>/` · черновики → `_inbox/` · в каждом проекте желателен `README.md`.

## Rules / Правила

- No `node_modules`, `.venv`, secrets, or `.env`
- Avoid huge media unless required for the demo
- One project = one clear folder name (`landing-cafe`, `todo-app`, …)

Без `node_modules` / `.venv` / секретов. Один проект = одна понятная папка.

## Layout / Структура

```text
showcase/
  README.md
  _inbox/          ← temp, ignored by git
  my-landing/
    README.md
    index.html
    ...
```
