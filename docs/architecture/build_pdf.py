"""Собрать PDF-документацию CoreX (кириллица через Arial)."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "CoreX-как-это-работает.pdf"
FONT = Path(r"C:\Windows\Fonts\arial.ttf")
FONT_B = Path(r"C:\Windows\Fonts\arialbd.ttf")
if not FONT.is_file():
    FONT = Path(r"C:\Windows\Fonts\calibri.ttf")
    FONT_B = Path(r"C:\Windows\Fonts\calibrib.ttf")


class Doc(FPDF):
    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font("Body", size=9)
        self.set_text_color(100, 116, 139)
        self.cell(0, 8, "CoreX — как это работает", align="L")
        self.cell(0, 8, str(self.page_no()), align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(226, 232, 240)
        self.line(18, 16, 192, 16)
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("Body", "", 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 8, "Локальный AI-IDE  ·  файлы только в папке проекта  ·  см. docs/architecture/", align="C")


def _block(pdf: Doc, text: str, h: float) -> None:
    pdf.set_x(pdf.l_margin)
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.multi_cell(usable, h, text)
    pdf.set_x(pdf.l_margin)


def h1(pdf: Doc, text: str) -> None:
    pdf.set_font("Body", "", 18)
    pdf.set_text_color(15, 23, 42)
    _block(pdf, text, 9)
    pdf.ln(2)


def h2(pdf: Doc, text: str) -> None:
    pdf.ln(3)
    pdf.set_font("Body", "", 14)
    pdf.set_text_color(30, 64, 175)
    _block(pdf, text, 8)
    pdf.ln(1)


def h3(pdf: Doc, text: str) -> None:
    pdf.ln(2)
    pdf.set_font("Body", "", 12)
    pdf.set_text_color(51, 65, 85)
    _block(pdf, text, 7)
    pdf.ln(1)


def p(pdf: Doc, text: str) -> None:
    pdf.set_font("Body", "", 11)
    pdf.set_text_color(30, 41, 59)
    _block(pdf, text, 6)
    pdf.ln(2)


def bullet(pdf: Doc, items: list[str]) -> None:
    pdf.set_font("Body", "", 11)
    pdf.set_text_color(30, 41, 59)
    usable = pdf.w - pdf.l_margin - pdf.r_margin - 4
    for item in items:
        pdf.set_x(pdf.l_margin + 4)
        pdf.multi_cell(usable, 6, f"-  {item}")
    pdf.set_x(pdf.l_margin)
    pdf.ln(2)


def mono(pdf: Doc, text: str) -> None:
    pdf.set_font("Body", "", 10)
    pdf.set_fill_color(241, 245, 249)
    pdf.set_text_color(15, 23, 42)
    pdf.set_x(pdf.l_margin)
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.multi_cell(usable, 5.5, text, fill=True)
    pdf.set_x(pdf.l_margin)
    pdf.ln(3)


def build() -> Path:
    pdf = Doc(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 18, 18)
    face = str(FONT)
    pdf.add_font("Body", "", face)

    pdf.add_page()
    pdf.set_x(pdf.l_margin)
    pdf.ln(16)
    pdf.set_font("Body", "", 26)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 12, "CoreX", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Body", "", 15)
    pdf.set_text_color(30, 64, 175)
    pdf.cell(0, 9, "Как это работает", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Body", "", 12)
    pdf.set_text_color(71, 85, 105)
    pdf.multi_cell(
        0,
        7,
        "Документация для себя: что за процессы, куда идёт сообщение из чата, "
        "как выбирается файл, почему змейка стала snake.py, а /test1 — папка. "
        "Схема Draw.io лежит рядом: corex-architecture.drawio "
        "(открыть в diagrams.net или VS Code / Cursor с расширением Draw.io).",
    )
    pdf.ln(8)
    p(pdf, "Сентябрь 2026. Репозиторий на диске: папки frontend/, backend/core/, docs/architecture/.")

    h2(pdf, "1. Одной фразой")
    p(
        pdf,
        "CoreX — это окно на Windows (Electron + React) и Python-сервер рядом. "
        "Ты пишешь в чат. Сервер зовёт локальную модель (Ollama) или онлайн-API. "
        "Модель не «болтает в воздухе»: она просит записать файл, поправить строку или запустить скрипт. "
        "Python пишет на диск в открытую папку проекта. Редактор открывает этот файл.",
    )
    p(
        pdf,
        "Исходники проекта в облако не уезжают. Ключи онлайн-моделей лежат в "
        "%LOCALAPPDATA%\\CoreX\\secrets\\ (файл ai_online_providers.json), не в git. "
        "Папок chat/ две, обе скрыты из дерева и git: в установке CoreX — настройки движка "
        "(ai_runtime.json); в папке проекта — история чата и project_memory.md.",
    )

    h2(pdf, "2. Три процесса")
    bullet(
        pdf,
        [
            "Electron — окно, меню, выбор папки, GPU для интерфейса (на гибриде Intel+NVIDIA UI сидит на iGPU).",
            "Python backend на свободном порту 8000–8099 — HTTP /api/* (файлы, настройки) и WebSocket /ws (чат, мысли, патчи редактора). Electron читает строку COREX_READY port=N.",
            "Ollama — локальная модель. Системное приложение слушает 11434. Свой сервер CoreX — 11435. На ПК с Intel+NVIDIA к 11434 лучше не цепляться: видеокарту оставляем модели.",
        ],
    )
    p(
        pdf,
        "Запуск из исходников: start-corex.bat (окно + backend). "
        "Разработка UI: start-corex-dev.bat. Остановка: stop-corex-runtime.bat.",
    )

    h2(pdf, "3. Что ты видишь в окне")
    bullet(
        pdf,
        [
            "Дерево файлов — папка проекта. chat/ не показывают.",
            "Редактор — вкладки. Когда агент записал файл, приходит editor_patch и вкладка переключается на него.",
            "Чат — запрос, «мысли», статус «Пишу в …», карточки файлов, «Готово».",
            "Терминал — кнопка Run, pip, интерактивный ввод.",
            "Настройки — локальная / онлайн модель, интернет (никогда / спросить / всегда), GPU.",
            "Visio / схема — обзор файлов проекта, не путать с этим Draw.io.",
        ],
    )

    h2(pdf, "4. Путь одного запроса")
    p(pdf, "Пример: «создай сапёра с игровым окном в /test1».")
    bullet(
        pdf,
        [
            "Чат шлёт текст по WebSocket в backend.",
            "ws_server отдаёт задачу в orchestrator.execute_task.",
            "task_routing решает: это код, вопрос или «привет». Код идёт дальше.",
            "write_target смотрит /test1: нет расширения → папка. Имя файла по задаче → minesweeper.py. Итог: test1/minesweeper.py.",
            "file_mentions не прикрепляет содержимое папки и чужие файлы (змейку не подсовывают в промпт).",
            "Если просили сапёра с окном и файла ещё нет — game_gui_upgrade сразу пишет готовый tkinter. 3B сама сапёра не соберёт.",
            "Иначе цикл: модель отвечает JSON или блоком ```python```. agent_json это разбирает.",
            "Инструмент write_file / patch_file / view_file / run_file. Путь ещё раз прогоняют через remap_write_path (main.py модели → нужная папка/имя).",
            "file_service: нет расширения — отказ; заглушка из двух print — отказ; пустое pygame-окно — отказ. Родители папки создаются. Если test1 был ошибочным файлом — его снимают и делают папку.",
            "Успех → editor_patch в UI, проверка синтаксиса, иногда run_file. Игры с while True / input() не гоняют как дымовой тест.",
            "8 ходов подряд без новой записи — стоп (или снова шаблон сапёра). Чтобы Ollama не крутилась зря.",
        ],
    )

    h2(pdf, "5. /путь в чате — это не «аттач картинки»")
    p(
        pdf,
        "Чип над полем ввода просто показывает, что в тексте есть /ссылка. Смысл ссылки зависит от фразы.",
    )
    bullet(
        pdf,
        [
            "/main.py + «что делает» — только чтение. Файл прикрепляют в промпт, на диск не пишут.",
            "/main.py + «исправь» — правка этого файла. Другой путь моделью подменить нельзя.",
            "/test1 + «создай …» — папка. Внутри новый файл с нормальным именем. Не test1 и не test1/main.py.",
            "Без / вообще — агент сам выбирает имя: змейка → snake.py, калькулятор → calculator.py.",
            "Файл без расширения сохранить нельзя. Сообщение: одно название недостаточно.",
            "Если test1 уже лежит как файл (старая ошибка) — для /test1 это всё равно папка. При записи файл убирают, создают каталог.",
        ],
    )

    h2(pdf, "6. Инструменты агента")
    bullet(
        pdf,
        [
            "write_file — новый или полный файл. Предпочтительно для новой программы: один целый .py за ход.",
            "patch_file — одна строка (replace/delete). Для точечной правки после view_file.",
            "view_file — прочитать. Для создания с нуля 3B часто не должна сначала листать пустую папку.",
            "append_file — дописать кусок. Служебный текст из промпта отбрасывается.",
            "run_file / терминал — запуск. pip ставится в тот же Python, что и кнопка Run. Для 3.14 pygame -> pygame-ce.",
        ],
    )

    h2(pdf, "7. Модели и железо")
    p(
        pdf,
        "Рабочий ПК (i7, 16 ГБ, T600 4 ГБ): держимся Qwen 2.5 Coder 3B, контекст 4096. "
        "Домашний (32 ГБ, RTX 3050 8 ГБ): можно 7B. Онлайн — запасной канал, если локальный движок лежит, "
        "или если ты сам включил online в настройках.",
    )
    p(
        pdf,
        "llm_runtime собирает ActiveLlm: режим local или online, имя модели, клиент. "
        "Для слабой локальной модели промпт ужимают (local_pipeline_profile): один файл за ход, JSON не обязателен.",
    )

    h2(pdf, "8. Защиты, чтобы 3B не сожрала игру")
    bullet(
        pdf,
        [
            "Пустое pygame-окно и «два print» не записываются поверх живого кода.",
            "Недописанный tkinter (нет mainloop / pass вместо логики) отклоняется.",
            "Нельзя затереть готовую игру скелетом.",
            "Синтаксис чинят (отступы, обрыв), логику игры — нет.",
            "Шаблон сапёра подставляют только если просили сапёра (или в файле уже сапёр). Змейку им не подменяют.",
        ],
    )

    h2(pdf, "9. Карта папок")
    mono(
        pdf,
        "frontend/                 окно: Electron + React\n"
        "  electron.cjs            старт UI и Python\n"
        "  src/app/                чат, редактор, дерево, настройки\n"
        "backend/core/             мозг агента (см. лист 4 в Draw.io)\n"
        "  orchestrator.py         цикл задачи\n"
        "  write_target.py         куда писать\n"
        "  file_service.py         диск\n"
        "  game_gui_upgrade.py     шаблон окна-сапёра\n"
        "chat/ (у CoreX)           ai_runtime.json, лимиты, лог Ollama\n"
        "{проект}/chat/            история чата, project_memory.md, visio\n"
        "core_x_skills/            библиотека скиллов\n"
        "core_x_agents/            персоны пайплайна\n"
        "docs/architecture/        эта документация и .drawio",
    )

    h2(pdf, "10. Как читать схему Draw.io")
    p(
        pdf,
        "Файл: docs/architecture/corex-architecture.drawio. Четыре листа:",
    )
    bullet(
        pdf,
        [
            "1. Общая схема — ты, окно, backend, диск, Ollama.",
            "2. Ход сообщения — 15 шагов от фразы до «Готово».",
            "3. Куда писать — развилка /файл vs /папка vs без слэша.",
            "4. Модули backend — какой .py за что отвечает.",
        ],
    )
    p(
        pdf,
        "Открыть: https://app.diagrams.net → Open Existing → выбрать файл. "
        "Или расширение «Draw.io Integration» в Cursor/VS Code.",
    )

    h2(pdf, "11. Частые «почему так»")
    h3(pdf, "Почему змейка в snake.py, а не в main.py?")
    p(pdf, "Ты не указал /путь. Система сама берёт имя из задачи. Корневой main.py не затирают.")
    h3(pdf, "Почему сапёр в /test1 сначала не записался?")
    p(
        pdf,
        "3B не собирает сапёра за 8 ходов. Шаблон должен писаться сразу в test1/minesweeper.py. "
        "Если /test1 ошибочно стал файлом без расширения — запись внутрь ломалась. Сейчас имя без точки = папка, "
        "лишний файл test1 при записи снимают.",
    )
    h3(pdf, "Почему интернет «не гуглит весь проект»?")
    p(
        pdf,
        "web_access: never / ask / always. Поиск — короткие сниппеты (DuckDuckGo). "
        "Исходники папки на сервер поиска не отправляют.",
    )
    h3(pdf, "Где ключи и модели?")
    p(
        pdf,
        "Ключи: %LOCALAPPDATA%\\CoreX\\secrets\\. Модели Ollama: либо системная папка .ollama, "
        "либо каталог моделей установки CoreX. Предустановки — chat/ai_runtime.json (скрыт).",
    )

    h2(pdf, "12. С чего править код, если снова «не туда пишет»")
    bullet(
        pdf,
        [
            "backend/core/write_target.py — смысл /пути и имя файла.",
            "backend/core/file_service.py — физическая запись, запрет без расширения, папка вместо файла test1.",
            "backend/core/orchestrator.py — цикл, fallback окна, editor_patch.",
            "backend/core/game_gui_upgrade.py — когда подставлять сапёра.",
            "frontend/src/app/contexts/ChatContext.tsx — приём патча в редактор.",
        ],
    )

    pdf.output(str(OUT))
    return OUT


if __name__ == "__main__":
    path = build()
    print(path)
