// Sidebar logic is nearly identical to popup.js, but runs in the persistent side panel
// This is a direct copy of popup.js with only minor changes for sidebar context

const statusText = document.getElementById("statusText");
const linksList = document.getElementById("linksList");
const refreshButton = document.getElementById("refreshButton");
const hideTechnicalToggle = document.getElementById("hideTechnicalToggle");
const autoRefreshLabel = document.getElementById("autoRefreshLabel");
const webAppUrlInput = document.getElementById("webAppUrlInput");
const saveWebAppUrlButton = document.getElementById("saveWebAppUrlButton");

const AUTO_REFRESH_MS = 2000;
const DEFAULT_WEB_APP_URL = "http://localhost:3000";
let isLoading = false;
let autoRefreshTimer = null;

function setStatus(text) {
  statusText.textContent = text;
}

function loadWebAppUrl() {
  chrome.runtime.sendMessage({ type: "getWebAppBaseUrl" }, (response) => {
    const value = response?.url || DEFAULT_WEB_APP_URL;
    if (webAppUrlInput) {
      webAppUrlInput.value = value;
    }
  });
}

function saveWebAppUrl() {
  if (!webAppUrlInput) return;
  const value = webAppUrlInput.value.trim();
  chrome.runtime.sendMessage({ type: "setWebAppBaseUrl", url: value }, (response) => {
    if (response?.ok) {
      webAppUrlInput.value = response.url;
      setStatus("Saved LectureLens web app URL.");
    } else {
      setStatus(response?.error || "Invalid web app URL.");
    }
  });
}

function sendToDesktop(url) {
  setStatus("Sending to desktop app...");
  chrome.runtime.sendMessage({ type: "sendToDesktop", url }, (response) => {
    if (response?.ok) {
      setStatus("Sent to desktop app.");
    } else {
      setStatus(response?.error || "Unable to reach desktop app.");
    }
  });
}

function sendToWeb(url) {
  setStatus("Opening LectureLens web app...");
  chrome.runtime.sendMessage({ type: "openWebApp", url }, (response) => {
    if (response?.ok) {
      setStatus("Opened in LectureLens web app.");
    } else {
      setStatus(response?.error || "Unable to open LectureLens web app.");
    }
  });
}

function clearList() {
  linksList.innerHTML = "";
}

