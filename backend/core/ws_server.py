import json
import os
import re
import asyncio
from pathlib import Path

from aiohttp import web, WSMsgType

from core.core_x_library import invalidate_cache, list_library_agents, resolve_persona_prompt
from core.agent_service import create_agent, delete_agent, ensure_agents_dir, list_agents
from core.persona_service import (
    create_persona,
    delete_persona,
    ensure_personas_dir,
    list_personas,
)
from core.pipeline_service import (
    create_pipeline,
    delete_pipeline,
    ensure_pipelines_dir,
    list_pipelines,
)
from core.device_profile import profile_to_dict
from core.knowledge_service import knowledge_meta
from core.app_version import COREX_BACKEND_VERSION
from core.core_x_library import list_library_agents, list_library_teams
from core.error_remediation import remediate_python_error
from core.terminal_service import run_command, run_file
from core.terminal_session import (
    InteractiveTerminal,
    annotate_python_hints,
    start_command as start_terminal_command,
    start_file as start_terminal_file,
)
from core.skill_categories import SKILL_CATEGORIES, TEAM_PRESETS
from core.project_bootstrap_service import create_project
from core.visio_service import get_visio_payload
from core.git_clone_service import clone_repository
from core.git_scm_service import (
    commit_staged,
    discard_paths,
    get_status,
    init_repository,
    push_repository,
    stage_paths,
    unstage_paths,
)
from core.token_usage_service import reset_session_usage
from core.chat_history_service import (
    archive_current_chat,
    clear_ui_messages,
    list_chat_sessions,
    load_chat_session,
    load_ui_messages,
    save_ui_messages,
)
from core.trace_store import list_errors, load_event, load_task_events

