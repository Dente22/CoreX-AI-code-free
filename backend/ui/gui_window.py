import customtkinter as ctk
from tkinter import ttk
import os
import threading

class CoreXGUI(ctk.CTk):
    def __init__(self, project_dir, on_submit_callback, on_file_save_callback=None):
        super().__init__()

        self.project_dir = project_dir
        self.on_submit_callback = on_submit_callback
        self.on_file_save_callback = on_file_save_callback
        self.current_open_file = None

        # Палитра дизайна CoreX (GitHub Dark / Neon Cyberpunk)
        self.bg_dark = "#0d1117"        # Основной фон редактора и окон
        self.bg_sidebar = "#161b22"     # Панели проводника и вкладок
        self.bg_activity = "#090d13"    # Крайняя левая полоса иконок
        self.bg_terminal = "#010409"    # Панель терминала bash
        self.accent_cyan = "#58a6ff"    # Бирюзовый подсветки
        self.accent_purple = "#c678dd"  # Пурпурный
        self.accent_green = "#2ea043"   # Зеленый кнопок
        self.border_color = "#30363d"   # Тонкие разделители

        # Настройки окна
        self.title("CoreX - Autonomous Workspace")
        self.geometry("1280x760")
        self.configure(fg_color=self.bg_dark)
        ctk.set_appearance_mode("dark")

        # Настройка сетки главного окна (3 колонки: Сайдбары + Редактор + Чат)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0) # Activity Bar (60px)
        self.grid_columnconfigure(1, weight=0) # File Explorer (240px)
        self.grid_columnconfigure(2, weight=3) # Center Editor + Terminal (Flex)
        self.grid_columnconfigure(3, weight=1) # CoreX AI Chat (350px)

        self._create_activity_bar()
        self._create_file_explorer()
        self._create_center_editor()
        self._create_ai_sidebar()
        self._create_status_bar()

        # Инициализация дерева файлов выполняется после выбора папки/файла
        # (пока дерево остаётся пустым при запуске).

    def _create_activity_bar(self):
        """1. Крайняя левая панель иконок (Activity Bar)."""
        bar = ctk.CTkFrame(self, width=55, fg_color=self.bg_activity, corner_radius=0, border_color=self.border_color, border_width=1)
        bar.grid(row=0, column=0, sticky="ns")
        bar.grid_propagate(False)

        # Псевдо-иконки (unicode-символы для сохранения легкости приложения)
        icons = [
            ("📁", "Explorer"),
            ("🔍", "Search"),
            ("⌥", "Source Control"),
            ("⊞", "Extensions"),
            ("⚙️", "Settings")
        ]
        for i, (char, name) in enumerate(icons):
            btn = ctk.CTkButton(
                bar, text=char, width=40, height=40, 
                fg_color="transparent", hover_color="#21262d",
                font=("Consolas", 18), text_color="#8b949e",
                corner_radius=4
            )
            btn.pack(pady=8, padx=5)

    def _create_file_explorer(self):
        """2. Панель Проводника (File Explorer)."""
        explorer_frame = ctk.CTkFrame(self, width=240, fg_color=self.bg_sidebar, corner_radius=0, border_color=self.border_color, border_width=1)
        explorer_frame.grid(row=0, column=1, sticky="nsew")
        explorer_frame.grid_propagate(False)

        # Заголовок проводника
        lbl = ctk.CTkLabel(explorer_frame, text="ПРОВОДНИК", font=("Segoe UI", 11, "bold"), text_color="#8b949e")
        lbl.pack(anchor="w", padx=15, pady=(15, 5))

        # Название папки проекта
        proj_name = os.path.basename(self.project_dir).upper()
        proj_lbl = ctk.CTkLabel(explorer_frame, text=f"📂 {proj_name}", font=("Segoe UI", 12, "bold"), text_color="#c9d1d9")
        proj_lbl.pack(anchor="w", padx=15, pady=(0, 10))

        # Стилизуем Treeview под тему GitHub Dark
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview", 
            background=self.bg_sidebar, 
            foreground="#c9d1d9", 
            fieldbackground=self.bg_sidebar,
            font=("Segoe UI", 11),
            rowheight=24,
            borderwidth=0
        )
        style.map("Treeview", background=[("selected", "#21262d")], foreground=[("selected", self.accent_cyan)])
        style.configure("Treeview.Heading", background=self.bg_sidebar, foreground="#8b949e", borderwidth=0)

        # Контейнер для дерева с прокруткой
        tree_container = ctk.CTkFrame(explorer_frame, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=5, pady=5)

        self.tree = ttk.Treeview(tree_container, show="tree", selectmode="browse")
        self.tree.pack(side="left", fill="both", expand=True)
        
        self.tree.bind("<<TreeviewOpen>>", self.on_tree_open)
        self.tree.bind("<Double-1>", self.on_tree_click)

    def _create_center_editor(self):
        """3. Центральная панель: Вкладки файлов + Текстовый редактор + Терминал."""
        center_frame = ctk.CTkFrame(self, fg_color=self.bg_dark, corner_radius=0)
        center_frame.grid(row=0, column=2, sticky="nsew")
        
        center_frame.grid_rowconfigure(0, weight=0) # Вкладки
        center_frame.grid_rowconfigure(1, weight=2) # Код
        center_frame.grid_rowconfigure(2, weight=1) # Терминал (bash)
        center_frame.grid_columnconfigure(0, weight=1)

        # Панель вкладок (Tabs)
        self.tabs_frame = ctk.CTkFrame(center_frame, height=35, fg_color=self.bg_sidebar, corner_radius=0, border_color=self.border_color, border_width=1)
        self.tabs_frame.grid(row=0, column=0, sticky="ew")
        self.tabs_frame.grid_propagate(False)

        self.tab_lbl = ctk.CTkLabel(self.tabs_frame, text="Нет открытого файла", font=("Segoe UI", 11, "bold"), text_color=self.accent_cyan)
        self.tab_lbl.pack(side="left", padx=15, pady=5)

        # Окно редактора кода (Code Editor)
        self.code_editor = ctk.CTkTextbox(
            center_frame, 
            font=("Consolas", 13), 
            fg_color=self.bg_dark, 
            text_color="#c9d1d9",
            wrap="none",
            border_width=0,
            corner_radius=0
        )
        self.code_editor.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)

        # Нижняя панель встроенного bash-терминала
        term_frame = ctk.CTkFrame(center_frame, fg_color=self.bg_terminal, corner_radius=0, border_color=self.border_color, border_width=1)
        term_frame.grid(row=2, column=0, sticky="nsew", padx=2, pady=(1, 2))
        term_frame.grid_rowconfigure(0, weight=0) # Заголовок
        term_frame.grid_rowconfigure(1, weight=1) # Вывод терминала
        term_frame.grid_columnconfigure(0, weight=1)

        term_title = ctk.CTkLabel(term_frame, text=" ❯_ bash", font=("Consolas", 12, "bold"), text_color="#8b949e", anchor="w")
        term_title.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        self.term_view = ctk.CTkTextbox(
            term_frame, 
            font=("Consolas", 12), 
            fg_color=self.bg_terminal, 
            text_color="#8b949e", 
            wrap="word",
            corner_radius=0
        )
        self.term_view.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.term_view.configure(state="disabled")

    def _create_ai_sidebar(self):
        """4. Правая панель ИИ-Помощника (CoreX AI Chat)."""
        ai_frame = ctk.CTkFrame(self, width=350, fg_color=self.bg_sidebar, corner_radius=0, border_color=self.border_color, border_width=1)
        ai_frame.grid(row=0, column=3, sticky="nsew")
        ai_frame.grid_propagate(False)

        ai_frame.grid_rowconfigure(0, weight=0) # Хедер
        ai_frame.grid_rowconfigure(1, weight=1) # Чат лог
        ai_frame.grid_rowconfigure(2, weight=0) # Поле ввода + кнопка
        ai_frame.grid_columnconfigure(0, weight=1)

        # Заголовок ИИ-помощника
        header = ctk.CTkFrame(ai_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=15, pady=15)
        
        ai_lbl = ctk.CTkLabel(header, text="✨ CoreX AI", font=("Segoe UI", 14, "bold"), text_color=self.accent_purple)
        ai_lbl.pack(side="left")
        
        self.status_dot = ctk.CTkLabel(header, text="● Локально", font=("Segoe UI", 10), text_color="#2ea043")
        self.status_dot.pack(side="right")

        # Окно лога чата с ИИ
        self.chat_view = ctk.CTkTextbox(
            ai_frame, 
            font=("Segoe UI", 12), 
            fg_color=self.bg_dark, 
            text_color="#c9d1d9",
            wrap="word",
            corner_radius=8,
            border_color=self.border_color,
            border_width=1
        )
        self.chat_view.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.chat_view.insert("1.0", "CoreX AI: Привет! Я твой локальный ИИ-инженер. Я умею искать уязвимости, править код и запускать утилиты. Какая задача стоит перед нами?\n")
        self.chat_view.configure(state="disabled")

        # Зона ввода задач
        input_container = ctk.CTkFrame(ai_frame, fg_color="transparent")
        input_container.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 15))
        input_container.grid_columnconfigure(0, weight=1)
        input_container.grid_columnconfigure(1, weight=0)

        self.chat_input = ctk.CTkEntry(
            input_container, 
            placeholder_text="Спросите CoreX AI...",
            font=("Segoe UI", 12),
            fg_color=self.bg_dark,
            border_color=self.border_color,
            corner_radius=8
        )
        self.chat_input.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.chat_input.bind("<Return>", lambda event: self.send_ai_task())

        self.chat_btn = ctk.CTkButton(
            input_container, 
            text="➤", 
            width=40,
            font=("Consolas", 14, "bold"),
            fg_color=self.accent_purple,
            text_color="#ffffff",
            hover_color="#a855f7",
            corner_radius=8,
            command=self.send_ai_task
        )
        self.chat_btn.grid(row=0, column=1, sticky="w")

    def _create_status_bar(self):
        """5. Нижний информационный статус-бар."""
        status = ctk.CTkFrame(self, height=25, fg_color="#1f242c", corner_radius=0)
        status.grid(row=1, column=0, columnspan=4, sticky="ew")
        
        lbl_branch = ctk.CTkLabel(status, text=" 🌿 main  |  ✓ Нет ошибок  |  TypeScript React", font=("Segoe UI", 10), text_color="#8b949e")
        lbl_branch.pack(side="left", padx=15, pady=2)

        lbl_pos = ctk.CTkLabel(status, text="Строка 1, Колонка 1  |  UTF-8  |  LF ", font=("Segoe UI", 10), text_color="#8b949e")
        lbl_pos.pack(side="right", padx=15, pady=2)

    # --- ЛОГИКА ФАЙЛОВОЙ СИСТЕМЫ (ПРОДВИК) ---
    def load_project_tree(self):
        """Инициализация корневого каталога."""
        for child in self.tree.get_children():
            self.tree.delete(child)
        self.populate_tree("", self.project_dir)

    def populate_tree(self, parent, path):
        """Сканирование директорий без зависания интерфейса."""
        try:
            items = sorted(os.listdir(path))
            for item in items:
                # Фильтруем тяжелый мусор, чтобы дерево летало
                if item in [".venv", "__pycache__", ".git", "node_modules", "dist", ".idea"]:
                    continue
                
                full_path = os.path.join(path, item)
                is_dir = os.path.isdir(full_path)
                icon = "📁 " if is_dir else "📄 "
                
                node = self.tree.insert(parent, "end", text=f"{icon}{item}", values=[full_path])
                
                # Если папка, вставляем пустышку-dummy для возможности раскрытия
                if is_dir:
                    self.tree.insert(node, "end", text="загрузка...")
        except Exception as e:
            pass

    def on_tree_open(self, event):
        """Динамическая ленивая загрузка папок при клике на раскрытие."""
        node = self.tree.focus()
        path = self.tree.item(node, "values")[0]
        
        # Стираем временные dummy элементы
        children = self.tree.get_children(node)
        if len(children) == 1 and self.tree.item(children[0], "text") == "загрузка...":
            self.tree.delete(children[0])
            self.populate_tree(node, path)

    def on_tree_click(self, event):
        """Открытие файла в редакторе по двойному клику."""
        node = self.tree.focus()
        values = self.tree.item(node, "values")
        if values:
            file_path = values[0]
            if os.path.isfile(file_path):
                self.load_file_into_editor(file_path)

    def load_file_into_editor(self, file_path):
        """Загрузка текстового содержимого файла в окно редактора."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            self.current_open_file = file_path
            self.tab_lbl.configure(text=f"📄 {os.path.basename(file_path)}")
            
            self.code_editor.delete("1.0", "end")
            self.code_editor.insert("1.0", content)
            self.print_terminal("System", f"Файл открыт: {file_path}")
        except Exception as e:
            self.print_terminal("Error", f"Не удалось прочитать файл: {e}")

    def send_ai_task(self):
        """Отправка запроса пользователем в CoreX AI."""
        task_text = self.chat_input.get().strip()
        if not task_text:
            return

        self.chat_input.delete(0, "end")
        self.print_user_message(task_text)

        if self.on_submit_callback:
            self.on_submit_callback(task_text)

    def print_user_message(self, text: str):
        """Вывод сообщения пользователя в чат ИИ."""
        def append():
            self.chat_view.configure(state="normal")
            self.chat_view.insert("end", f"\n👤 Вы: {text}\n")
            self.chat_view.see("end")
            self.chat_view.configure(state="disabled")
        self.after(0, append)

    # --- ЛОГИКА ВЫВОДА ЛОГОВ И ЧАТА ---
    def print_log(self, tag: str, text: str):
        """Безопасный вывод мыслей и ответов ИИ в панель ассистента."""
        def append():
            self.chat_view.configure(state="normal")
            self.chat_view.insert("end", f"\n🤖 {tag}: {text}\n")
            self.chat_view.see("end")
            self.chat_view.configure(state="disabled")
        self.after(0, append)

    def print_terminal(self, sender: str, text: str):
        """Вывод действий и ответов инструментов во встроенный bash-терминал."""
        def append():
            self.term_view.configure(state="normal")
            self.term_view.insert("end", f"$ [{sender}] {text}\n")
            self.term_view.see("end")
            self.term_view.configure(state="disabled")
        self.after(0, append)

