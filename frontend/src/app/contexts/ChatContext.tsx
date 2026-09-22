import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { getWebSocketUrl, waitForBackend } from '../utils/api';
import {
  createPersona,
  deletePersona,
  fetchPersonas,
  getSavedPersonaId,
  refreshSkillsLibrary,
  savePersonaId,
  type Persona,
} from '../utils/personas';
import {
  createAgent,
  deleteAgent,
  fetchAgents,
  getSavedAgentId,
  saveAgentId,
  type Agent,
} from '../utils/agents';
import {
  createPipeline,
  deletePipeline,
  fetchPipelines,
  getSavedPipelineId,
  getSavedWorkMode,
  savePipelineId,
  saveWorkMode,
  type Pipeline,
  type PipelineStepInput,
  type WorkMode,
} from '../utils/pipelines';
import {
  CODING_LANGUAGES,
  fetchCodingLanguage,
  getSavedCodingLanguage,
  saveCodingLanguage,
  saveCodingLanguageLocal,
  type CodingLanguageId,
  type CodingLanguageOption,
} from '../utils/codingLanguage';
import {
  CODING_ENGINES,
  fetchCodingEngine,
  getSavedCodingEngine,
  persistCodingEngine,
  saveCodingEngineLocal,
  type CodingEngineId,
  type CodingEngineOption,
} from '../utils/codingEngine';
import { syncProjectRoot } from '../utils/projectRoot';
import {
  archiveChatSession,
  fetchChatMessages,
  fetchChatSession,
  fetchChatSessions,
  saveChatMessages,
  type ChatSessionSummary,
} from '../utils/chatHistory';
import type { EditorPatchEvent } from '../types/editorPatch';
import type { TraceErrorRecord, TraceEvent } from '../types/trace';
import { fetchTraceErrors } from '../utils/traceApi';
import type { ChatMessage } from '../types/chatMessage';
import { isCorexInternalPath } from '../utils/corexInternal';

export type { ChatMessage };

export type ConnectionStatus = 'connecting' | 'open' | 'closed' | 'error';

interface ChatContextValue {
  messages: ChatMessage[];
  thoughts: string[];
  isThinking: boolean;
  connectionStatus: ConnectionStatus;
  personas: Persona[];
  selectedPersonaId: string;
  setSelectedPersonaId: (personaId: string) => void;
  addPersona: (name: string, prompt: string, category?: string) => Promise<Persona | null>;
  addAgent: (name: string, prompt: string, categoryRu?: string) => Promise<Agent | null>;
  addPipeline: (
    name: string,
    description: string,
    steps: PipelineStepInput[],
  ) => Promise<Pipeline | null>;
  removePersona: (personaId: string) => Promise<void>;
  removeAgent: (agentId: string) => Promise<void>;
  removePipeline: (pipelineId: string) => Promise<void>;
  refreshSkills: () => Promise<void>;
  workMode: WorkMode;
  setWorkMode: (mode: WorkMode) => void;
  agents: Agent[];
  selectedAgentId: string;
  setSelectedAgentId: (id: string) => void;
  pipelines: Pipeline[];
  selectedPipelineId: string;
  setSelectedPipelineId: (id: string) => void;
  codingLanguage: CodingLanguageId;
  codingLanguages: CodingLanguageOption[];
  setCodingLanguage: (id: CodingLanguageId) => void;
  codingEngine: CodingEngineId;
  codingEngines: CodingEngineOption[];
  setCodingEngine: (id: CodingEngineId) => void;
  sendMessage: (text: string, overrides?: { projectRoot?: string }) => Promise<boolean>;
  stopGeneration: () => void;
  refreshConnection: () => void;
  clearThinking: () => void;
  editorPatch: EditorPatchEvent | null;
  clearEditorPatch: () => void;
  traceEvents: TraceEvent[];
  traceTaskId: string | null;
  traceErrors: TraceErrorRecord[];
  highlightTraceEventId: string | null;
  jumpToTraceEvent: (eventId: string) => void;
  refreshTraceErrors: () => Promise<void>;
  clearTrace: () => void;
  chatSessions: ChatSessionSummary[];
  historyLoaded: boolean;
  refreshChatSessions: () => Promise<void>;
  openChatSession: (sessionId: string) => Promise<void>;
  startNewChat: () => Promise<void>;
  reloadSavedChat: () => Promise<void>;
}

