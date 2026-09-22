const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('splashAPI', {
  onUpdate: (callback) => {
    if (typeof callback !== 'function') return () => {};
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on('splash-update', listener);
    return () => ipcRenderer.removeListener('splash-update', listener);
  },
  choose: (action) => {
    ipcRenderer.send('splash-choice', action);
  },
});