function classifyLink(linkObj) {
  const url = (linkObj.url || "").toLowerCase();
  const source = (linkObj.source || "").toLowerCase();
  const isSegment = /(^|\W)(segment|chunk|frag|fragment)(\W|$)/.test(url) || /\.(m4s|ts)(\?|#|$)/.test(url);
  const isSubtitle = /\.(vtt|srt|ttml)(\?|#|$)/.test(url) || /subtitle|caption/.test(url);
  const isAudioOnly = /(^|\W)audio(\W|$)/.test(url) || /mime=audio/.test(url);
  let kind = "Unknown stream";
  let score = 40;
  let isTechnical = false;
  if (/\.(mp4|webm|mov|mkv)(\?|#|$)/.test(url)) {
    kind = "Direct file";
    score = 96;
  } else if (/\.m3u8(\?|#|$)/.test(url)) {
    kind = "HLS playlist";
    score = 88;
    if (/master|manifest|playlist|index/.test(url)) {
      score = 93;
    }
  } else if (/\.mpd(\?|#|$)/.test(url)) {
    kind = "DASH manifest";
    score = 90;
  } else if (isSegment) {
    kind = "Segment/chunk";
    score = 18;
    isTechnical = true;
  }
  if (isSubtitle) {
    kind = "Subtitle";
    score = 8;
    isTechnical = true;
  }
  if (isAudioOnly) {
    kind = "Audio stream";
    score = Math.min(score, 34);
    isTechnical = true;
  }
  if (/token=|expires=|signature=|sig=/.test(url)) {
    score -= 3;
  }
  if (source.includes("dom")) {
    score += 2;
  }
  if (source.includes("network:media")) {
    score += 3;
  }
  if (isSegment) {
    isTechnical = true;
  }
  return {
    ...linkObj,
    kind,
    score: Math.max(1, Math.min(99, score)),
    isTechnical
  };
}

function createBadge(text, className) {
  const badge = document.createElement("span");
  badge.className = `badge ${className}`;
  badge.textContent = text;
  return badge;
}

function createLinkItem(linkObj, index) {
  const item = document.createElement("li");
  item.className = "link-item";
  const top = document.createElement("div");
  top.className = "link-top";
  const badges = document.createElement("div");
  badges.className = "badges";
  badges.appendChild(createBadge(linkObj.kind, "badge-kind"));
  if (index === 0 && linkObj.score >= 70) {
    badges.appendChild(createBadge("Likely main", "badge-main"));
  }
  const score = document.createElement("span");
  score.className = "score";
  score.textContent = `Score ${linkObj.score}/99`;
  top.append(badges, score);
  const urlText = document.createElement("div");
  urlText.className = "link-url";
  urlText.textContent = linkObj.url;
  const meta = document.createElement("div");
  meta.className = "link-meta";
  const source = document.createElement("span");
  source.className = "source";
  source.textContent = linkObj.source || "unknown";
  const copyButton = document.createElement("button");
  copyButton.className = "copy-btn";
  copyButton.type = "button";
  copyButton.textContent = "Copy";
  copyButton.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(linkObj.url);
      copyButton.textContent = "Copied";
      setTimeout(() => {
        copyButton.textContent = "Copy";
      }, 1000);
    } catch (_err) {
      copyButton.textContent = "Failed";
      setTimeout(() => {
        copyButton.textContent = "Copy";
      }, 1200);
    }
  });
  meta.append(source, copyButton);
  const actions = document.createElement("div");
  actions.className = "link-actions";
  const sendWebButton = document.createElement("button");
  sendWebButton.className = "send-btn";
  sendWebButton.type = "button";
  sendWebButton.textContent = "Send to Web";
  sendWebButton.addEventListener("click", () => sendToWeb(linkObj.url));
  const sendDesktopButton = document.createElement("button");
  sendDesktopButton.className = "send-btn secondary";
  sendDesktopButton.type = "button";
  sendDesktopButton.textContent = "Send to Desktop";
  sendDesktopButton.addEventListener("click", () => sendToDesktop(linkObj.url));
  actions.append(sendWebButton, sendDesktopButton);
  item.append(top, urlText, meta, actions);
  return item;
}

function mergeLinks(networkLinks, domLinks) {
  const merged = new Map();
  networkLinks.forEach((link) => {
    if (link?.url) {
      merged.set(link.url, link);
    }
  });
  domLinks.forEach((url) => {
    if (typeof url !== "string" || !url.trim()) {
      return;
    }
    if (merged.has(url)) {
      const existing = merged.get(url);
      existing.source = existing.source.includes("dom")
        ? existing.source
        : `${existing.source}, dom`;
      merged.set(url, existing);
      return;
    }
    merged.set(url, {
      url,
      source: "dom",
      firstSeenAt: Date.now(),
      lastSeenAt: Date.now()
    });
  });
  return Array.from(merged.values());
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0] || null;
}

async function collectFromPage(tabId) {
  try {
    const response = await chrome.tabs.sendMessage(tabId, { type: "collectDomLinks" });
    const links = Array.isArray(response?.links) ? response.links : [];
    await chrome.runtime.sendMessage({ type: "addDomLinks", links });
    return links;
  } catch (_err) {
    return [];
  }
}

async function loadLinks() {
  if (isLoading) {
    return;
  }
  isLoading = true;
  clearList();
  setStatus("Scanning for video links...");
  try {
    const tab = await getActiveTab();
    if (!tab?.id) {
      setStatus("No active tab found.");
      return;
    }
    const domLinks = await collectFromPage(tab.id);
    const response = await chrome.runtime.sendMessage({ type: "getTabLinks", tabId: tab.id });
    const networkLinks = Array.isArray(response?.links) ? response.links : [];
    const analyzedLinks = mergeLinks(networkLinks, domLinks)
      .map(classifyLink)
      .sort((a, b) => {
        if (b.score !== a.score) {
          return b.score - a.score;
        }
        return (b.lastSeenAt || 0) - (a.lastSeenAt || 0);
      });
    if (!analyzedLinks.length) {
      setStatus("No video links detected yet. Start the video and keep sidebar open.");
      return;
    }
    const hideTechnical = Boolean(hideTechnicalToggle?.checked);
    const visibleLinks = hideTechnical
      ? analyzedLinks.filter((link) => !link.isTechnical)
      : analyzedLinks;
    if (!visibleLinks.length) {
      setStatus(`Found ${analyzedLinks.length} link(s), but all are technical. Disable filter to view all.`);
      return;
    }
    setStatus(`Showing ${visibleLinks.length} of ${analyzedLinks.length} link(s). Top result is most likely video.`);
    visibleLinks.forEach((link, index) => {
      linksList.appendChild(createLinkItem(link, index));
    });
  } finally {
    isLoading = false;
  }
}

refreshButton.addEventListener("click", () => {
  loadLinks();
});
hideTechnicalToggle?.addEventListener("change", () => {
  loadLinks();
});
saveWebAppUrlButton?.addEventListener("click", () => {
  saveWebAppUrl();
});
function startAutoRefresh() {
  autoRefreshTimer = window.setInterval(() => {
    loadLinks();
  }, AUTO_REFRESH_MS);
  autoRefreshLabel.textContent = `Auto-refresh: On (${AUTO_REFRESH_MS / 1000}s)`;
}
window.addEventListener("unload", () => {
  if (autoRefreshTimer !== null) {
    window.clearInterval(autoRefreshTimer);
  }
});
loadLinks();
startAutoRefresh();
loadWebAppUrl();
