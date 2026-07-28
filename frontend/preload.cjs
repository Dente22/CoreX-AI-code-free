const { contextBridge, ipcRenderer } = require('electron');

const backendPort = process.env.COREX_BACKEND_PORT || '8000';
const backendUrl = process.env.COREX_BACKEND_URL || `http://127.0.0.1:${backendPort}`;

contextBridge.exposeInMainWorld('electronAPI', {
  isElectron: true,
  backendPort,
  backendUrl,
  projectDir: process.env.COREX_PROJECT_DIR || null,
  getBackendInfo: () => ipcRenderer.invoke('get-backend-info'),
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  pickInstallerUpdate: () => ipcRenderer.invoke('pick-installer-update'),
  onFolderSelected: (callback) => {
    const listener = (event, path) => callback(path);
    ipcRenderer.on('folder-selected', listener);
    return () => ipcRenderer.removeListener('folder-selected', listener);
  },
  onMenuAction: (callback) => {
    const listener = (event, action) => callback(action);
    ipcRenderer.on('menu-action', listener);
    return () => ipcRenderer.removeListener('menu-action', listener);
  },
  onUpdateStatus: (callback) => {
    const listener = (event, status) => callback(status);
    ipcRenderer.on('update-status', listener);
    return () => ipcRenderer.removeListener('update-status', listener);
  },
  openFolder: () => ipcRenderer.invoke('open-folder'),
});
