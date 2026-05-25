const queueList = document.getElementById("queueList");
const queueCount = document.getElementById("queueCount");
const urlInput = document.getElementById("urlInput");
const addJobBtn = document.getElementById("addJobBtn");
const clearInputBtn = document.getElementById("clearInputBtn");
const modelList = document.getElementById("modelList");
const hardwareCard = document.getElementById("hardwareCard");
const engineLogs = document.getElementById("engineLogs");
const bridgeStatus = document.getElementById("bridgeStatus");
const webAppUrl = document.getElementById("webAppUrl");
const saveSettingsBtn = document.getElementById("saveSettingsBtn");
const apiBaseUrl = document.getElementById("apiBaseUrl");
const accessToken = document.getElementById("accessToken");
const refreshHistoryBtn = document.getElementById("refreshHistoryBtn");
const cloudStatus = document.getElementById("cloudStatus");
const cloudHistoryList = document.getElementById("cloudHistoryList");

const navItems = document.querySelectorAll(".nav-item");
const panels = document.querySelectorAll(".panel");

function switchPanel(name) {
  navItems.forEach((item) => item.classList.toggle("is-active", item.dataset.section === name));
  panels.forEach((panel) => {
    panel.hidden = panel.dataset.panel !== name;
  });
}

navItems.forEach((item) => {
  item.addEventListener("click", () => switchPanel(item.dataset.section));
});

function renderQueue(items) {
  queueList.innerHTML = "";
  queueCount.textContent = `${items.length} jobs`;

  if (!items.length) {
    queueList.innerHTML = '<div class="muted">No jobs yet.</div>';
    return;
  }

  items.forEach((job) => {
    const row = document.createElement("div");
    row.className = "queue-item";
    row.innerHTML = `
      <div>
        <div>${job.url}</div>
        <span>${job.source} · ${new Date(job.createdAt).toLocaleTimeString()}</span>
      </div>
      <strong>${job.status}</strong>
    `;
    queueList.appendChild(row);
  });
}

function renderModels(models) {
  modelList.innerHTML = "";
  models.forEach((model) => {
    const card = document.createElement("div");
    card.className = "model-card";
    card.innerHTML = `
      <div><strong>${model.label}</strong> · ${model.sizeGb} GB</div>
      <div>Status: ${model.status}</div>
      <div class="actions">
        <button data-action="download" data-id="${model.id}">Download</button>
        <button data-action="delete" data-id="${model.id}">Remove</button>
      </div>
    `;
    modelList.appendChild(card);
  });

  modelList.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const action = btn.dataset.action;
      const id = btn.dataset.id;
      if (action === "download") {
        const updated = await window.api.downloadModel(id);
        renderModels(updated);
      }
      if (action === "delete") {
        const updated = await window.api.deleteModel(id);
        renderModels(updated);
      }
    });
  });
}

function renderHardware(info) {
  hardwareCard.innerHTML = `
    <div><strong>CPU</strong> ${info.cpu}</div>
    <div><strong>Cores</strong> ${info.cores}</div>
    <div><strong>Memory</strong> ${info.memoryGb} GB</div>
    <div><strong>GPU</strong> ${info.gpu.length ? info.gpu.join(", ") : "Not detected"}</div>
  `;
}

function renderBridgeStatus(payload) {
  if (!bridgeStatus || !payload) return;
  if (payload.status === "connected") {
    bridgeStatus.textContent = "Bridge: Connected";
    return;
  }
  if (payload.status === "error") {
    bridgeStatus.textContent = "Bridge: Error";
    return;
  }
  bridgeStatus.textContent = "Bridge: Listening";
}

