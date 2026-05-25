const path = require("path");
const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const os = require("os");
const WebSocket = require("ws");

let mainWindow = null;
let wsServer = null;
let pythonProcess = null;
let watchFolder = null;
let watchWatcher = null;

const queue = [];

const MODEL_DEFAULTS = [
  { id: "tiny", label: "Whisper Tiny", sizeGb: 0.15 },
  { id: "base", label: "Whisper Base", sizeGb: 0.29 },
  { id: "small", label: "Whisper Small", sizeGb: 0.6 },
  { id: "medium", label: "Whisper Medium", sizeGb: 1.4 },
  { id: "large-v3", label: "Whisper Large v3", sizeGb: 2.9 }
];

function getModelsPath() {
  return path.join(app.getPath("userData"), "models.json");
}

function getWatchConfigPath() {
  return path.join(app.getPath("userData"), "watch.json");
}

function loadModels() {
  const modelPath = getModelsPath();
  if (!fs.existsSync(modelPath)) {
    return MODEL_DEFAULTS.map((m) => ({ ...m, status: "not-downloaded" }));
  }
  try {
    const raw = fs.readFileSync(modelPath, "utf-8");
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed;
    }
  } catch {
    return MODEL_DEFAULTS.map((m) => ({ ...m, status: "not-downloaded" }));
  }
  return MODEL_DEFAULTS.map((m) => ({ ...m, status: "not-downloaded" }));
}

function saveModels(models) {
  fs.writeFileSync(getModelsPath(), JSON.stringify(models, null, 2));
}

function loadWatchFolder() {
  const configPath = getWatchConfigPath();
  if (!fs.existsSync(configPath)) {
    return null;
  }
  try {
    const raw = fs.readFileSync(configPath, "utf-8");
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.path === "string") {
      return parsed.path;
    }
  } catch {
    return null;
  }
  return null;
}

function saveWatchFolder(folderPath) {
  const payload = { path: folderPath };
  fs.writeFileSync(getWatchConfigPath(), JSON.stringify(payload, null, 2));
}

function enqueueJob(job) {
  queue.push(job);
  broadcastQueue();
}

function broadcastQueue() {
  if (!mainWindow) return;
  mainWindow.webContents.send("queue:update", queue);
}

function broadcastBridgeStatus(payload) {
  if (!mainWindow) return;
  mainWindow.webContents.send("bridge:status", payload);
}

function broadcastWatchStatus(payload) {
  if (!mainWindow) return;
  mainWindow.webContents.send("watch:status", payload);
}

async function getHardwareInfo() {
  try {
    const si = require("systeminformation");
    const [cpu, mem, graphics] = await Promise.all([
      si.cpu(),
      si.mem(),
      si.graphics()
    ]);

    return {
      cpu: `${cpu.manufacturer} ${cpu.brand}`,
      cores: cpu.cores,
      memoryGb: Math.round(mem.total / 1024 / 1024 / 1024),
      gpu: (graphics.controllers || []).map((g) => g.model).filter(Boolean)
    };
  } catch {
    return {
      cpu: os.cpus()?.[0]?.model || "Unknown CPU",
      cores: os.cpus()?.length || 0,
      memoryGb: Math.round(os.totalmem() / 1024 / 1024 / 1024),
      gpu: []
    };
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1024,
    minHeight: 700,
    backgroundColor: "#0b0f14",
    webPreferences: {
      preload: path.join(__dirname, "preload.js")
    }
  });

  mainWindow.loadFile(path.join(__dirname, "..", "renderer", "index.html"));
}

function startPythonEngine() {
  const enginePath = path.join(__dirname, "..", "python", "engine.py");
  try {
    pythonProcess = spawn("python", [enginePath], {
      stdio: "pipe"
    });

    pythonProcess.stdout.on("data", (data) => {
      const line = data.toString("utf-8").trim();
      if (line && mainWindow) {
        mainWindow.webContents.send("engine:log", line);
      }
    });

    pythonProcess.stderr.on("data", (data) => {
      const line = data.toString("utf-8").trim();
      if (line && mainWindow) {
        mainWindow.webContents.send("engine:log", line);
      }
    });
  } catch (error) {
    if (mainWindow) {
      mainWindow.webContents.send("engine:log", `Python engine failed: ${error.message}`);
    }
  }
}

