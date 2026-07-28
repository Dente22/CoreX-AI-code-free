import { Sparkles, Plus, Copy, Check, User, Bot, X, RefreshCw, ChevronDown, ChevronUp, Settings2, History, MessageSquare } from 'lucide-react';
import { useMemo, useState, useRef, useEffect } from 'react';
import { ThinkingMessage } from './ThinkingModal';
import { ChatInput } from './ChatInput';
import { AddPersonaModal } from './AddPersonaModal';
import { AddAgentModal } from './AddAgentModal';
import { AddPipelineModal } from './AddPipelineModal';
import { SelectionPickerModal } from './SelectionPickerModal';
import { SelectionBar } from './SelectionBar';
import { WorkModeSelector } from './WorkModeSelector';
import { AIModelSelector } from './AIModelSelector';
import { AIControlSection } from './AIControlSection';
import { useChat } from '../contexts/ChatContext';
import { ErrorActionText } from './ErrorActionText';
import {
  agentItemsFromAgents,
  buildAgentFilters,
  buildSkillFilters,
  buildTeamFilters,
  skillItemsFromPersonas,
  teamItemsFromPipelines,
} from '../utils/pickerHelpers';
import { formatSessionDate } from '../utils/chatHistory';
import type { WorkMode } from '../utils/pipelines';

const MODE_LABELS: Record<WorkMode, string> = {
  single: 'Скил',
  agent: 'Агент',
  pipeline: 'Команда',
};

interface AIChatPanelProps {
  onSend: (message: string) => void;
  onCreateProject?: () => void;
  onRefresh: () => void;
  onStop?: () => void;
  onClosePanel: () => void;
  projectRoot?: string;
  onOpenFile?: (path: string, name: string) => void;
  onNotification?: (text: string) => void;
  onFileChanged?: (path: string, message: string) => void;
}

const CONTROLS_OPEN_KEY = 'corex-ai-controls-open';

function readControlsOpen(): boolean {
  try {
    return sessionStorage.getItem(CONTROLS_OPEN_KEY) === '1';
  } catch {
    return false;
  }
}

function storeControlsOpen(open: boolean) {
  try {
    sessionStorage.setItem(CONTROLS_OPEN_KEY, open ? '1' : '0');
  } catch {
    // ignore
  }
}

