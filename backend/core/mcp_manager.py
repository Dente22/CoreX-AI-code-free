import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPManager:
    def __init__(self):
        self.sessions = {}
        self._stop_flags = {}
        self._connection_tasks = {}

    async def connect_server(self, server_name: str, command: str, args: list):
        """Подключение внешнего MCP сервера (например, filesystem) через Stdio."""
        self._stop_flags[server_name] = False
        current = asyncio.current_task()
        if current is not None:
            self._connection_tasks[server_name] = current
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=None,
        )

        try:
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    self.sessions[server_name] = session
                    print(f"[CoreX] MCP Server '{server_name}' successfully connected.")

                    while (
                        server_name in self.sessions
                        and not self._stop_flags.get(server_name, False)
                    ):
                        await asyncio.sleep(1)
        finally:
            self.sessions.pop(server_name, None)
            self._connection_tasks.pop(server_name, None)

    async def disconnect_server(self, server_name: str):
        self._stop_flags[server_name] = True
        self.sessions.pop(server_name, None)

        task = self._connection_tasks.get(server_name)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._connection_tasks.pop(server_name, None)
        await asyncio.sleep(0.3)

    async def reconnect_filesystem(self, project_root: str) -> bool:
        """Переподключить filesystem MCP к новому корню проекта."""
        await self.disconnect_server("filesystem")

        task = asyncio.create_task(self.connect_server(
            server_name="filesystem",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", project_root],
        ))
        self._connection_tasks["filesystem"] = task

        for _ in range(20):
            if "filesystem" in self.sessions:
                return True
            await asyncio.sleep(0.5)

        return False

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict):
        """Вызов конкретной команды (инструмента) на MCP сервере."""
        session = self.sessions.get(server_name)
        if not session:
            return {"error": f"Server {server_name} not connected"}

        try:
            result = await session.call_tool(tool_name, arguments=arguments)
            return result
        except Exception as e:
            return {"error": str(e)}
