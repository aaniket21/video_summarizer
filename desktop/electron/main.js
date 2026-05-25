const path = require("path");
const { app, BrowserWindow, ipcMain } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const os = require("os");
const WebSocket = require("ws");

let mainWindow = null;
let wsServer = null;
let pythonProcess = null;

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

app.whenReady().then(() => {
  createWindow();
  startPythonEngine();
  startWebSocketBridge();

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
  if (pythonProcess) {
    pythonProcess.kill();
  }
});
