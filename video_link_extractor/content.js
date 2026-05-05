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
});

observer.observe(document.documentElement, {
  childList: true,
  subtree: true,
  attributes: true,
  attributeFilter: ["src"]
});