const ChatContext = createContext<ChatContextValue | null>(null);

const MAX_TRACE_EVENTS = 160;

function createId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
}

const RECONNECT_DELAY_MS = 3000;

function shouldStopThinking(sender: string, text: string): boolean {
  if (sender === 'CoreX Status') {
    return true;
  }
  if (sender === 'CoreX Error') {
    const trimmed = text.trim();
    return (
      trimmed.startsWith('[CoreX Critical Error]')
      || trimmed.includes('Ошибка выполнения задачи')
      || trimmed.includes('не вернула корректный JSON')
      || trimmed.includes('Сначала откройте папку')
      || trimmed.includes('Не удалось открыть проект')
      || trimmed.includes('Лимит токенов')
    );
  }
  const trimmed = text.trim();
  return trimmed.startsWith('[CoreX Critical Error]');
}

interface ChatProviderProps {
  children: ReactNode;
  projectRoot?: string;
}

export function ChatProvider({ children, projectRoot = '' }: ChatProviderProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [thoughts, setThoughts] = useState<string[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting');
  const [socketKey, setSocketKey] = useState(0);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [selectedPersonaId, setSelectedPersonaIdState] = useState('');
  const [workMode, setWorkModeState] = useState<WorkMode>('single');
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgentId, setSelectedAgentIdState] = useState('');
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [selectedPipelineId, setSelectedPipelineIdState] = useState('');
  const [codingLanguage, setCodingLanguageState] = useState<CodingLanguageId>('auto');
  const [codingLanguages, setCodingLanguages] = useState<CodingLanguageOption[]>(CODING_LANGUAGES);
  const [codingEngine, setCodingEngineState] = useState<CodingEngineId>(getSavedCodingEngine());
  const [codingEngines, setCodingEngines] = useState<CodingEngineOption[]>(CODING_ENGINES);
  const [editorPatch, setEditorPatch] = useState<EditorPatchEvent | null>(null);
  const [traceEvents, setTraceEvents] = useState<TraceEvent[]>([]);
  const [traceTaskId, setTraceTaskId] = useState<string | null>(null);
  const [traceErrors, setTraceErrors] = useState<TraceErrorRecord[]>([]);
  const [highlightTraceEventId, setHighlightTraceEventId] = useState<string | null>(null);
  const [chatSessions, setChatSessions] = useState<ChatSessionSummary[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);

  const skipSaveRef = useRef(false);
  const isThinkingRef = useRef(false);
  const archivingRef = useRef(false);
  const inflightTasksRef = useRef(0);
  const saveTimerRef = useRef<number | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const selectedPersonaRef = useRef(selectedPersonaId);
  const selectedAgentRef = useRef(selectedAgentId);
  const workModeRef = useRef(workMode);
  const pipelineIdRef = useRef(selectedPipelineId);
  const codingLanguageRef = useRef(codingLanguage);
  const codingEngineRef = useRef(codingEngine);
  selectedPersonaRef.current = selectedPersonaId;
  selectedAgentRef.current = selectedAgentId;
  workModeRef.current = workMode;
  pipelineIdRef.current = selectedPipelineId;
  codingLanguageRef.current = codingLanguage;
  codingEngineRef.current = codingEngine;

  const setWorkMode = useCallback(
    (mode: WorkMode) => {
      setWorkModeState(mode);
      if (projectRoot) saveWorkMode(projectRoot, mode);
    },
    [projectRoot],
  );

  const setSelectedPipelineId = useCallback(
    (pipelineId: string) => {
      setSelectedPipelineIdState(pipelineId);
      if (projectRoot) savePipelineId(projectRoot, pipelineId);
    },
    [projectRoot],
  );

  const setSelectedPersonaId = useCallback(
    (personaId: string) => {
      setSelectedPersonaIdState(personaId);
      if (projectRoot) {
        savePersonaId(projectRoot, personaId);
      }
    },
    [projectRoot],
  );

  const setSelectedAgentId = useCallback(
    (agentId: string) => {
      setSelectedAgentIdState(agentId);
      if (projectRoot) {
        saveAgentId(projectRoot, agentId);
      }
    },
    [projectRoot],
  );

  const setCodingLanguage = useCallback(
    (language: CodingLanguageId) => {
      codingLanguageRef.current = language;
      setCodingLanguageState(language);
      if (projectRoot) {
        saveCodingLanguageLocal(projectRoot, language);
        void saveCodingLanguage(language);
      }
    },
    [projectRoot],
  );

  const setCodingEngine = useCallback((engine: CodingEngineId) => {
    codingEngineRef.current = engine;
    setCodingEngineState(engine);
    saveCodingEngineLocal(engine);
    void persistCodingEngine(engine);
  }, []);

  const refreshPersonas = useCallback(async () => {
    try {
      const loaded = await fetchPersonas();
      setPersonas(loaded);
      return loaded;
    } catch (error) {
      console.error('[ChatContext] Failed to load personas:', error);
      return [];
    }
  }, []);

  const refreshPipelines = useCallback(async () => {
    try {
      const loaded = await fetchPipelines();
      setPipelines(loaded);
      return loaded;
    } catch (error) {
      console.error('[ChatContext] Failed to load pipelines:', error);
      return [];
    }
  }, []);

  const refreshAgents = useCallback(async () => {
    try {
      const loaded = await fetchAgents();
      setAgents(loaded);
      return loaded;
    } catch (error) {
      console.error('[ChatContext] Failed to load agents:', error);
      return [];
    }
  }, []);

  const refreshSkills = useCallback(async () => {
    await refreshSkillsLibrary();
    await Promise.all([refreshPersonas(), refreshAgents(), refreshPipelines()]);
  }, [refreshPersonas, refreshAgents, refreshPipelines]);

  const addPersona = useCallback(
    async (name: string, prompt: string, category = '') => {
      const result = await createPersona(name, prompt, category);
      if (result.error || !result.persona) {
        throw new Error(result.error || 'Не удалось создать скил');
      }
      await refreshPersonas();
      setSelectedPersonaId(result.persona.id);
      return result.persona;
    },
    [refreshPersonas, setSelectedPersonaId],
  );

  const addAgent = useCallback(
    async (name: string, prompt: string, categoryRu = 'Мои агенты') => {
      const result = await createAgent(name, prompt, categoryRu);
      if (result.error || !result.agent) {
        throw new Error(result.error || 'Не удалось создать агента');
      }
      await refreshAgents();
      setSelectedAgentId(result.agent.id);
      setWorkMode('agent');
      return result.agent;
    },
    [refreshAgents, setSelectedAgentId, setWorkMode],
  );

  const addPipeline = useCallback(
    async (name: string, description: string, steps: PipelineStepInput[]) => {
      const result = await createPipeline(name, description, steps);
      if (result.error || !result.pipeline) {
        throw new Error(result.error || 'Не удалось создать команду');
      }
      const loaded = await refreshPipelines();
      if (loaded.some((p) => p.id === result.pipeline!.id)) {
        setSelectedPipelineId(result.pipeline.id);
        setWorkMode('pipeline');
      }
      return result.pipeline;
    },
    [refreshPipelines, setSelectedPipelineId, setWorkMode],
  );

  const removePersona = useCallback(
    async (personaId: string) => {
      const result = await deletePersona(personaId);
      if (result.error) {
        throw new Error(result.error);
      }
      const loaded = await refreshPersonas();
      if (selectedPersonaId === personaId) {
        setSelectedPersonaIdState('');
        if (projectRoot) savePersonaId(projectRoot, '');
      }
      void loaded;
    },
    [projectRoot, refreshPersonas, selectedPersonaId],
  );

  const removeAgent = useCallback(
    async (agentId: string) => {
      const result = await deleteAgent(agentId);
      if (result.error) {
        throw new Error(result.error);
      }
      const loaded = await refreshAgents();
      if (selectedAgentId === agentId) {
        setSelectedAgentIdState('');
        if (projectRoot) saveAgentId(projectRoot, '');
      }
      void loaded;
    },
    [projectRoot, refreshAgents, selectedAgentId],
  );

  const removePipeline = useCallback(
    async (pipelineId: string) => {
      const result = await deletePipeline(pipelineId);
      if (result.error) {
        throw new Error(result.error);
      }
      const loaded = await refreshPipelines();
      if (selectedPipelineId === pipelineId) {
        setSelectedPipelineIdState('');
        if (projectRoot) savePipelineId(projectRoot, '');
      }
      void loaded;
    },
    [projectRoot, refreshPipelines, selectedPipelineId],
  );

  const refreshChatSessions = useCallback(async () => {
    if (!projectRoot) {
      setChatSessions([]);
      return;
    }
    const sessions = await fetchChatSessions();
    setChatSessions(sessions);
  }, [projectRoot]);

  const reloadSavedChat = useCallback(async () => {
    if (isThinkingRef.current) {
      return;
    }
    if (!projectRoot) {
      setMessages([]);
      setHistoryLoaded(false);
      return;
    }
    skipSaveRef.current = true;
    const loaded = await fetchChatMessages();
    setMessages(loaded);
    setHistoryLoaded(true);
    skipSaveRef.current = false;
    await refreshChatSessions();
  }, [projectRoot, refreshChatSessions]);

  const openChatSession = useCallback(
    async (sessionId: string) => {
      if (isThinkingRef.current) {
        return;
      }
      skipSaveRef.current = true;
      const loaded = await fetchChatSession(sessionId);
      setMessages(loaded);
      setHistoryLoaded(true);
      skipSaveRef.current = false;
    },
    [],
  );

  const startNewChat = useCallback(async () => {
    if (archivingRef.current || isThinkingRef.current) {
      return;
    }
    archivingRef.current = true;
    try {
      if (messages.length > 0 && projectRoot) {
        await archiveChatSession(messages);
        await refreshChatSessions();
      }
      skipSaveRef.current = true;
      setMessages([]);
      setHistoryLoaded(true);
      skipSaveRef.current = false;
      if (projectRoot) {
        await saveChatMessages([]);
      }
    } finally {
      archivingRef.current = false;
    }
  }, [messages, projectRoot, refreshChatSessions]);

  useEffect(() => {
    isThinkingRef.current = isThinking;
  }, [isThinking]);

  useEffect(() => {
    if (!projectRoot) {
      setMessages([]);
      setChatSessions([]);
      setHistoryLoaded(false);
      return;
    }

    if (isThinkingRef.current) {
      return;
    }

    void reloadSavedChat();
  }, [projectRoot, reloadSavedChat]);

  useEffect(() => {
    if (!projectRoot || !historyLoaded || skipSaveRef.current) {
      return;
    }

    if (saveTimerRef.current !== null) {
      window.clearTimeout(saveTimerRef.current);
    }

    saveTimerRef.current = window.setTimeout(() => {
      void saveChatMessages(messages);
    }, 1200);

    return () => {
      if (saveTimerRef.current !== null) {
        window.clearTimeout(saveTimerRef.current);
      }
    };
  }, [messages, projectRoot, historyLoaded]);

  useEffect(() => {
    if (!projectRoot) {
      setPersonas([]);
      setAgents([]);
      setPipelines([]);
      setSelectedPersonaIdState('');
      setSelectedAgentIdState('');
      setSelectedPipelineIdState('');
      setWorkModeState('single');
      setCodingLanguageState('auto');
      return;
    }

    setWorkModeState(getSavedWorkMode(projectRoot));
    setCodingLanguageState(getSavedCodingLanguage(projectRoot));
    setCodingEngineState(getSavedCodingEngine());

    void (async () => {
      await refreshSkillsLibrary();
      const [loadedPersonas, loadedAgents, loadedPipelines, languageSnapshot, engineSnapshot] =
        await Promise.all([
          refreshPersonas(),
          fetchAgents(),
          fetchPipelines(),
          fetchCodingLanguage(),
          fetchCodingEngine(),
        ]);
      setAgents(loadedAgents);
      setPipelines(loadedPipelines);
      if (languageSnapshot.languages?.length) {
        setCodingLanguages(languageSnapshot.languages);
      }
      if (languageSnapshot.language) {
        setCodingLanguageState(languageSnapshot.language);
        saveCodingLanguageLocal(projectRoot, languageSnapshot.language);
      }
      if (engineSnapshot.engines?.length) {
        setCodingEngines(engineSnapshot.engines);
      }
      if (engineSnapshot.engine) {
        setCodingEngineState(engineSnapshot.engine);
        saveCodingEngineLocal(engineSnapshot.engine);
      }

      const savedPersona = getSavedPersonaId(projectRoot);
      if (savedPersona && loadedPersonas.some((p) => p.id === savedPersona)) {
        setSelectedPersonaIdState(savedPersona);
      } else {
        setSelectedPersonaIdState('');
      }

      const savedAgent = getSavedAgentId(projectRoot);
      if (savedAgent && loadedAgents.some((a) => a.id === savedAgent)) {
        setSelectedAgentIdState(savedAgent);
      } else {
        setSelectedAgentIdState('');
      }

      const savedPipeline = getSavedPipelineId(projectRoot);
      if (savedPipeline && loadedPipelines.some((p) => p.id === savedPipeline)) {
        setSelectedPipelineIdState(savedPipeline);
      } else {
        setSelectedPipelineIdState('');
      }
    })();
  }, [projectRoot, refreshPersonas]);
  const reconnectTimerRef = useRef<number | null>(null);
  const manualCloseRef = useRef(false);

  const scheduleReconnect = useCallback(() => {
    if (manualCloseRef.current || reconnectTimerRef.current !== null) {
      return;
    }

    reconnectTimerRef.current = window.setTimeout(() => {
      reconnectTimerRef.current = null;
      setSocketKey((prev) => prev + 1);
    }, RECONNECT_DELAY_MS);
  }, []);

  const refreshConnection = useCallback(() => {
    manualCloseRef.current = false;
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    setSocketKey((prev) => prev + 1);
  }, []);

  const clearTrace = useCallback(() => {
    setTraceEvents([]);
    setTraceTaskId(null);
    setTraceErrors([]);
    setHighlightTraceEventId(null);
  }, []);

  const pushTraceError = useCallback((error: TraceErrorRecord) => {
    setTraceErrors((prev) => {
      if (prev.some((item) => item.id === error.id)) {
        return prev;
      }
      const next = [...prev, error];
      return next.length > 120 ? next.slice(-120) : next;
    });
  }, []);

  const jumpToTraceEvent = useCallback((eventId: string) => {
    setHighlightTraceEventId(eventId);
    window.setTimeout(() => setHighlightTraceEventId(null), 2600);
  }, []);

  const refreshTraceErrors = useCallback(async () => {
    const taskId = traceTaskId;
    if (!taskId) {
      return;
    }
    try {
      const errors = await fetchTraceErrors(taskId);
      if (errors.length) {
        setTraceErrors(errors);
      }
    } catch {
      // ignore — live WS errors still work
    }
  }, [traceTaskId]);

  const pushTraceEvent = useCallback((raw: TraceEvent) => {
    setTraceTaskId(raw.task_id);
    setTraceEvents((prev) => {
      const next = [...prev, raw];
      return next.length > MAX_TRACE_EVENTS ? next.slice(-MAX_TRACE_EVENTS) : next;
    });
    if (raw.status === 'error') {
      pushTraceError({
        id: `evt-${raw.id}`,
        task_id: raw.task_id,
        event_id: raw.id,
        ts: raw.ts,
        label: raw.label,
        message: raw.detail?.body?.slice(0, 240) || raw.label,
        kind: raw.kind,
        node: raw.node,
      });
    }
  }, [pushTraceError]);

  useEffect(() => {
    manualCloseRef.current = false;
    let disposed = false;
    let socket: WebSocket | null = null;

    const connect = async () => {
      setConnectionStatus('connecting');
      await waitForBackend();

      if (disposed) {
        return;
      }

      socket = new WebSocket(getWebSocketUrl());
      socketRef.current = socket;

      socket.onopen = () => {
        if (!disposed) {
          setConnectionStatus('open');
        }
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as {
            target?: string;
            sender?: string;
            text?: string;
            model?: string;
            action?: string;
            path?: string;
            content?: string;
            highlights?: unknown[];
            event?: TraceEvent;
            error?: TraceErrorRecord;
          };

          const target = data?.target;

          if (target === 'trace' && data.event?.id) {
            pushTraceEvent(data.event);
            return;
          }

          if (target === 'trace_error' && data.error?.id) {
            pushTraceError(data.error);
            return;
          }

          const sender = data?.sender ?? '';
          const text = data?.text ?? '';

          if (target === 'editor' && data?.action === 'file_patch') {
            const patchPath = String(data.path ?? '');
            if (patchPath && !isCorexInternalPath(patchPath)) {
              setEditorPatch({
                path: patchPath,
                content: String(data.content ?? ''),
                highlights: Array.isArray(data.highlights) ? data.highlights : [],
              });
            }
            return;
          }

          if (target === 'thinking_done') {
            inflightTasksRef.current = Math.max(0, inflightTasksRef.current - 1);
            setIsThinking(inflightTasksRef.current > 0);
            if (inflightTasksRef.current === 0) {
              setThoughts([]);
            }
            return;
          }

          if (target === 'thinking') {
            setIsThinking(true);
            setThoughts((prev) => [...prev, text]);
            return;
          }

          if (target === 'chat') {
            if (shouldStopThinking(sender, text)) {
              setIsThinking(false);
              setThoughts([]);
            }

            if (sender.startsWith('System:') || sender === 'CoreX Action') {
              return;
            }

            let content = text;
            if (sender === 'CoreX Status') {
              content = text.replace(/^Task finished! -> /, '');
            }

            if (!content.trim()) {
              return;
            }

            setMessages((prev) => [
              ...prev,
              {
                id: createId('msg'),
                role: 'assistant',
                content,
                timestamp: 'только что',
                ...(typeof data.model === 'string' && data.model.trim() ? { model: data.model.trim() } : {}),
              },
            ]);
          }
        } catch (error) {
          console.error('[ChatContext] Invalid WebSocket message:', error);
        }
      };

      socket.onclose = () => {
        if (disposed) {
          return;
        }
        setConnectionStatus('closed');
        socketRef.current = null;
        if (isThinkingRef.current) {
          inflightTasksRef.current = Math.max(0, inflightTasksRef.current - 1);
          setIsThinking(inflightTasksRef.current > 0);
          setThoughts([]);
          setMessages((prev) => [
            ...prev,
            {
              id: createId('msg'),
              role: 'assistant',
              content:
                'Соединение с CoreX прервано во время выполнения задачи. Перезапустите приложение или нажмите ↻ в чате и отправьте запрос снова.',
              timestamp: 'только что',
            },
          ]);
        }
        if (!manualCloseRef.current) {
          scheduleReconnect();
        }
      };

      socket.onerror = () => {
        if (!disposed) {
          setConnectionStatus('error');
        }
      };
    };

    void connect();

    return () => {
      disposed = true;
      manualCloseRef.current = true;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      socket?.close();
      socketRef.current = null;
    };
  }, [socketKey, scheduleReconnect, pushTraceEvent, pushTraceError]);

  useEffect(() => {
    if (!traceTaskId) {
      return;
    }
    void refreshTraceErrors();
  }, [traceTaskId, refreshTraceErrors]);

  const sendMessage = useCallback(async (text: string, overrides?: { projectRoot?: string }) => {
    const trimmed = text.trim();
    if (!trimmed) {
      return false;
    }

    if (workModeRef.current === 'single' && !selectedPersonaRef.current) {
      setMessages((prev) => [
        ...prev,
        {
          id: createId('msg'),
          role: 'assistant',
          content: 'Выберите скил — нажмите на поле выбора над чатом.',
          timestamp: 'только что',
        },
      ]);
      return false;
    }

    if (workModeRef.current === 'agent' && !selectedAgentRef.current) {
      setMessages((prev) => [
        ...prev,
        {
          id: createId('msg'),
          role: 'assistant',
          content: 'Выберите агента — нажмите на поле выбора над чатом.',
          timestamp: 'только что',
        },
      ]);
      return false;
    }

    if (workModeRef.current === 'pipeline' && !pipelineIdRef.current) {
      setMessages((prev) => [
        ...prev,
        {
          id: createId('msg'),
          role: 'assistant',
          content: 'Выберите команду — нажмите на поле выбора над чатом.',
          timestamp: 'только что',
        },
      ]);
      return false;
    }

    if (!projectRoot?.trim() && !overrides?.projectRoot?.trim()) {
      setMessages((prev) => [
        ...prev,
        {
          id: createId('msg'),
          role: 'assistant',
          content: 'Сначала откройте папку проекта (Файл → Открыть папку).',
          timestamp: 'только что',
        },
      ]);
      return false;
    }

    const userMessage: ChatMessage = {
      id: createId('user'),
      role: 'user',
      content: trimmed,
      timestamp: 'только что',
    };

    const historyPayload = [...messages, userMessage].slice(-20).map((message) => ({
      role: message.role,
      content: message.content,
    }));

    inflightTasksRef.current += 1;
    setMessages((prev) => [...prev, userMessage]);
    setIsThinking(true);
    setThoughts(['Отправка запроса…']);
    const pendingTraceId = `pending-${Date.now()}`;
    setTraceTaskId(pendingTraceId);
    setTraceEvents([
      {
        id: `${pendingTraceId}-send`,
        task_id: pendingTraceId,
        phase: 'ws',
        kind: 'client_send',
        label: 'Запрос отправлен',
        node: 'request',
        status: 'active',
        ts: Date.now(),
        meta: { preview: trimmed.slice(0, 120) },
      },
    ]);

    const syncResult = await syncProjectRoot(overrides?.projectRoot?.trim() || projectRoot);
    if (!syncResult.success) {
      inflightTasksRef.current = Math.max(0, inflightTasksRef.current - 1);
      setIsThinking(inflightTasksRef.current > 0);
      setThoughts([]);
      setMessages((prev) => [
        ...prev,
        {
          id: createId('msg'),
          role: 'assistant',
          content: `Не удалось привязать открытую папку: ${syncResult.error ?? 'ошибка'}`,
          timestamp: 'только что',
        },
      ]);
      return false;
    }

    const activeRoot = syncResult.root ?? overrides?.projectRoot ?? projectRoot;

    if (socketRef.current?.readyState === WebSocket.OPEN) {

      const payload: Record<string, unknown> = {
        task: trimmed,
        project_root: activeRoot,
        history: historyPayload,
      };
      payload.work_mode = workModeRef.current;
      if (workModeRef.current === 'pipeline') {
        payload.pipeline_id = pipelineIdRef.current;
      } else if (workModeRef.current === 'agent' && selectedAgentRef.current) {
        payload.persona_id = selectedAgentRef.current;
      } else if (selectedPersonaRef.current) {
        payload.persona_id = selectedPersonaRef.current;
      }
      payload.coding_language = codingLanguageRef.current;
      payload.coding_engine = codingEngineRef.current;

      socketRef.current.send(JSON.stringify(payload));
      setThoughts((prev) => (prev.length ? [...prev, 'Ожидание ответа CoreX…'] : ['Ожидание ответа CoreX…']));
      return true;
    }

    inflightTasksRef.current = Math.max(0, inflightTasksRef.current - 1);
    setConnectionStatus('closed');
    setIsThinking(inflightTasksRef.current > 0);
    setThoughts([]);
    scheduleReconnect();
    return false;
  }, [projectRoot, messages, scheduleReconnect]);

  const stopGeneration = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ stop: true }));
    }
    inflightTasksRef.current = 0;
    setIsThinking(false);
    setThoughts([]);
  }, []);

  const clearThinking = useCallback(() => {
    setIsThinking(false);
    setThoughts([]);
  }, []);

  const clearEditorPatch = useCallback(() => {
    setEditorPatch(null);
  }, []);

  const value = useMemo(
    () => ({
      messages,
      thoughts,
      isThinking,
      connectionStatus,
      personas,
      selectedPersonaId,
      setSelectedPersonaId,
      addPersona,
      addAgent,
      addPipeline,
      removePersona,
      removeAgent,
      removePipeline,
      refreshSkills,
      agents,
      selectedAgentId,
      setSelectedAgentId,
      workMode,
      setWorkMode,
      pipelines,
      selectedPipelineId,
      setSelectedPipelineId,
      codingLanguage,
      codingLanguages,
      setCodingLanguage,
      codingEngine,
      codingEngines,
      setCodingEngine,
      sendMessage,
      stopGeneration,
      refreshConnection,
      clearThinking,
      editorPatch,
      clearEditorPatch,
      traceEvents,
      traceTaskId,
      traceErrors,
      highlightTraceEventId,
      jumpToTraceEvent,
      refreshTraceErrors,
      clearTrace,
      chatSessions,
      historyLoaded,
      refreshChatSessions,
      openChatSession,
      startNewChat,
      reloadSavedChat,
    }),
    [
      messages,
      thoughts,
      isThinking,
      connectionStatus,
      personas,
      selectedPersonaId,
      setSelectedPersonaId,
      addPersona,
      addAgent,
      addPipeline,
      removePersona,
      removeAgent,
      removePipeline,
      refreshSkills,
      agents,
      selectedAgentId,
      setSelectedAgentId,
      workMode,
      setWorkMode,
      pipelines,
      selectedPipelineId,
      setSelectedPipelineId,
      codingLanguage,
      codingLanguages,
      setCodingLanguage,
      codingEngine,
      codingEngines,
      setCodingEngine,
      sendMessage,
      stopGeneration,
      refreshConnection,
      clearThinking,
      editorPatch,
      clearEditorPatch,
      traceEvents,
      traceTaskId,
      traceErrors,
      highlightTraceEventId,
      jumpToTraceEvent,
      refreshTraceErrors,
      clearTrace,
      chatSessions,
      historyLoaded,
      refreshChatSessions,
      openChatSession,
      startNewChat,
      reloadSavedChat,
    ],
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat() {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within ChatProvider');
  }
  return context;
}
