import sys
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML

class CoreXTUI:
    def __init__(self):
        # Настраиваем неоновые цвета для нашего TUI
        self.style = Style.from_dict({
            'prompt_user': '#00ffff bold',       # Циан / Бирюзовый
            'prompt_arrow': '#00ff00 bold',      # Зеленый
            'engine_status': '#ff00ff italic',   # Пурпурный
            'action_label': '#ffff00 bold',      # Желтый
            'error_label': '#ff0000 bold',       # Красный
        })
        self.session = PromptSession(style=self.style)

    def print_welcome(self):
        """Красивый баннер при запуске."""
        print("\033[2J\033[H", end="") # Очистка экрана
        print("-" * 50)
        print("  ⚡ CoreX Engine v1.0.0 ⚡  ")
        print("  Autonomous Local AI Workspace")
        print("-" * 50)

    def print_status(self, text: str):
        print(f"\n⚡ [CoreX]: {text}")

    def print_action(self, server: str, tool: str, args: dict):
        print(f"\n⚙️  [Action]: Calling {server} -> {tool} with args: {args}")

    def print_error(self, text: str):
         print(f"\n❌ [Error]: {text}")

    async def get_user_input(self) -> str:
        """Асинхронный ввод с красивой стрелкой."""
        try:
            # Используем HTML для раскраски промпта
            prompt_text = HTML('<prompt_user>CoreX_User</prompt_user> <prompt_arrow>❯</prompt_arrow> ')
            user_input = await self.session.prompt_async(prompt_text)
            return user_input.strip()
        except (KeyboardInterrupt, EOFError):
            return "exit"