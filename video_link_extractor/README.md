# Actual Video Link Extractor (Chrome Extension)

This extension detects and displays likely media URLs (for example `.m3u8`, `.mp4`, `.mpd`) from the active tab.

## What it does

- Watches network requests in the current tab and stores media-like URLs.
- Reads `<video>` and `<source>` elements from the page to catch direct links in the DOM.
- Shows all detected links in the popup.
- Lets you copy a URL with one click.

## How to install (developer mode)

1. Open Chrome and go to `chrome://extensions`.
2. Turn on **Developer mode**.
3. Click **Load unpacked**.
4. Select this folder: `d:\\ai-tools\\video_link_extractor`.

## How to use

1. Open a page with a playing video.
2. Click the extension icon.
3. Press **Refresh** in the popup if needed.
4. Copy the detected URL.

## Notes

- Some websites use DRM/protected streams, encrypted segments, or short-lived signed URLs.
- In those cases, a visible request URL may still not be directly downloadable.
- Use this only where you have permission.