export function AIChatPanel({
  onSend,
  onCreateProject,
  onRefresh,
  onStop,
  onClosePanel,
  projectRoot = '',
  onOpenFile,
  onNotification,
  onFileChanged,
}: AIChatPanelProps) {
  const {
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
    agents,
    selectedAgentId,
    setSelectedAgentId,
    workMode,
    setWorkMode,
    pipelines,
    selectedPipelineId,
    setSelectedPipelineId,
    chatSessions,
    openChatSession,
    startNewChat,
    reloadSavedChat,
  } = useChat();
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState<'skill' | 'agent' | 'team' | null>(null);
  const [showAddPersona, setShowAddPersona] = useState(false);
  const [showAddAgent, setShowAddAgent] = useState(false);
  const [showAddPipeline, setShowAddPipeline] = useState(false);
  const [addPersonaError, setAddPersonaError] = useState('');
  const [addAgentError, setAddAgentError] = useState('');
  const [addPipelineError, setAddPipelineError] = useState('');
  const [isAddingPersona, setIsAddingPersona] = useState(false);
  const [isAddingAgent, setIsAddingAgent] = useState(false);
  const [isAddingPipeline, setIsAddingPipeline] = useState(false);
  const [controlsOpen, setControlsOpen] = useState(readControlsOpen);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const safeMessages = messages ?? [];
  const safeChatSessions = chatSessions ?? [];
  const safeThoughts = thoughts ?? [];

  const selectedSkill = personas.find((p) => p.id === selectedPersonaId);
  const selectedAgent = agents.find((a) => a.id === selectedAgentId);
  const selectedTeam = pipelines.find((p) => p.id === selectedPipelineId);

  const activeSelectionName =
    workMode === 'single'
      ? selectedSkill?.name
      : workMode === 'agent'
        ? selectedAgent?.name
        : selectedTeam?.name;

  const skillPickerItems = useMemo(() => skillItemsFromPersonas(personas), [personas]);
  const skillPickerFilters = useMemo(() => buildSkillFilters(personas), [personas]);
  const agentPickerItems = useMemo(() => agentItemsFromAgents(agents), [agents]);
  const agentPickerFilters = useMemo(() => buildAgentFilters(agents), [agents]);
  const teamPickerItems = useMemo(() => teamItemsFromPipelines(pipelines), [pipelines]);
  const teamPickerFilters = useMemo(() => buildTeamFilters(pipelines), [pipelines]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [safeMessages, safeThoughts]);

  const statusLabel =
    connectionStatus === 'open'
      ? 'Online'
      : connectionStatus === 'connecting'
        ? '…'
        : connectionStatus === 'error'
          ? 'Error'
          : 'Offline';

  const statusDotClass =
    connectionStatus === 'open'
      ? 'bg-[var(--corex-spark)] corex-pulse-spark'
      : connectionStatus === 'connecting'
        ? 'bg-[var(--corex-brand)]'
        : connectionStatus === 'error'
          ? 'bg-red-500'
          : 'bg-[var(--corex-text-dim)]';

  const controlsSummary = [
    MODE_LABELS[workMode],
    activeSelectionName || 'не выбрано',
  ].join(' · ');

  const handleAddPersona = async (name: string, prompt: string, category: string) => {
    setIsAddingPersona(true);
    setAddPersonaError('');
    try {
      await addPersona(name, prompt, category);
      setShowAddPersona(false);
    } catch (error) {
      setAddPersonaError(error instanceof Error ? error.message : 'Ошибка сохранения');
    } finally {
      setIsAddingPersona(false);
    }
  };

  const handleAddAgent = async (name: string, prompt: string, categoryRu: string) => {
    setIsAddingAgent(true);
    setAddAgentError('');
    try {
      await addAgent(name, prompt, categoryRu);
      setShowAddAgent(false);
    } catch (error) {
      setAddAgentError(error instanceof Error ? error.message : 'Ошибка сохранения');
    } finally {
      setIsAddingAgent(false);
    }
  };

  const handleAddPipeline = async (
    name: string,
    description: string,
    steps: Parameters<typeof addPipeline>[2],
  ) => {
    setIsAddingPipeline(true);
    setAddPipelineError('');
    try {
      await addPipeline(name, description, steps);
      setShowAddPipeline(false);
    } catch (error) {
      setAddPipelineError(error instanceof Error ? error.message : 'Ошибка сохранения');
    } finally {
      setIsAddingPipeline(false);
    }
  };

  const handleCopy = (content: string, id: string) => {
    try {
      navigator.clipboard.writeText(content ?? '');
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // Ignore clipboard errors
    }
  };

  const orchestrationLabel =
    workMode === 'single' ? 'Активный скил' : workMode === 'agent' ? 'Активный агент' : 'Активная команда';

  return (
    <div className="h-full flex flex-col min-h-0 bg-[var(--corex-panel)] border-l border-[var(--corex-border)]">
      {/* Header */}
      <div className="corex-panel-header">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-6 h-6 rounded-lg bg-[var(--corex-gradient-spark)] flex items-center justify-center flex-shrink-0">
            <Sparkles className="w-3.5 h-3.5 text-[#041018]" />
          </div>
          <span className="text-sm font-semibold text-[var(--corex-text)] truncate">Neural Link</span>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <button
            onClick={() => setHistoryOpen((v) => !v)}
            className={`corex-icon-btn ${historyOpen ? 'text-[var(--corex-spark)]' : ''}`}
            title="История чатов"
          >
            <History className="w-3.5 h-3.5" />
          </button>
          <div className={`w-1.5 h-1.5 rounded-full ${statusDotClass}`} />
          <span className="text-[10px] text-[var(--corex-text-dim)] w-10">{statusLabel}</span>
          <button onClick={onRefresh} className="corex-icon-btn" title="Переподключить">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          {onCreateProject ? (
            <button onClick={onCreateProject} className="corex-icon-btn" title="Создать проект">
              <Plus className="w-3.5 h-3.5" />
            </button>
          ) : null}
          <button onClick={onClosePanel} className="corex-icon-btn" title="Скрыть">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {historyOpen ? (
        <div className="border-b border-[var(--corex-border)] bg-[var(--corex-surface)] px-3 py-2 max-h-48 overflow-y-auto">
          <div className="flex items-center justify-between gap-2 mb-2">
            <span className="text-[10px] uppercase tracking-wider text-[var(--corex-text-dim)]">История</span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => void reloadSavedChat()}
                className="text-[10px] px-2 py-0.5 rounded corex-btn-ghost"
                title="Обновить текущий чат"
              >
                Обновить
              </button>
              <button
                type="button"
                onClick={() => void startNewChat()}
                className="text-[10px] px-2 py-0.5 rounded corex-btn-primary"
                title="Сохранить текущий и начать новый"
              >
                Новый чат
              </button>
            </div>
          </div>

          <button
            type="button"
            onClick={() => {
              void reloadSavedChat();
              setHistoryOpen(false);
            }}
            className="w-full text-left rounded-lg px-2 py-1.5 mb-1 bg-[rgba(0,210,255,0.08)] border border-[var(--corex-spark)]/20 hover:bg-[rgba(0,210,255,0.12)] transition-colors"
          >
            <div className="flex items-center gap-2">
              <MessageSquare className="w-3.5 h-3.5 text-[var(--corex-spark)] flex-shrink-0" />
              <div className="min-w-0">
                <div className="text-[11px] text-[var(--corex-text)] truncate">Текущий чат</div>
                <div className="text-[9px] text-[var(--corex-text-dim)]">{safeMessages.length} сообщений</div>
              </div>
            </div>
          </button>

          {safeChatSessions.length === 0 ? (
            <p className="text-[10px] text-[var(--corex-text-dim)] px-1 py-1">
              Архив пуст. «Новый чат» сохранит текущий диалог сюда.
            </p>
          ) : (
            safeChatSessions.map((session) => (
              <button
                key={session.id}
                type="button"
                onClick={() => {
                  void openChatSession(session.id);
                  setHistoryOpen(false);
                }}
                className="w-full text-left rounded-lg px-2 py-1.5 mb-1 hover:bg-[var(--corex-surface-hover)] transition-colors"
              >
                <div className="text-[11px] text-[var(--corex-text)] truncate">{session.title}</div>
                <div className="text-[9px] text-[var(--corex-text-dim)] font-mono">
                  {formatSessionDate(session.created_at)} · {session.message_count} сообщ.
                </div>
              </button>
            ))
          )}
        </div>
      ) : null}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto min-h-0 px-3 py-3 space-y-4">
        {safeMessages.length === 0 && !isThinking ? (
          <div className="flex flex-col items-center justify-center h-full min-h-[120px] text-center px-4">
            <div className="w-10 h-10 rounded-xl bg-[rgba(0,210,255,0.08)] border border-[var(--corex-border)] flex items-center justify-center mb-3">
              <Bot className="w-5 h-5 text-[var(--corex-spark)]" />
            </div>
            <p className="text-sm text-[var(--corex-text-muted)]">Начните диалог с AI</p>
            <p className="text-[10px] text-[var(--corex-text-dim)] mt-1">
              Настройте модель и режим ниже
            </p>
          </div>
        ) : null}

        {safeMessages.map((message) => {
          const role = message?.role ?? 'assistant';
          const content = message?.content ?? '';
          const id = message?.id ?? `msg-${Math.random()}`;
          const isUser = role === 'user';

          return (
            <div key={id} className={`flex gap-2.5 ${isUser ? 'flex-row-reverse' : ''}`}>
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${
                isUser ? 'corex-avatar-user' : 'corex-avatar-ai'
              }`}>
                {isUser ? <User className="w-3.5 h-3.5 text-white" /> : <Bot className="w-3.5 h-3.5" />}
              </div>
              <div className={`flex-1 min-w-0 ${isUser ? 'flex flex-col items-end' : ''}`}>
                <div className={`text-sm whitespace-pre-wrap break-words ${
                  isUser ? 'corex-chat-bubble-user' : 'corex-chat-bubble-ai'
                }`}>
                  {role === 'assistant' ? (
                    <ErrorActionText
                      text={content}
                      onFixWithAI={onSend}
                      onOpenFile={onOpenFile}
                      onRemediated={(path, msg) => {
                        onNotification?.(msg);
                        onFileChanged?.(path, msg);
                      }}
                    />
                  ) : (
                    content
                  )}
                </div>
                {role === 'assistant' && content ? (
                  <button
                    onClick={() => handleCopy(content, id)}
                    className="flex items-center gap-1 mt-1 px-1.5 py-0.5 text-[10px] text-[var(--corex-text-dim)] hover:text-[var(--corex-text)] rounded transition-colors"
                  >
                    {copiedId === id ? <><Check className="w-3 h-3" />Скопировано</> : <><Copy className="w-3 h-3" />Копировать</>}
                  </button>
                ) : null}
              </div>
            </div>
          );
        })}

        {(isThinking || safeThoughts.length > 0) && (
          <ThinkingMessage thoughts={safeThoughts} isThinking={isThinking} />
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Footer: controls + input */}
      <div className="flex-shrink-0 border-t border-[var(--corex-border)] bg-[var(--corex-surface)]">
        <button
          type="button"
          onClick={() => {
            setControlsOpen((v) => {
              const next = !v;
              storeControlsOpen(next);
              return next;
            });
          }}
          className="corex-controls-collapse w-full"
          aria-expanded={controlsOpen}
        >
          <Settings2 className="w-3.5 h-3.5 text-[var(--corex-text-dim)] flex-shrink-0" />
          {controlsOpen ? (
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--corex-text-dim)]">
              Настройки AI
            </span>
          ) : (
            <span className="corex-controls-summary">{controlsSummary}</span>
          )}
          {controlsOpen ? (
            <ChevronDown className="w-3.5 h-3.5 text-[var(--corex-text-dim)] flex-shrink-0" />
          ) : (
            <ChevronUp className="w-3.5 h-3.5 text-[var(--corex-text-dim)] flex-shrink-0" />
          )}
        </button>

        {controlsOpen ? (
          <div className="px-3 pb-2 space-y-2 max-h-[42vh] overflow-y-auto">
            <AIModelSelector disabled={isThinking} onNotification={onNotification} />

            <AIControlSection title="Оркестрация" hint="скил · агент · команда">
              <WorkModeSelector
                workMode={workMode}
                onWorkModeChange={setWorkMode}
                disabled={isThinking}
              />

              {workMode === 'single' ? (
                <SelectionBar
                  label={orchestrationLabel}
                  selectedName={selectedSkill?.name}
                  selectedDescription={selectedSkill?.category_ru || selectedSkill?.description}
                  placeholder="Выберите скил..."
                  onOpenPicker={() => setPickerOpen('skill')}
                  onAdd={() => { setAddPersonaError(''); setShowAddPersona(true); }}
                  onDelete={
                    selectedSkill?.source === 'project'
                      ? async () => {
                          if (!window.confirm('Удалить этот скил из проекта?')) return;
                          try { await removePersona(selectedPersonaId); }
                          catch (error) { setAddPersonaError(error instanceof Error ? error.message : 'Ошибка'); }
                        }
                      : undefined
                  }
                  canDelete={selectedSkill?.source === 'project'}
                  addLabel="Свой"
                  disabled={isThinking}
                />
              ) : null}

              {workMode === 'agent' ? (
                <SelectionBar
                  label={orchestrationLabel}
                  selectedName={selectedAgent?.name}
                  selectedDescription={selectedAgent?.description}
                  placeholder="Выберите агента..."
                  onOpenPicker={() => setPickerOpen('agent')}
                  onAdd={() => { setAddAgentError(''); setShowAddAgent(true); }}
                  onDelete={
                    selectedAgent?.source === 'project'
                      ? async () => {
                          if (!window.confirm('Удалить этого агента?')) return;
                          try { await removeAgent(selectedAgentId); }
                          catch (error) { setAddAgentError(error instanceof Error ? error.message : 'Ошибка'); }
                        }
                      : undefined
                  }
                  canDelete={selectedAgent?.source === 'project'}
                  addLabel="Свой"
                  disabled={isThinking}
                />
              ) : null}

              {workMode === 'pipeline' ? (
                <SelectionBar
                  label={orchestrationLabel}
                  selectedName={selectedTeam?.name}
                  selectedDescription={
                    selectedTeam
                      ? `${selectedTeam.steps_count} этапов · ${(selectedTeam.step_labels || []).join(' → ')}`
                      : undefined
                  }
                  placeholder="Выберите команду..."
                  onOpenPicker={() => setPickerOpen('team')}
                  onAdd={() => { setAddPipelineError(''); setShowAddPipeline(true); }}
                  onDelete={
                    selectedTeam?.source === 'project'
                      ? async () => {
                          if (!window.confirm('Удалить эту команду?')) return;
                          try { await removePipeline(selectedPipelineId); }
                          catch (error) { setAddPipelineError(error instanceof Error ? error.message : 'Ошибка'); }
                        }
                      : undefined
                  }
                  canDelete={selectedTeam?.source === 'project'}
                  addLabel="Своя"
                  disabled={isThinking}
                />
              ) : null}
            </AIControlSection>
          </div>
        ) : null}

        <ChatInput
          onSend={onSend}
          isProcessing={isThinking}
          onStop={onStop}
          projectRoot={projectRoot}
          embedded
        />

        <SelectionPickerModal
          open={pickerOpen === 'skill'}
          title="Выбор скила"
          items={skillPickerItems}
          selectedId={selectedPersonaId}
          filters={skillPickerFilters}
          onClose={() => setPickerOpen(null)}
          onSelect={setSelectedPersonaId}
        />
        <SelectionPickerModal
          open={pickerOpen === 'agent'}
          title="Выбор агента"
          items={agentPickerItems}
          selectedId={selectedAgentId}
          filters={agentPickerFilters}
          onClose={() => setPickerOpen(null)}
          onSelect={setSelectedAgentId}
        />
        <SelectionPickerModal
          open={pickerOpen === 'team'}
          title="Выбор команды"
          items={teamPickerItems}
          selectedId={selectedPipelineId}
          filters={teamPickerFilters}
          onClose={() => setPickerOpen(null)}
          onSelect={setSelectedPipelineId}
        />
        <AddPersonaModal
          open={showAddPersona}
          onClose={() => { if (!isAddingPersona) { setShowAddPersona(false); setAddPersonaError(''); } }}
          onSubmit={handleAddPersona}
          isSubmitting={isAddingPersona}
          error={addPersonaError}
        />
        <AddAgentModal
          open={showAddAgent}
          onClose={() => { if (!isAddingAgent) { setShowAddAgent(false); setAddAgentError(''); } }}
          onSubmit={handleAddAgent}
          isSubmitting={isAddingAgent}
          error={addAgentError}
        />
        <AddPipelineModal
          open={showAddPipeline}
          personas={personas}
          onClose={() => { if (!isAddingPipeline) { setShowAddPipeline(false); setAddPipelineError(''); } }}
          onSubmit={handleAddPipeline}
          isSubmitting={isAddingPipeline}
          error={addPipelineError}
        />
      </div>
    </div>
  );
}
