import React from 'react';
import { useViewSettings } from '../contexts/ViewSettingsContext';
import { CoreXLogo } from './CoreXLogo';

interface MenuBarProps {
  onMenuAction: (action: string) => void;
  onFileOpen?: (name: string, content: string) => void;
}

const menuItems = ['Файл', 'Правка', 'Выбор', 'Вид', 'Переход', 'Запуск', 'Терминал', 'Помощь'];

export function MenuBar({ onMenuAction, onFileOpen }: MenuBarProps) {
  const { terminalVisio, setTerminalVisio } = useViewSettings();
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);
  const [openMenu, setOpenMenu] = React.useState<string | null>(null);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const file = files[0];
    const reader = new FileReader();
    reader.onload = () => {
      const text = typeof reader.result === 'string' ? reader.result : '';
      onFileOpen && onFileOpen(file.name, text);
      setOpenMenu(null);
    };
    reader.readAsText(file);
    e.currentTarget.value = '';
  };

  React.useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('[data-menu-trigger]') && !target.closest('[data-menu-dropdown]')) {
        setOpenMenu(null);
      }
    };
    if (openMenu) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [openMenu]);

  const dropdownItem = 'corex-dropdown-item';
  const divider = <div className="my-1 border-t border-[var(--corex-border)]" />;

  return (
    <div className="corex-menubar flex items-center px-3">
      <div className="flex items-center gap-1">
        <div className="flex items-center gap-2 px-2 mr-2">
          <CoreXLogo className="w-5 h-5" />
          <span className="text-sm font-bold corex-brand-text">CoreX</span>
        </div>
        {menuItems.map((item) => (
          <div key={item} className="relative">
            <button
              type="button"
              data-menu-trigger={item}
              onClick={() => {
                if (item === 'Файл' || item === 'Терминал' || item === 'Вид') {
                  setOpenMenu((prev) => (prev === item ? null : item));
                  return;
                }
                onMenuAction(item.toLowerCase());
                setOpenMenu(null);
              }}
              aria-label={`Menu ${item}`}
              title={item}
              className={`px-2.5 py-1 text-sm rounded-md transition-colors ${
                openMenu === item
                  ? 'text-white bg-[var(--corex-surface-hover)]'
                  : 'text-[var(--corex-text-muted)] hover:text-[var(--corex-text)] hover:bg-[var(--corex-surface-hover)]'
              }`}
            >
              {item}
            </button>

            {openMenu === 'Файл' && item === 'Файл' && (
              <div data-menu-dropdown="файл" className="corex-menubar-dropdown corex-dropdown w-56 py-1">
                <button type="button" className={dropdownItem} onClick={() => { onMenuAction('new-file'); setOpenMenu(null); }}>New File</button>
                <button type="button" className={dropdownItem} onClick={() => { onMenuAction('new-folder'); setOpenMenu(null); }}>New Folder</button>
                <button type="button" className={dropdownItem}>New Window</button>
                {divider}
                <button type="button" className={dropdownItem} onClick={() => fileInputRef.current?.click()}>Open File...</button>
                <button type="button" className={dropdownItem} onClick={() => { onMenuAction('open-folder'); setOpenMenu(null); }}>Open Folder...</button>
                <button type="button" className={dropdownItem}>Open Recent</button>
                {divider}
                <button type="button" className={dropdownItem}>Save</button>
                <button type="button" className={dropdownItem}>Save As...</button>
                {divider}
                <button type="button" className={dropdownItem} onClick={() => { onMenuAction('exit'); setOpenMenu(null); }}>Exit</button>
              </div>
            )}

            {openMenu === 'Вид' && item === 'Вид' && (
              <div data-menu-dropdown="вид" className="corex-menubar-dropdown corex-dropdown w-72 py-1">
                <label className="flex items-start gap-3 px-4 py-2.5 text-sm cursor-pointer hover:bg-[var(--corex-surface-hover)]">
                  <input
                    type="checkbox"
                    checked={terminalVisio}
                    onChange={(e) => setTerminalVisio(e.currentTarget.checked)}
                    className="mt-0.5 accent-indigo-500"
                  />
                  <span>
                    <span className="block font-medium text-[var(--corex-text)]">Терминальный Visio</span>
                    <span className="block text-xs text-[var(--corex-text-muted)] mt-0.5">
                      Схемы CoreX: обзор IDE, AI-режим, архитектура
                    </span>
                  </span>
                </label>
                {divider}
                <button type="button" className={dropdownItem} onClick={() => { onMenuAction('open-browser'); setOpenMenu(null); }}>
                  Браузер CoreX
                </button>
              </div>
            )}

            {openMenu === 'Терминал' && item === 'Терминал' && (
              <div data-menu-dropdown="терминал" className="corex-menubar-dropdown corex-dropdown w-56 py-1">
                <button type="button" className={dropdownItem} onClick={() => { onMenuAction('new-terminal'); setOpenMenu(null); }}>
                  New Terminal
                  <span className="float-right text-xs text-[var(--corex-text-dim)]">Ctrl+Shift+`</span>
                </button>
                <button type="button" className={dropdownItem}>
                  Split Terminal
                  <span className="float-right text-xs text-[var(--corex-text-dim)]">Ctrl+Shift+5</span>
                </button>
                {divider}
                <button type="button" className={dropdownItem}>New Terminal Window</button>
                {divider}
                <button type="button" className={dropdownItem}>Run Task...</button>
                <button type="button" className={dropdownItem}>Run Build Task...</button>
                <button type="button" className={dropdownItem}>Run Active File</button>
                <button type="button" className={dropdownItem}>Run Selected Text</button>
              </div>
            )}
          </div>
        ))}
        <input ref={fileInputRef} type="file" className="hidden" aria-label="Open file" onChange={handleFileInput} />
      </div>
    </div>
  );
}
