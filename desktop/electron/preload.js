const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("api", {
  getHardware: () => ipcRenderer.invoke("hardware:get"),
  getModels: () => ipcRenderer.invoke("models:get"),
  downloadModel: (id) => ipcRenderer.invoke("models:download", id),
  deleteModel: (id) => ipcRenderer.invoke("models:delete", id),
  getQueue: () => ipcRenderer.invoke("queue:get"),
  enqueue: (url) => ipcRenderer.invoke("queue:add", url),
  onQueueUpdate: (handler) => ipcRenderer.on("queue:update", (_event, payload) => handler(payload)),
  onIncomingUrl: (handler) => ipcRenderer.on("bridge:url", (_event, url) => handler(url)),
  onBridgeStatus: (handler) => ipcRenderer.on("bridge:status", (_event, payload) => handler(payload)),
  onEngineLog: (handler) => ipcRenderer.on("engine:log", (_event, line) => handler(line))
});