class WebSocketServer:
    def __init__(self, orchestrator, file_service=None):
        self.orchestrator = orchestrator
        self.file_service = file_service
        self.clients = set()
        self._inflight_task_key: str | None = None
        self.terminal_session = InteractiveTerminal()
        self.orchestrator.register_websocket_server(self)

    def _task_dispatch_key(
        self,
        task_text: str,
        *,
        project_root: str | None,
        work_mode: str,
        pipeline_id: str | None,
        persona_id: str | None,
    ) -> str:
        return "|".join([
            (project_root or "").strip(),
            work_mode or "single",
            pipeline_id or "",
            persona_id or "",
            task_text.strip(),
        ])

    def clear_inflight_task_key(self) -> None:
        self._inflight_task_key = None

    async def broadcast(self, message: dict):
        closed = []
        for ws in list(self.clients):
            if ws.closed:
                closed.append(ws)
                continue
            try:
                await ws.send_json(message)
            except Exception:
                closed.append(ws)
        for ws in closed:
            self.clients.discard(ws)

    async def _send_chat(self, ws, sender: str, text: str):
        await ws.send_json({
            'target': 'chat',
            'sender': sender,
            'text': text,
        })

    def _default_file_template(self, path: str) -> str:
        extension = os.path.splitext(path)[1].lower()
        if extension == '.py':
            return '# New file created by CoreX\n'
        if extension in {'.ts', '.tsx', '.js', '.jsx'}:
            return '// New file created by CoreX\n'
        if extension == '.md':
            return '# New file created by CoreX\n'
        return ''

    def _parse_create_file_command(self, task_text: str):
        """Parse direct file-create shortcuts. Returns (path, content) or None → orchestrator."""
        normalized = task_text.strip()
        if not normalized:
            return None

        patterns_with_content = [
            r'^(?:создай|создать)\s+файл\s+([^\s:]+)\s*::\s*(.*)$',
            r'^(?:создай|создать)\s+файл\s+([^\s:]+)\s+с\s+кодом\s+(.+)$',
            r'^create\s+file\s+([^\s:]+)\s*::\s*(.*)$',
        ]
        for pattern in patterns_with_content:
            match = re.match(pattern, normalized, re.IGNORECASE | re.DOTALL)
            if match:
                path = match.group(1).strip().strip('"\'')
                content = match.group(2).strip()
                return path, content

        simple = re.match(r'^(?:создай|создать)\s+файл\s+([^\s:]+)$', normalized, re.IGNORECASE)
        if simple:
            path = simple.group(1).strip().strip('"\'')
            return path, self._default_file_template(path)

        return None

    @staticmethod
    def _is_write_success(result) -> bool:
        if not isinstance(result, dict):
            return False
        if result.get('error'):
            return False
        return result.get('success') is True

    async def _handle_create_file_command(self, task_text: str, ws):
        parsed = self._parse_create_file_command(task_text)
        if parsed is None:
            return False

        path, content = parsed
        if not path:
            await self._send_chat(ws, 'CoreX Error', 'Путь к файлу не указан.')
            return True

        if not self.file_service:
            await self._send_chat(ws, 'CoreX Error', 'File service not available')
            return True

        result = await self.file_service.write_file(path, content)
        if self._is_write_success(result):
            await self._send_chat(ws, 'CoreX', f'Файл создан: {path}')
        else:
            error_text = result.get('error') if isinstance(result, dict) else str(result)
            await self._send_chat(
                ws,
                'CoreX Error',
                f'Не удалось создать файл {path}: {error_text or "неизвестная ошибка записи"}',
            )
        return True

    async def _handle_task(
        self,
        task_text: str,
        ws,
        project_root: str | None = None,
        history: list | None = None,
        persona_id: str | None = None,
        pipeline_id: str | None = None,
        work_mode: str = "single",
        coding_language: str | None = None,
        coding_engine: str | None = None,
    ):
        self.clients.add(ws)

        if not project_root:
            await self._send_chat(
                ws,
                "CoreX Error",
                "Сначала откройте папку проекта в CoreX (Файл → Открыть папку).",
            )
            return

        root_result = await self.orchestrator.set_project_root(project_root)
        if isinstance(root_result, dict) and root_result.get("error"):
            await self._send_chat(
                ws,
                "CoreX Error",
                f"Не удалось установить проект: {root_result['error']}",
            )
            return

        if await self._handle_create_file_command(task_text, ws):
            return

        self.orchestrator.begin_trace_task(
            task_text,
            work_mode=work_mode,
            persona_id=persona_id,
            pipeline_id=pipeline_id,
        )

        await self.orchestrator.execute_task(
            task_text,
            project_root=project_root,
            history=history,
            persona_id=persona_id,
            pipeline_id=pipeline_id,
            work_mode=work_mode,
            coding_language=coding_language,
            coding_engine=coding_engine,
        )

    async def handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self.clients.add(ws)

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except json.JSONDecodeError:
                        await ws.send_json({
                            'target': 'chat',
                            'sender': 'System',
                            'text': 'Invalid JSON payload',
                        })
                        continue

                    task_text = data.get('task')
                    project_root = data.get('project_root') or data.get('projectRoot')
                    history = data.get('history')
                    persona_id = data.get('persona_id') or data.get('personaId')
                    pipeline_id = data.get('pipeline_id') or data.get('pipelineId')
                    work_mode = data.get('work_mode') or data.get('workMode') or 'single'
                    coding_language = data.get('coding_language') or data.get('codingLanguage')
                    coding_engine = data.get('coding_engine') or data.get('codingEngine')
                    stop_request = data.get('stop')

                    if stop_request:
                        stopped = self.orchestrator.stop_current_task()
                        await ws.send_json({
                            'target': 'chat',
                            'sender': 'System',
                            'text': 'Остановка запроса отправлена.' if stopped else 'Нет активной задачи для остановки.',
                        })
                        continue

                    if task_text:
                        task_key = self._task_dispatch_key(
                            task_text,
                            project_root=project_root,
                            work_mode=work_mode,
                            pipeline_id=pipeline_id,
                            persona_id=persona_id,
                        )
                        current = self.orchestrator.current_task
                        if (
                            task_key == self._inflight_task_key
                            and current is not None
                            and not current.done()
                        ):
                            continue

                        self.orchestrator.stop_current_task()
                        self._inflight_task_key = task_key
                        asyncio.create_task(
                            self._handle_task(
                                task_text, ws, project_root, history,
                                persona_id, pipeline_id, work_mode, coding_language,
                                coding_engine,
                            )
                        )
                    else:
                        await ws.send_json({
                            'target': 'chat',
                            'sender': 'System',
                            'text': 'No task field provided',
                        })
                elif msg.type == WSMsgType.ERROR:
                    print('WebSocket connection closed with exception', ws.exception())
        finally:
            self.clients.discard(ws)

        return ws

    async def handle_list_files(self, request):
        """HTTP endpoint: GET /api/files?path=."""
        path = request.query.get('path', '.')
        result = await self.file_service.list_directory(path) if self.file_service else {"error": "File service not available"}
        return web.json_response(result)

    async def handle_file_mentions(self, request):
        if not self.file_service:
            return web.json_response({"error": "File service not available"})
        query = request.query.get("q", "")
        limit = min(int(request.query.get("limit", "30") or 30), 50)
        files = await self.file_service.list_mention_candidates(query, limit=limit)
        return web.json_response({"success": True, "files": files})

    async def handle_search_files(self, request):
        if not self.file_service:
            return web.json_response({"error": "File service not available"})
        query = request.query.get("q", "")
        try:
            limit = int(request.query.get("limit", "80") or 80)
        except ValueError:
            limit = 80
        result = await self.file_service.search_contents(query, limit=limit)
        status = 400 if result.get("error") else 200
        return web.json_response(result, status=status)

    async def handle_read_file(self, request):
        """HTTP endpoint: GET /api/files/read?path=filename."""
        path = request.query.get('path', '')
        if not path:
            return web.json_response({"error": "path parameter required"})
        result = await self.file_service.read_file(path) if self.file_service else {"error": "File service not available"}
        return web.json_response(result)

    async def handle_file_tree(self, request):
        """HTTP endpoint: GET /api/files/tree."""
        result = await self.file_service.get_file_tree() if self.file_service else {"error": "File service not available"}
        return web.json_response(result)

    async def handle_list_pipelines(self, request):
        if not self.file_service:
            return web.json_response({"error": "File service not available"})
        root = Path(self.file_service.project_root)
        ensure_pipelines_dir(root)
        return web.json_response({"success": True, "pipelines": list_pipelines(root)})

    async def handle_list_agents(self, request):
        if not self.file_service:
            return web.json_response({"error": "File service not available"})
        root = Path(self.file_service.project_root)
        ensure_agents_dir(root)
        return web.json_response({"success": True, "agents": list_agents(root)})

    async def handle_create_agent(self, request):
        if not self.file_service:
            return web.json_response({"error": "File service not available"})

        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)

        name = data.get("name", "")
        prompt = data.get("prompt", "")
        category_ru = data.get("category_ru", "")

        root = Path(self.file_service.project_root)
        result = create_agent(root, name, prompt, category_ru=category_ru)
        status = 400 if result.get("error") else 200
        return web.json_response(result, status=status)

    async def handle_delete_agent(self, request):
        if not self.file_service:
            return web.json_response({"error": "File service not available"})
        agent_id = request.match_info.get("agent_id", "")
        root = Path(self.file_service.project_root)
        result = delete_agent(root, agent_id)
        status = 400 if result.get("error") else 200
        return web.json_response(result, status=status)

    async def handle_ai_usage(self, request):
        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not available"})
        return web.json_response(self.orchestrator.get_token_usage())

    async def handle_set_ai_usage_limits(self, request):
        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not available"})
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)
        result = self.orchestrator.update_token_limits(data)
        return web.json_response(result)

    async def handle_reset_ai_usage(self, request):
        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not available"})
        app_root = self.orchestrator._app_root()
        return web.json_response(reset_session_usage(app_root))

    def _chat_project_root(self) -> Path | None:
        if not self.file_service or not self.file_service.project_root:
            return None
        root = Path(self.file_service.project_root)
        return root if root.is_dir() else None

    async def handle_trace_errors(self, request):
        root = self._chat_project_root()
        if not root:
            return web.json_response({"error": "Откройте папку проекта"}, status=400)
        task_id = request.rel_url.query.get("task_id")
        errors = list_errors(root, task_id=task_id or None)
        return web.json_response({"success": True, "errors": errors})

    async def handle_trace_task(self, request):
        root = self._chat_project_root()
        if not root:
            return web.json_response({"error": "Откройте папку проекта"}, status=400)
        task_id = request.match_info.get("task_id", "")
        events = load_task_events(root, task_id)
        return web.json_response({"success": True, "task_id": task_id, "events": events})

    async def handle_trace_event(self, request):
        root = self._chat_project_root()
        if not root:
            return web.json_response({"error": "Откройте папку проекта"}, status=400)
        task_id = request.match_info.get("task_id", "")
        event_id = request.match_info.get("event_id", "")
        event = load_event(root, task_id, event_id)
        if not event:
            return web.json_response({"error": "Событие не найдено"}, status=404)
        return web.json_response({"success": True, "event": event})

    async def handle_chat_messages_get(self, request):
        root = self._chat_project_root()
        if not root:
            return web.json_response({"error": "Откройте папку проекта"}, status=400)
        messages = load_ui_messages(root)
        return web.json_response({"success": True, "messages": messages})

    async def handle_chat_messages_save(self, request):
        root = self._chat_project_root()
        if not root:
            return web.json_response({"error": "Откройте папку проекта"}, status=400)
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)
        messages = data.get("messages") if isinstance(data, dict) else []
        result = save_ui_messages(root, messages if isinstance(messages, list) else [])
        status = 400 if result.get("error") else 200
        return web.json_response(result, status=status)

    async def handle_chat_sessions_list(self, request):
        root = self._chat_project_root()
        if not root:
            return web.json_response({"error": "Откройте папку проекта"}, status=400)
        return web.json_response({"success": True, "sessions": list_chat_sessions(root)})

    async def handle_chat_session_get(self, request):
        root = self._chat_project_root()
        if not root:
            return web.json_response({"error": "Откройте папку проекта"}, status=400)
        session_id = request.match_info.get("session_id", "")
        result = load_chat_session(root, session_id)
        status = 404 if result.get("error") else 200
        return web.json_response(result, status=status)

    async def handle_chat_archive(self, request):
        root = self._chat_project_root()
        if not root:
            return web.json_response({"error": "Откройте папку проекта"}, status=400)
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)
        messages = data.get("messages") if isinstance(data, dict) else []
        result = archive_current_chat(root, messages if isinstance(messages, list) else [])
        if result.get("success"):
            clear_ui_messages(root)
            from core.conversation_memory import save_history
            save_history(root, [])
        status = 400 if result.get("error") else 200
        return web.json_response(result, status=status)

    async def handle_create_project(self, request):
        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not available"})
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)

        parent_path = (data.get("parent_path") or "").strip()
        name = (data.get("name") or "").strip()
        description = (data.get("description") or "").strip()
        stack = (data.get("stack") or "python").strip()

        if not parent_path:
            return web.json_response({"error": "parent_path field required"}, status=400)

        result = create_project(Path(parent_path), name, description, stack=stack)
        if result.get("error"):
            return web.json_response(result, status=400)

        root_result = await self.orchestrator.set_project_root(result["root"])
        if not root_result.get("success"):
            return web.json_response(
                {"error": root_result.get("error") or "Не удалось открыть проект"},
                status=400,
            )

        runtime = self.orchestrator.get_ai_runtime_snapshot()
        result["ai_mode"] = runtime.get("mode")
        result["requires_online"] = True
        if runtime.get("mode") != "online":
            result["warning"] = (
                "Для создания целого проекта рекомендуется режим «Онлайн API» "
                "с подключённым ключом."
            )
        return web.json_response(result)

    async def handle_git_clone(self, request):
        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not available"})
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)

        url = str(data.get("url") or "").strip()
        parent_path = str(data.get("parent_path") or "").strip()
        if not url:
            return web.json_response({"error": "url field required"}, status=400)
        if not parent_path:
            return web.json_response({"error": "parent_path field required"}, status=400)

        result = clone_repository(url, Path(parent_path))
        if result.get("error"):
            return web.json_response(result, status=400)

        root_result = await self.orchestrator.set_project_root(result["root"])
        if not root_result.get("success"):
            return web.json_response(
                {"error": root_result.get("error") or "Репозиторий склонирован, но не удалось открыть папку"},
                status=400,
            )
        return web.json_response(result)

    def _git_root(self):
        if not self.file_service:
            return None
        return Path(self.file_service.project_root)

    async def handle_git_status(self, request):
        root = self._git_root()
        if root is None:
            return web.json_response({"error": "File service not available"}, status=400)
        result = await asyncio.to_thread(get_status, root)
        status = 400 if result.get("error") else 200
        return web.json_response(result, status=status)

    async def handle_git_init(self, request):
        root = self._git_root()
        if root is None:
            return web.json_response({"error": "File service not available"}, status=400)
        result = await asyncio.to_thread(init_repository, root)
        status = 400 if result.get("error") else 200
        return web.json_response(result, status=status)

    async def _git_paths_action(self, request, action):
        root = self._git_root()
        if root is None:
            return web.json_response({"error": "File service not available"}, status=400)
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)
        paths = data.get("paths") if isinstance(data, dict) else None
        if not isinstance(paths, list):
            path = data.get("path") if isinstance(data, dict) else None
            paths = [path] if path else []
        result = await asyncio.to_thread(action, root, paths)
        status = 400 if result.get("error") else 200
        return web.json_response(result, status=status)

    async def handle_git_stage(self, request):
        return await self._git_paths_action(request, stage_paths)

    async def handle_git_unstage(self, request):
        return await self._git_paths_action(request, unstage_paths)

    async def handle_git_discard(self, request):
        return await self._git_paths_action(request, discard_paths)

    async def handle_git_commit(self, request):
        root = self._git_root()
        if root is None:
            return web.json_response({"error": "File service not available"}, status=400)
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)
        message = str((data or {}).get("message") or "")
        result = await asyncio.to_thread(commit_staged, root, message)
        status = 400 if result.get("error") else 200
        return web.json_response(result, status=status)

    async def handle_git_push(self, request):
        root = self._git_root()
        if root is None:
            return web.json_response({"error": "File service not available"}, status=400)
        result = await asyncio.to_thread(push_repository, root)
        status = 400 if result.get("error") else 200
        return web.json_response(result, status=status)

    async def handle_skill_meta(self, request):
        """Справочник категорий и примеров команд (не подставляет скилы в проект)."""
        return web.json_response({
            "success": True,
            "categories": SKILL_CATEGORIES,
            "team_presets": TEAM_PRESETS,
        })

    async def handle_visio(self, request):
        if not self.file_service:
            return web.json_response({"error": "File service not available"})
        root = Path(self.file_service.project_root)
        return web.json_response(get_visio_payload(root))

    async def handle_list_personas(self, request):
        """HTTP endpoint: GET /api/personas"""
        if not self.file_service:
            return web.json_response({"error": "File service not available"})
        root = Path(self.file_service.project_root)
        ensure_personas_dir(root)
        personas = list_personas(root)
        return web.json_response({"success": True, "personas": personas})

    async def handle_create_persona(self, request):
        """HTTP endpoint: POST /api/personas -> {name, prompt}"""
        if not self.file_service:
            return web.json_response({"error": "File service not available"})

        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)

        name = data.get("name", "")
        prompt = data.get("prompt", "")
        category = data.get("category", "")

        root = Path(self.file_service.project_root)
        result = create_persona(root, name, prompt, category=category)
        status = 400 if result.get("error") else 200
        return web.json_response(result, status=status)

    async def handle_get_persona(self, request):
        """HTTP endpoint: GET /api/personas/{persona_id}"""
        if not self.file_service:
            return web.json_response({"error": "File service not available"})
        persona_id = request.match_info.get("persona_id", "")
        root = Path(self.file_service.project_root)
        name, body = resolve_persona_prompt(root, persona_id)
        if not body:
            return web.json_response({"error": f"Persona not found: {persona_id}"}, status=404)
        return web.json_response({
            "success": True,
            "id": persona_id,
            "name": name,
            "prompt": body,
        })

    async def handle_delete_persona(self, request):
        if not self.file_service:
            return web.json_response({"error": "File service not available"})
        persona_id = request.match_info.get("persona_id", "")
        root = Path(self.file_service.project_root)
        result = delete_persona(root, persona_id)
        status = 400 if result.get("error") else 200
        return web.json_response(result, status=status)

    async def handle_delete_pipeline(self, request):
        if not self.file_service:
            return web.json_response({"error": "File service not available"})
        pipeline_id = request.match_info.get("pipeline_id", "")
        root = Path(self.file_service.project_root)
        result = delete_pipeline(root, pipeline_id)
        status = 400 if result.get("error") else 200
        return web.json_response(result, status=status)

    async def handle_refresh_library(self, request):
        invalidate_cache()
        return web.json_response({"success": True})

    async def handle_create_pipeline(self, request):
        """HTTP endpoint: POST /api/pipelines"""
        if not self.file_service:
            return web.json_response({"error": "File service not available"})

        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)

        root = Path(self.file_service.project_root)
        result = create_pipeline(
            root,
            name=data.get("name", ""),
            description=data.get("description", ""),
            steps=data.get("steps") or [],
            limits=data.get("limits"),
        )
        status = 400 if result.get("error") else 200
        return web.json_response(result, status=status)

    async def handle_system_profile(self, request):
        root = Path(self.file_service.project_root) if self.file_service else None
        return web.json_response({"success": True, **profile_to_dict(root)})

    async def handle_set_gpu_preference(self, request):
        from core.gpu_preference import set_selected_gpu_id
        from core.ollama_lifecycle import is_using_desktop_ollama, restart_managed_ollama_serve

        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)
        result = set_selected_gpu_id(str(data.get("gpu_id") or ""))
        restarted = await restart_managed_ollama_serve()
        result["ollama_restarted"] = restarted
        result["ollama_using_desktop"] = is_using_desktop_ollama()
        return web.json_response(result)

    async def handle_get_web_access(self, request):
        from core.web_access import web_access_snapshot

        return web.json_response(web_access_snapshot())

    async def handle_set_web_access(self, request):
        from core.web_access import set_web_access_mode

        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"ok": False, "error": "Invalid JSON payload"}, status=400)
        return web.json_response(set_web_access_mode(str(data.get("mode") or "")))

    async def handle_get_coding_language(self, request):
        from core.coding_language import coding_language_snapshot

        if not self.file_service:
            return web.json_response({"error": "File service not available"}, status=503)
        root = Path(self.file_service.project_root)
        return web.json_response(coding_language_snapshot(root))

    async def handle_set_coding_language(self, request):
        from core.coding_language import set_coding_language

        if not self.file_service:
            return web.json_response({"error": "File service not available"}, status=503)
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)
        root = Path(self.file_service.project_root)
        return web.json_response(
            set_coding_language(root, str(data.get("language") or ""))
        )

    async def handle_get_coding_engine(self, request):
        from core.coding_engine import coding_engine_snapshot

        root = self.orchestrator._app_root()
        return web.json_response(coding_engine_snapshot(root))

    async def handle_set_coding_engine(self, request):
        from core.coding_engine import coding_engine_snapshot, set_coding_engine

        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)
        root = self.orchestrator._app_root()
        engine = set_coding_engine(root, str(data.get("engine") or ""))
        self.orchestrator._coding_engine = engine
        return web.json_response(coding_engine_snapshot(root))

    async def handle_set_workload_limits(self, request):
        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not available"}, status=503)
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)
        result = self.orchestrator.update_workload_limits(data)
        return web.json_response(result)

    async def handle_system_shutdown(self, request):
        from core.shutdown_service import shutdown_corex_runtime

        result = await shutdown_corex_runtime()
        return web.json_response(result)

    async def handle_list_ai_providers(self, request):
        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not available"}, status=503)
        return web.json_response({
            "success": True,
            **self.orchestrator.list_ai_providers(),
        })

    async def handle_set_ai_provider(self, request):
        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not available"}, status=503)
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)

        provider_id = (data.get("provider_id") or data.get("id") or "").strip()
        if not provider_id:
            return web.json_response({"error": "provider_id field required"}, status=400)

        result = self.orchestrator.set_ai_provider(provider_id)
        status = 200 if result.get("success") else 400
        return web.json_response({"success": result.get("success", False), **result}, status=status)

    async def handle_ai_runtime(self, request):
        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not available"}, status=503)
        return web.json_response({
            "success": True,
            **self.orchestrator.get_ai_runtime_snapshot(),
        })

    async def handle_set_ai_mode(self, request):
        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not available"}, status=503)
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)
        mode = (data.get("mode") or "").strip().lower()
        if not mode:
            return web.json_response({"error": "mode field required"}, status=400)
        result = self.orchestrator.set_ai_mode(mode)
        status = 200 if result.get("success") else 400
        payload = {"success": result.get("success", False), **result}
        if result.get("success"):
            try:
                self.orchestrator.ai_runtime_service.apply_active_client(
                    self.orchestrator.ollama,
                    self.orchestrator.online,
                )
            except RuntimeError as exc:
                payload["warning"] = str(exc)
            payload.update(self.orchestrator.get_ai_runtime_snapshot())
        return web.json_response(payload, status=status)

    async def handle_create_online_provider(self, request):
        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not available"}, status=503)
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)
        result = self.orchestrator.create_online_provider(data)
        status = 200 if result.get("success") else 400
        payload = {"success": result.get("success", False), **result}
        if result.get("success"):
            payload.update(self.orchestrator.get_ai_runtime_snapshot())
        return web.json_response(payload, status=status)

    async def handle_set_online_provider(self, request):
        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not available"}, status=503)
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)
        provider_id = (data.get("provider_id") or data.get("id") or "").strip()
        if not provider_id:
            return web.json_response({"error": "provider_id field required"}, status=400)
        result = self.orchestrator.set_online_provider(provider_id)
        status = 200 if result.get("success") else 400
        payload = {"success": result.get("success", False), **result}
        if result.get("success"):
            payload.update(self.orchestrator.get_ai_runtime_snapshot())
        return web.json_response(payload, status=status)

    async def handle_delete_online_provider(self, request):
        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not available"}, status=503)
        provider_id = (request.match_info.get("provider_id") or "").strip()
        if not provider_id:
            return web.json_response({"error": "provider_id required"}, status=400)
        result = self.orchestrator.delete_online_provider(provider_id)
        status = 200 if result.get("success") else 400
        payload = {"success": result.get("success", False), **result}
        if result.get("success"):
            payload.update(self.orchestrator.get_ai_runtime_snapshot())
        return web.json_response(payload, status=status)

    async def handle_ollama_models(self, request):
        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not available"}, status=503)
        payload = await self.orchestrator.get_ollama_models_snapshot()
        status = 200 if payload.get("success", False) else 503
        return web.json_response({"success": payload.get("success", False), **payload}, status=status)

    async def handle_ollama_pull(self, request):
        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not available"}, status=503)
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)
        provider_id = (data.get("provider_id") or data.get("id") or "").strip() or None
        model_name = (data.get("model_name") or "").strip() or None
        wait = bool(data.get("wait"))
        if wait:
            result = await self.orchestrator.pull_ollama_model(provider_id=provider_id, model_name=model_name)
        else:
            result = await self.orchestrator.start_ollama_pull(provider_id=provider_id, model_name=model_name)
        status = 200 if result.get("success") else 400
        return web.json_response({"success": result.get("success", False), **result}, status=status)

    async def handle_ollama_pull_progress(self, request):
        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not available"}, status=503)
        job_id = (request.rel_url.query.get("job_id") or "").strip()
        if not job_id:
            return web.json_response({"error": "job_id required"}, status=400)
        result = self.orchestrator.get_ollama_pull_progress(job_id)
        status = 200 if result.get("found", False) else 404
        return web.json_response(result, status=status)

    async def handle_ollama_delete(self, request):
        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not available"}, status=503)
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)
        provider_id = (data.get("provider_id") or data.get("id") or "").strip() or None
        model_name = (data.get("model_name") or "").strip() or None
        if not provider_id and not model_name:
            return web.json_response({"error": "provider_id or model_name required"}, status=400)
        result = await self.orchestrator.delete_ollama_model(
            provider_id=provider_id,
            model_name=model_name,
        )
        status = 200 if result.get("success") else 400
        return web.json_response({"success": result.get("success", False), **result}, status=status)

    async def handle_knowledge_meta(self, request):
        if not self.file_service:
            return web.json_response({"error": "File service not available"}, status=503)
        root = Path(self.file_service.project_root)
        task = request.rel_url.query.get("task", "")
        persona_id = request.rel_url.query.get("persona_id")
        return web.json_response({
            "success": True,
            **knowledge_meta(root, task, persona_id),
        })

    async def handle_remediate_error(self, request):
        if not self.file_service:
            return web.json_response({"error": "File service not available"}, status=503)
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)

        path = (data.get("path") or "").strip()
        error_text = (data.get("error") or "").strip()
        mode = (data.get("mode") or "auto").strip().lower()
        if mode not in {"auto", "fix", "stub"}:
            mode = "auto"
        if not path:
            return web.json_response({"error": "path field required"}, status=400)

        root = Path(self.file_service.project_root)
        result = remediate_python_error(root, path, error_text, mode=mode)
        status = 200 if result.get("ok") else 400
        return web.json_response(result, status=status)

    async def handle_terminal_run_file(self, request):
        if not self.file_service:
            return web.json_response({"error": "File service not available"}, status=503)
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)

        path = (data.get("path") or "").strip()
        if not path:
            return web.json_response({"error": "path field required"}, status=400)

        try:
            root = Path(self.file_service.project_root)
            result = await run_file(root, path)
            return web.json_response(result)
        except Exception as exc:
            return web.json_response({
                "success": False,
                "output": "",
                "error": str(exc),
                "exit_code": -1,
            }, status=500)

    async def handle_terminal_exec(self, request):
        if not self.file_service:
            return web.json_response({"error": "File service not available"}, status=503)
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)

        command = (data.get("command") or "").strip()
        if not command:
            return web.json_response({"error": "command field required"}, status=400)

        try:
            root = Path(self.file_service.project_root)
            cwd = data.get("cwd")
            result = await run_command(root, command, cwd=cwd)
            return web.json_response(result)
        except Exception as exc:
            return web.json_response({
                "success": False,
                "output": "",
                "error": str(exc),
                "exit_code": -1,
            }, status=500)

    async def handle_terminal_session_start(self, request):
        if not self.file_service:
            return web.json_response({"error": "File service not available"}, status=503)
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)
        root = Path(self.file_service.project_root)
        path = (data.get("path") or "").strip()
        command = (data.get("command") or "").strip()
        cwd = data.get("cwd")
        try:
            if path:
                result = start_terminal_file(self.terminal_session, root, path)
            elif command:
                result = start_terminal_command(self.terminal_session, root, command, cwd=cwd)
            else:
                return web.json_response({"error": "path or command required"}, status=400)
            return web.json_response(result)
        except Exception as exc:
            return web.json_response({"success": False, "running": False, "error": str(exc)}, status=500)

    async def handle_terminal_session_stdin(self, request):
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)
        text = data.get("text")
        if text is None:
            text = ""
        return web.json_response(self.terminal_session.write_stdin(str(text)))

    async def handle_terminal_session_poll(self, request):
        result = self.terminal_session.snapshot()
        if not result.get("running") and self.file_service:
            path = request.query.get("path") or ""
            if path:
                result = annotate_python_hints(result, Path(self.file_service.project_root), path)
        return web.json_response(result)

    async def handle_terminal_session_kill(self, request):
        return web.json_response(self.terminal_session.kill())

    async def handle_get_root(self, request):
        """HTTP endpoint: GET /api/files/root — текущая открытая папка проекта."""
        if not self.file_service:
            return web.json_response({"error": "File service not available"})
        return web.json_response({
            "success": True,
            "root": str(self.file_service.project_root.resolve()),
        })

    async def handle_set_root(self, request):
        """HTTP endpoint: POST /api/files/set_root."""
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)

        path = data.get('path')
        if not path:
            return web.json_response({"error": "path field required"}, status=400)

        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not available"})

        result = await self.orchestrator.set_project_root(path)
        return web.json_response(result)

    @staticmethod
    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == 'OPTIONS':
            return web.Response(status=204, headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
            })

        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    async def handle_options(self, request):
        return web.Response(status=204, headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        })

    async def handle_health(self, request):
        return web.json_response({
            "ok": True,
            "backend_version": COREX_BACKEND_VERSION,
            "task_routing": True,
            "library_agents": len(list_library_agents()),
            "library_teams": len(list_library_teams()),
        })

    async def handle_system_ready(self, request):
        if not self.orchestrator:
            return web.json_response({
                "ok": False,
                "ready": False,
                "phase": "backend",
                "message": "Backend инициализируется…",
            })
        from core.startup_readiness import evaluate_startup_readiness

        payload = await evaluate_startup_readiness(self.orchestrator)
        return web.json_response({"ok": True, **payload})

    def create_app(self):
        app = web.Application(middlewares=[self.cors_middleware])
        app.router.add_get('/ws', self.handler)
        app.router.add_get('/health', self.handle_health)
        app.router.add_get('/api/system/ready', self.handle_system_ready)
        
        # File service endpoints
        if self.file_service:
            app.router.add_get('/api/files', self.handle_list_files)
            app.router.add_get('/api/files/read', self.handle_read_file)
            app.router.add_get('/api/files/mentions', self.handle_file_mentions)
            app.router.add_get('/api/files/search', self.handle_search_files)
            app.router.add_get('/api/files/tree', self.handle_file_tree)
            app.router.add_get('/api/files/root', self.handle_get_root)
            app.router.add_get('/api/agents', self.handle_list_agents)
            app.router.add_post('/api/agents', self.handle_create_agent)
            app.router.add_delete('/api/agents/{agent_id}', self.handle_delete_agent)
            app.router.add_get('/api/pipelines', self.handle_list_pipelines)
            app.router.add_post('/api/pipelines', self.handle_create_pipeline)
            app.router.add_delete('/api/pipelines/{pipeline_id}', self.handle_delete_pipeline)
            app.router.add_get('/api/skills/meta', self.handle_skill_meta)
            app.router.add_get('/api/visio', self.handle_visio)
            app.router.add_post('/api/skills/refresh', self.handle_refresh_library)
            app.router.add_get('/api/personas', self.handle_list_personas)
            app.router.add_post('/api/personas', self.handle_create_persona)
            app.router.add_get('/api/personas/{persona_id}', self.handle_get_persona)
            app.router.add_delete('/api/personas/{persona_id}', self.handle_delete_persona)
            app.router.add_post('/api/files/set_root', self.handle_set_root)
            app.router.add_post('/api/files/create', self.handle_create_file)
            app.router.add_post('/api/files/delete', self.handle_delete_file)
            app.router.add_get('/api/system/profile', self.handle_system_profile)
            app.router.add_post('/api/system/gpu-preference', self.handle_set_gpu_preference)
            app.router.add_get('/api/system/web-access', self.handle_get_web_access)
            app.router.add_post('/api/system/web-access', self.handle_set_web_access)
            app.router.add_get('/api/project/coding-language', self.handle_get_coding_language)
            app.router.add_post('/api/project/coding-language', self.handle_set_coding_language)
            app.router.add_get('/api/project/coding-engine', self.handle_get_coding_engine)
            app.router.add_post('/api/project/coding-engine', self.handle_set_coding_engine)
            app.router.add_post('/api/system/workload-limits', self.handle_set_workload_limits)
            app.router.add_post('/api/system/shutdown', self.handle_system_shutdown)
            app.router.add_get('/api/ai/providers', self.handle_list_ai_providers)
            app.router.add_post('/api/ai/provider', self.handle_set_ai_provider)
            app.router.add_get('/api/ai/runtime', self.handle_ai_runtime)
            app.router.add_post('/api/ai/mode', self.handle_set_ai_mode)
            app.router.add_post('/api/ai/online/providers', self.handle_create_online_provider)
            app.router.add_post('/api/ai/online/provider', self.handle_set_online_provider)
            app.router.add_delete('/api/ai/online/providers/{provider_id}', self.handle_delete_online_provider)
            app.router.add_get('/api/ai/ollama/models', self.handle_ollama_models)
            app.router.add_post('/api/ai/ollama/pull', self.handle_ollama_pull)
            app.router.add_get('/api/ai/ollama/pull/progress', self.handle_ollama_pull_progress)
            app.router.add_post('/api/ai/ollama/delete', self.handle_ollama_delete)
            app.router.add_get('/api/ai/usage', self.handle_ai_usage)
            app.router.add_post('/api/ai/usage/limits', self.handle_set_ai_usage_limits)
            app.router.add_post('/api/ai/usage/reset', self.handle_reset_ai_usage)
            app.router.add_get('/api/trace/errors', self.handle_trace_errors)
            app.router.add_get('/api/trace/task/{task_id}', self.handle_trace_task)
            app.router.add_get('/api/trace/task/{task_id}/event/{event_id}', self.handle_trace_event)
            app.router.add_get('/api/chat/messages', self.handle_chat_messages_get)
            app.router.add_post('/api/chat/messages', self.handle_chat_messages_save)
            app.router.add_get('/api/chat/sessions', self.handle_chat_sessions_list)
            app.router.add_get('/api/chat/sessions/{session_id}', self.handle_chat_session_get)
            app.router.add_post('/api/chat/archive', self.handle_chat_archive)
            app.router.add_post('/api/projects/create', self.handle_create_project)
            app.router.add_post('/api/git/clone', self.handle_git_clone)
            app.router.add_get('/api/git/status', self.handle_git_status)
            app.router.add_post('/api/git/init', self.handle_git_init)
            app.router.add_post('/api/git/stage', self.handle_git_stage)
            app.router.add_post('/api/git/unstage', self.handle_git_unstage)
            app.router.add_post('/api/git/discard', self.handle_git_discard)
            app.router.add_post('/api/git/commit', self.handle_git_commit)
            app.router.add_post('/api/git/push', self.handle_git_push)
            app.router.add_get('/api/knowledge', self.handle_knowledge_meta)
            app.router.add_post('/api/errors/remediate', self.handle_remediate_error)
            app.router.add_post('/api/terminal/run', self.handle_terminal_run_file)
            app.router.add_post('/api/terminal/exec', self.handle_terminal_exec)
            app.router.add_post('/api/terminal/session/start', self.handle_terminal_session_start)
            app.router.add_post('/api/terminal/session/stdin', self.handle_terminal_session_stdin)
            app.router.add_get('/api/terminal/session', self.handle_terminal_session_poll)
            app.router.add_post('/api/terminal/session/kill', self.handle_terminal_session_kill)
            app.router.add_route('OPTIONS', '/api/files', self.handle_options)
            app.router.add_route('OPTIONS', '/api/system/{tail:.*}', self.handle_options)
            app.router.add_route('OPTIONS', '/api/errors/{tail:.*}', self.handle_options)
            app.router.add_route('OPTIONS', '/api/terminal/{tail:.*}', self.handle_options)
            app.router.add_route('OPTIONS', '/api/files/{tail:.*}', self.handle_options)
            app.router.add_route('OPTIONS', '/api/git/{tail:.*}', self.handle_options)
        
        return app

    async def handle_create_file(self, request):
        """HTTP endpoint: POST /api/files/create -> {path, content?, isDir?}"""
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)

        path = data.get('path')
        content = data.get('content', '')
        is_dir = data.get('isDir', False)

        if not path:
            return web.json_response({"error": "path field required"}, status=400)

        if is_dir:
            result = await self.file_service.create_directory(path)
        else:
            result = await self.file_service.write_file(path, content)

        return web.json_response(result)

    async def handle_delete_file(self, request):
        """HTTP endpoint: POST /api/files/delete -> {path}"""
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON payload"}, status=400)

        path = data.get('path')
        if not path:
            return web.json_response({"error": "path field required"}, status=400)

        result = await self.file_service.delete_file(path)
        return web.json_response(result)
