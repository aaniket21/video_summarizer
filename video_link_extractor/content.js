function collectDomMediaLinks() {
  const links = new Set();

  const videoElements = document.querySelectorAll("video");
  videoElements.forEach((video) => {
    if (video.currentSrc) {
      links.add(video.currentSrc);
    }
    if (video.src) {
      links.add(video.src);
    }

    const sourceElements = video.querySelectorAll("source");
    sourceElements.forEach((source) => {
      if (source.src) {
        links.add(source.src);
      }
    });
  });

  return Array.from(links);
}

function publishDomLinks() {
  const links = collectDomMediaLinks();
  if (!links.length) {
    return;
  }

  chrome.runtime.sendMessage({
    type: "addDomLinks",
    links
  });
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "collectDomLinks") {
    sendResponse({ links: collectDomMediaLinks() });
  }
});

publishDomLinks();

const observer = new MutationObserver(() => {
  publishDomLinks();
  ensureFab();
});

observer.observe(document.documentElement, {
  childList: true,
  subtree: true,
  attributes: true,
  attributeFilter: ["src"]
});

let fabButton = null;
let fabPanel = null;

function getPrimaryVideoUrl() {
  const video = document.querySelector("video");
  if (video?.currentSrc) return video.currentSrc;
  if (video?.src) return video.src;
  const source = video?.querySelector("source[src]");
  if (source?.src) return source.src;
  return window.location.href;
}

function ensureFabStyles() {
  if (document.getElementById("lecturelens-fab-style")) return;
  const style = document.createElement("style");
  style.id = "lecturelens-fab-style";
  style.textContent = `
    .lecturelens-fab {
      position: fixed;
      right: 18px;
      bottom: 18px;
      z-index: 999999;
      border-radius: 999px;
      border: none;
      background: #0f172a;
      color: #ffffff;
      padding: 10px 14px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 8px 22px rgba(15, 23, 42, 0.25);
    }
    .lecturelens-panel {
      position: fixed;
      right: 18px;
      bottom: 60px;
      z-index: 999999;
      width: 220px;
      background: #ffffff;
      border-radius: 14px;
      border: 1px solid rgba(148, 163, 184, 0.35);
      padding: 10px;
      box-shadow: 0 18px 36px rgba(15, 23, 42, 0.18);
      font-family: "Segoe UI", Tahoma, sans-serif;
    }
    .lecturelens-panel.hidden { display: none; }
    .lecturelens-panel h4 {
      margin: 0 0 8px 0;
      font-size: 12px;
      color: #334155;
    }
    .lecturelens-panel button {
      width: 100%;
      margin-bottom: 6px;
      padding: 8px 10px;
      border-radius: 10px;
      border: 1px solid #cbd5e1;
      background: #f8fafc;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
    }
  `;
  document.head.appendChild(style);
}

function removeFab() {
  fabButton?.remove();
  fabPanel?.remove();
  fabButton = null;
  fabPanel = null;
}

function ensureFab() {
  const hasVideo = Boolean(document.querySelector("video"));
  if (!hasVideo) {
    removeFab();
    return;
  }

  if (fabButton) return;
  ensureFabStyles();

  fabButton = document.createElement("button");
  fabButton.className = "lecturelens-fab";
  fabButton.textContent = "Summarize";

  fabPanel = document.createElement("div");
  fabPanel.className = "lecturelens-panel hidden";
  fabPanel.innerHTML = `
    <h4>Send to LectureLens</h4>
    <button data-action="web">Summarize in Web App</button>
    <button data-action="desktop">Send to Desktop App</button>
  `;

  fabButton.addEventListener("click", () => {
    fabPanel.classList.toggle("hidden");
  });

  fabPanel.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const action = target.getAttribute("data-action");
    if (!action) return;

    const videoUrl = getPrimaryVideoUrl();
    if (action === "web") {
      chrome.runtime.sendMessage({ type: "openWebApp", url: videoUrl });
    }
    if (action === "desktop") {
      chrome.runtime.sendMessage({ type: "sendToDesktop", url: videoUrl });
    }
    fabPanel.classList.add("hidden");
  });

  document.body.appendChild(fabButton);
  document.body.appendChild(fabPanel);
}

ensureFab();
