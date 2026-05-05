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
