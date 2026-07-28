import { FolderOpen, Plus, Github, Sparkles, Terminal, Code2, Users, Cpu, Network } from 'lucide-react';
import { CoreXLogo } from './CoreXLogo';

interface WelcomeScreenProps {
  onCreateProject: () => void;
  onOpenProject: () => void;
  onCloneRepo: () => void;
  onCreateAIProject: () => void;
  lastProject?: string;
  onOpenLastProject?: () => void;
}

const pillars = [
  {
    icon: Code2,
    color: 'text-[var(--corex-spark)]',
    bg: 'bg-[rgba(0,210,255,0.1)]',
    title: 'Редактор',
    desc: 'Monaco, табы, подсветка синтаксиса',
  },
  {
    icon: Terminal,
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    title: 'Терминал',
    desc: 'Запуск main.py, npm, команды',
  },
  {
    icon: Network,
    color: 'text-[var(--corex-brand)]',
    bg: 'bg-[rgba(154,94,255,0.12)]',
    title: 'AI-оркестрация',
    desc: 'Скилы → Агенты → Команды',
  },
] as const;

const modes = [
  { icon: Sparkles, label: 'Скил', color: 'var(--corex-mode-skill)' },
  { icon: Cpu, label: 'Агент', color: 'var(--corex-mode-agent)' },
  { icon: Users, label: 'Команда', color: 'var(--corex-spark)' },
] as const;

const actions = [
  { icon: Plus, iconBg: 'bg-[var(--corex-gradient-brand)]', label: 'Новый проект', sub: 'С AI по описанию', fn: 'onCreateProject' as const },
  { icon: FolderOpen, iconBg: 'bg-[var(--corex-gradient-spark)]', label: 'Открыть', sub: 'Существующая папка', fn: 'onOpenProject' as const },
  { icon: Github, iconBg: 'bg-slate-700', label: 'Git clone', sub: 'Любой репозиторий', fn: 'onCloneRepo' as const },
  { icon: Sparkles, iconBg: 'bg-[var(--corex-gradient-neural)]', label: 'AI-проект', sub: 'Описание → код', fn: 'onCreateAIProject' as const },
] as const;

export function WelcomeScreen(props: WelcomeScreenProps) {
  const { lastProject, onOpenLastProject, onOpenProject } = props;
  const lastName = lastProject ? lastProject.split(/[\\/]/).pop() : null;

  const handlers = {
    onCreateProject: props.onCreateProject,
    onOpenProject: props.onOpenProject,
    onCloneRepo: props.onCloneRepo,
    onCreateAIProject: props.onCreateAIProject,
  };

  return (
    <div className="corex-welcome-page flex-1 p-6 sm:p-10">
      <div className="mx-auto max-w-6xl">
        <div className="corex-glass rounded-2xl p-6 sm:p-10">
          {/* Header */}
          <div className="flex flex-wrap items-center gap-3 mb-8">
            <div className="w-11 h-11 rounded-xl overflow-hidden ring-2 ring-[var(--corex-brand)]/40 shadow-lg shadow-[var(--corex-glow-brand)] flex items-center justify-center bg-[var(--corex-surface)]">
              <CoreXLogo className="w-8 h-8" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">CoreX</h1>
              <p className="text-xs text-[var(--corex-text-muted)]">Локальная AI-мастерская для разработки</p>
            </div>
            <div className="ml-auto flex flex-wrap gap-2">
              <span className="corex-tag-local">
                <Cpu className="w-3 h-3" />
                Ollama · локально
              </span>
              <span className="corex-tag-brand">Python + Electron</span>
            </div>
          </div>

          <div className="flex flex-col gap-8 lg:flex-row">
            {/* Left — product story */}
            <div className="flex-1 space-y-6">
              <div>
                <h2 className="text-2xl sm:text-3xl font-bold text-white leading-snug">
                  Код, терминал и AI —
                  <span className="block corex-brand-text">
                    одна мастерская на вашем ПК
                  </span>
                </h2>
                <p className="mt-3 text-[var(--corex-text-muted)] leading-relaxed max-w-lg">
                  CoreX — не облачный чат, а полноценная среда: редактируйте файлы, запускайте код
                  и управляйте AI через скилы, агентов и цепочки команд — всё без отправки данных наружу.
                </p>
              </div>

              {/* Three pillars */}
              <div className="grid gap-3 sm:grid-cols-3">
                {pillars.map(({ icon: Icon, color, bg, title, desc }) => (
                  <div key={title} className="corex-pillar">
                    <div className={`corex-pillar-icon ${bg}`}>
                      <Icon className={`w-5 h-5 ${color}`} />
                    </div>
                    <p className="text-sm font-semibold text-white">{title}</p>
                    <p className="text-xs text-[var(--corex-text-muted)] mt-0.5">{desc}</p>
                  </div>
                ))}
              </div>

              {/* AI modes */}
              <div className="corex-surface rounded-xl p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-[var(--corex-text-dim)] mb-3">
                  Три режима AI
                </p>
                <div className="flex flex-wrap gap-2">
                  {modes.map(({ icon: Icon, label, color }) => (
                    <div
                      key={label}
                      className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[var(--corex-border)] bg-[var(--corex-surface-elevated)]"
                    >
                      <Icon className="w-3.5 h-3.5" style={{ color }} />
                      <span className="text-xs font-medium text-[var(--corex-text)]">{label}</span>
                    </div>
                  ))}
                  <span className="text-xs text-[var(--corex-text-dim)] self-center ml-1">
                    → разработчик · QA · ревьюер
                  </span>
                </div>
              </div>
            </div>

            {/* Right — actions */}
            <div className="w-full max-w-sm space-y-4">
              <div className="corex-surface-elevated rounded-xl p-5">
                <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--corex-spark)]">
                  Быстрый старт
                </p>
                <h3 className="mt-2 text-lg font-bold text-white truncate">
                  {lastName ?? 'Проект не открыт'}
                </h3>
                {lastProject && (
                  <p className="mt-1 text-[10px] font-mono text-[var(--corex-text-dim)] truncate">{lastProject}</p>
                )}
                <div className="mt-4 flex flex-col gap-2">
                  <button onClick={onOpenLastProject} disabled={!lastProject} className="corex-btn-spark w-full py-2.5 text-sm">
                    Продолжить
                  </button>
                  <button onClick={onOpenProject} className="corex-btn-ghost w-full py-2.5 text-sm">
                    Другая папка
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                {actions.map(({ icon: Icon, iconBg, label, sub, fn }) => (
                  <button
                    key={label}
                    onClick={handlers[fn]}
                    className="corex-action-card w-full"
                  >
                    <div className={`corex-action-card-icon ${iconBg} text-white`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-[10px] uppercase tracking-wider text-[var(--corex-text-dim)]">{label}</p>
                      <p className="text-sm font-semibold text-white">{sub}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