function startWebSocketBridge() {
  wsServer = new WebSocket.Server({ port: 27182 });
  broadcastBridgeStatus({ status: "listening", port: 27182 });

  wsServer.on("error", (error) => {
    broadcastBridgeStatus({ status: "error", message: error?.message || "Bridge error" });
  });

  wsServer.on("connection", (socket) => {
    broadcastBridgeStatus({ status: "connected" });
    socket.on("message", (data) => {
      try {
        const payload = JSON.parse(data.toString());
        if (payload?.url) {
          enqueueJob({
            id: `ext-${Date.now()}`,
            url: payload.url,
            source: "extension",
            status: "queued",
            createdAt: Date.now()
          });
          if (mainWindow) {
            mainWindow.webContents.send("bridge:url", payload.url);
          }
        }
      } catch {
        // ignore malformed payloads
      }
    });

    socket.on("close", () => {
      broadcastBridgeStatus({ status: "listening", port: 27182 });
    });
  });
}

function isWatchableFile(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  return [".mp3", ".mp4", ".wav", ".m4a", ".mov", ".mkv"].includes(ext);
}

function stopWatchFolder() {
  if (watchWatcher) {
    watchWatcher.close();
    watchWatcher = null;
  }
}

function startWatchFolder() {
  stopWatchFolder();
  if (!watchFolder) {
    broadcastWatchStatus({ status: "disabled" });
    return;
  }

  try {
    watchWatcher = fs.watch(watchFolder, { persistent: true }, (eventType, filename) => {
      if (!filename) return;
      const fullPath = path.join(watchFolder, filename.toString());
      if (!isWatchableFile(fullPath)) return;
      try {
        const stats = fs.statSync(fullPath);
        if (!stats.isFile()) return;
      } catch {
        return;
      }
      enqueueJob({
        id: `watch-${Date.now()}`,
        url: fullPath,
        source: "watch-folder",
        status: "queued",
        createdAt: Date.now()
      });
    });
    broadcastWatchStatus({ status: "listening", path: watchFolder });
  } catch (error) {
    broadcastWatchStatus({ status: "error", message: error?.message || "Watch failed" });
  }
}

function setWatchFolder(nextPath) {
  watchFolder = nextPath;
  saveWatchFolder(watchFolder);
  startWatchFolder();
  return watchFolder;
}

app.whenReady().then(() => {
  createWindow();
  startPythonEngine();
  startWebSocketBridge();

  watchFolder = loadWatchFolder();
  startWatchFolder();

  ipcMain.handle("hardware:get", async () => getHardwareInfo());
  ipcMain.handle("models:get", () => loadModels());
  ipcMain.handle("models:download", (_event, modelId) => {
    const models = loadModels();
    const updated = models.map((m) =>
      m.id === modelId ? { ...m, status: "downloaded" } : m
    );
    saveModels(updated);
    return updated;
  });
  ipcMain.handle("models:delete", (_event, modelId) => {
    const models = loadModels();
    const updated = models.map((m) =>
      m.id === modelId ? { ...m, status: "not-downloaded" } : m
    );
    saveModels(updated);
    return updated;
  });
  ipcMain.handle("queue:get", () => queue);
  ipcMain.handle("queue:add", (_event, url) => {
    enqueueJob({
      id: `job-${Date.now()}`,
      url,
      source: "manual",
      status: "queued",
      createdAt: Date.now()
    });
    return queue;
  });
  ipcMain.handle("watch:get", () => watchFolder);
  ipcMain.handle("watch:pick", async () => {
    const result = await dialog.showOpenDialog({
      properties: ["openDirectory", "createDirectory"]
    });
    if (result.canceled || !result.filePaths?.length) {
      return watchFolder;
    }
    return setWatchFolder(result.filePaths[0]);
  });
  ipcMain.handle("watch:set", (_event, folderPath) => setWatchFolder(folderPath));
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  if (wsServer) {
    wsServer.close();
  }
  stopWatchFolder();
  if (pythonProcess) {
    pythonProcess.kill();
  }
});