function renderCloudHistory(items) {
  if (!cloudHistoryList) return;
  cloudHistoryList.innerHTML = "";

  if (!items.length) {
    cloudHistoryList.innerHTML = '<div class="muted">No cloud jobs yet.</div>';
    return;
  }

  items.forEach((job) => {
    const row = document.createElement("div");
    row.className = "queue-item";
    row.innerHTML = `
      <div>
        <div>${job.video_url || "(no url)"}</div>
        <span>${job.status} · ${new Date(job.created_at).toLocaleString()}</span>
      </div>
      <strong>${job.progress ?? 0}%</strong>
    `;
    cloudHistoryList.appendChild(row);
  });
}

function setCloudStatus(text) {
  if (cloudStatus) {
    cloudStatus.textContent = text;
  }
}

async function refreshCloudHistory() {
  const baseUrl = apiBaseUrl?.value?.trim() || "";
  const token = accessToken?.value?.trim() || "";

  if (!baseUrl || !token) {
    setCloudStatus("Add API URL + token to sync.");
    renderCloudHistory([]);
    return;
  }

  const jobsUrl = window.CloudSync?.buildJobsUrl(baseUrl, 1, 20) || "";
  if (!jobsUrl) {
    setCloudStatus("Invalid API base URL.");
    renderCloudHistory([]);
    return;
  }

  setCloudStatus("Syncing...");
  try {
    const res = await fetch(jobsUrl, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    if (!res.ok) {
      const err = await res.json().catch(() => null);
      setCloudStatus(err?.error || `Sync failed (${res.status})`);
      renderCloudHistory([]);
      return;
    }

    const payload = await res.json();
    const items = Array.isArray(payload?.items) ? payload.items : [];
    setCloudStatus(`Loaded ${items.length} job(s)`);
    renderCloudHistory(items);
  } catch (error) {
    setCloudStatus(error?.message || "Sync failed");
    renderCloudHistory([]);
  }
}

async function init() {
  const hardware = await window.api.getHardware();
  renderHardware(hardware);

  const models = await window.api.getModels();
  renderModels(models);

  const queue = await window.api.getQueue();
  renderQueue(queue);

  const savedWebUrl = localStorage.getItem("lecturelens_web_url") || "http://localhost:3000";
  webAppUrl.value = savedWebUrl;

  const savedApiUrl = localStorage.getItem("lecturelens_api_url") || "http://localhost:8000";
  const savedToken = localStorage.getItem("lecturelens_access_token") || "";
  if (apiBaseUrl) apiBaseUrl.value = savedApiUrl;
  if (accessToken) accessToken.value = savedToken;

  refreshCloudHistory();
}

addJobBtn.addEventListener("click", async () => {
  const raw = urlInput.value;
  const urls = window.BatchUrls?.parseBatchUrls(raw) || [];
  if (!urls.length) return;

  let nextQueue = null;
  for (const url of urls) {
    // eslint-disable-next-line no-await-in-loop
    nextQueue = await window.api.enqueue(url);
  }
  if (nextQueue) renderQueue(nextQueue);
  urlInput.value = "";
});

clearInputBtn.addEventListener("click", () => {
  urlInput.value = "";
});

window.api.onQueueUpdate(renderQueue);
window.api.onIncomingUrl((url) => {
  if (urlInput) {
    urlInput.value = url;
  }
});

window.api.onBridgeStatus((payload) => {
  renderBridgeStatus(payload);
});

window.api.onEngineLog((line) => {
  engineLogs.textContent = `${engineLogs.textContent}\n${line}`.trim();
});

saveSettingsBtn.addEventListener("click", () => {
  const value = webAppUrl.value.trim();
  if (value) {
    localStorage.setItem("lecturelens_web_url", value);
  }

  const apiValue = apiBaseUrl?.value?.trim();
  const tokenValue = accessToken?.value?.trim();
  if (apiValue) {
    localStorage.setItem("lecturelens_api_url", apiValue);
  }
  if (tokenValue !== undefined) {
    localStorage.setItem("lecturelens_access_token", tokenValue);
  }

  refreshCloudHistory();
});

refreshHistoryBtn?.addEventListener("click", () => {
  refreshCloudHistory();
});

init();
