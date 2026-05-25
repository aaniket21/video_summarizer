importScripts("bridge.js");

const DEFAULT_WEB_APP_URL = "http://localhost:3000";
const tabMediaLinks = new Map();

function configureSidePanelBehavior() {
  if (!chrome.sidePanel?.setPanelBehavior) {
    return;
  }

  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
}

configureSidePanelBehavior();
chrome.runtime.onInstalled.addListener(() => {
  configureSidePanelBehavior();
});

const MEDIA_EXT_PATTERN = /\.(m3u8|mp4|webm|m4s|mpd|mov|avi|mkv)(\?|#|$)/i;
const MEDIA_KEYWORDS = [
  "m3u8",
  "mp4",
  "manifest",
  "playlist",
  "dash",
  "hls",
  "videoplayback"
];

function getStoreForTab(tabId) {
  if (!tabMediaLinks.has(tabId)) {
    tabMediaLinks.set(tabId, new Map());
  }
  return tabMediaLinks.get(tabId);
}

function looksLikeMediaUrl(url) {
  if (!url || typeof url !== "string") {
    return false;
  }

  if (MEDIA_EXT_PATTERN.test(url)) {
    return true;
  }

  const lowerUrl = url.toLowerCase();
  return MEDIA_KEYWORDS.some((keyword) => lowerUrl.includes(keyword));
}

function addLink(tabId, url, source) {
  if (typeof tabId !== "number" || tabId < 0 || !looksLikeMediaUrl(url)) {
    return;
  }

  const tabStore = getStoreForTab(tabId);
  const existing = tabStore.get(url);

  if (existing) {
    existing.source = existing.source.includes(source)
      ? existing.source
      : `${existing.source}, ${source}`;
    existing.lastSeenAt = Date.now();
    return;
  }

  tabStore.set(url, {
    url,
    source,
    firstSeenAt: Date.now(),
    lastSeenAt: Date.now()
  });
}

function getLinksForTab(tabId) {
  const tabStore = tabMediaLinks.get(tabId);
  if (!tabStore) {
    return [];
  }

  return Array.from(tabStore.values()).sort((a, b) => b.lastSeenAt - a.lastSeenAt);
}

chrome.webRequest.onBeforeRequest.addListener(
  (details) => {
    addLink(details.tabId, details.url, `network:${details.type}`);
  },
  {
    urls: ["<all_urls>"],
    types: ["media", "xmlhttprequest", "other"]
  }
);

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status === "loading") {
    tabMediaLinks.set(tabId, new Map());
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  tabMediaLinks.delete(tabId);
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message !== "object") {
    return;
  }

  if (message.type === "getWebAppBaseUrl") {
    chrome.storage.local.get({ webAppBaseUrl: DEFAULT_WEB_APP_URL }, (result) => {
      sendResponse({ ok: true, url: result.webAppBaseUrl || DEFAULT_WEB_APP_URL });
    });
    return true;
  }

  if (message.type === "setWebAppBaseUrl") {
    const raw = String(message.url || "");
    const sanitized = globalThis.LectureLensBridge?.sanitizeBaseUrl(raw) || "";
    if (!sanitized) {
      sendResponse({ ok: false, error: "Invalid URL" });
      return;
    }
    chrome.storage.local.set({ webAppBaseUrl: sanitized }, () => {
      sendResponse({ ok: true, url: sanitized });
    });
    return true;
  }

  if (message.type === "openWebApp") {
    const videoUrl = String(message.url || "");
    chrome.storage.local.get({ webAppBaseUrl: DEFAULT_WEB_APP_URL }, (result) => {
      const baseUrl = result.webAppBaseUrl || DEFAULT_WEB_APP_URL;
      const targetUrl = globalThis.LectureLensBridge?.buildWebAppJobUrl(baseUrl, videoUrl) || "";
      if (!targetUrl) {
        sendResponse({ ok: false, error: "Invalid web app URL" });
        return;
      }

      let origin = "";
      try {
        origin = new URL(targetUrl).origin;
      } catch {
        sendResponse({ ok: false, error: "Invalid web app URL" });
        return;
      }

      chrome.tabs.query({ url: `${origin}/*` }, (tabs) => {
        if (tabs && tabs.length > 0 && tabs[0].id !== undefined) {
          chrome.tabs.update(tabs[0].id, { url: targetUrl, active: true });
        } else {
          chrome.tabs.create({ url: targetUrl, active: true });
        }
        sendResponse({ ok: true, url: targetUrl });
      });
    });
    return true;
  }

  if (message.type === "sendToDesktop") {
    const videoUrl = String(message.url || "");
    let settled = false;

    try {
      const socket = new WebSocket("ws://localhost:27182");
      const timeout = setTimeout(() => {
        if (settled) return;
        settled = true;
        try {
          socket.close();
        } catch {
          // ignore
        }
        sendResponse({ ok: false, error: "Desktop app is not running." });
      }, 1500);

      socket.addEventListener("open", () => {
        if (settled) return;
        settled = true;
        clearTimeout(timeout);
        socket.send(JSON.stringify({ url: videoUrl }));
        socket.close();
        sendResponse({ ok: true });
      });

      socket.addEventListener("error", () => {
        if (settled) return;
        settled = true;
        clearTimeout(timeout);
        sendResponse({ ok: false, error: "Unable to reach desktop app." });
      });
    } catch {
      sendResponse({ ok: false, error: "Unable to reach desktop app." });
    }
    return true;
  }

  if (message.type === "getTabLinks") {
    sendResponse({ links: getLinksForTab(message.tabId) });
    return;
  }

  if (message.type === "addDomLinks") {
    const tabId = sender?.tab?.id;
    if (typeof tabId !== "number") {
      sendResponse({ ok: false });
      return;
    }

    const links = Array.isArray(message.links) ? message.links : [];
    links.forEach((url) => addLink(tabId, url, "dom"));
    sendResponse({ ok: true });
  }
});
