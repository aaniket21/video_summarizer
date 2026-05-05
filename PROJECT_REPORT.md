# AI Video Lecture Summarizer Project Report

## 1. Executive Summary

This repository contains a multi-part video summarization system built around lecture-style content. Its main purpose is to take a video or a video link, extract the audio, transcribe the speech, convert the transcript into structured study notes, and export the result as both Markdown and PDF.

The repository is not one single application. It is a small ecosystem with three separate user-facing pieces:

1. A Python desktop application in `app.py`.
2. A Next.js web application in `web/`.
3. A Chrome extension in `video_link_extractor/`.

The desktop and web applications do the summarization work. The Chrome extension is a helper tool that finds likely playable media URLs in the current browser tab.

The sample data currently in the workspace is mostly about MongoDB data modeling and document design, which shows the project being used to generate lecture notes from educational videos.

## 2. What The Project Does

At a high level, the project solves this workflow:

1. Get a lecture video from a URL or local file.
2. Extract audio from the video.
3. Run speech transcription.
4. Turn the transcript into readable study notes.
5. Export the final notes as Markdown and PDF.
6. Keep a local history of completed summaries.

The project also includes a video-link extractor extension for finding media URLs inside a browser tab, which can help users copy a direct stream or file URL for use in the summarizer.

## 3. Repository Layout

The important top-level folders are:

- `app.py`: Tkinter-based desktop summarizer.
- `web/`: Next.js browser-based summarizer.
- `video_link_extractor/`: Chrome extension for detecting media URLs.
- `videos/`: downloaded or staged source videos.
- `audio/`: extracted WAV audio files.
- `transcripts/`: raw transcript text files.
- `notes/`: generated Markdown notes.
- `pdf/`: generated PDF notes.
- `README.md`: top-level description of the desktop workflow.
- `PROJECT_REPORT.md`: this report.

The data folders are generated working/output directories. They are not the application source code; they are where the apps store intermediate and final artifacts.

## 4. End-to-End Data Flow

### Desktop application flow

The Python desktop app in `app.py` follows this pipeline:

1. Collect video URLs from a text box or accept dragged-and-dropped local video files.
2. Download each URL using `yt-dlp` or use the local file directly.
3. Extract a mono 16 kHz WAV file with `ffmpeg`.
4. Transcribe the audio with Whisper.
5. Generate a title and structured notes with Gemini.
6. Save the transcript and notes into the local output folders.
7. Render the notes into a styled PDF.
8. Optionally delete the source video after processing.

### Web application flow

The Next.js app in `web/` uses a similar pipeline, but it is split between browser workers and server routes:

1. The user pastes a URL or uploads a video file.
2. A browser worker runs FFmpeg in WebAssembly to extract audio.
3. Another worker runs Whisper transcription in the browser.
4. A Next.js API route sends the transcript to Gemini.
5. The browser builds a PDF from the generated Markdown.
6. The app stores completed jobs in browser local storage and allows them to be reopened later.

### Browser extension flow

The Chrome extension does not summarize videos. It finds possible media links by:

1. Watching network requests for media-like URLs.
2. Reading `<video>` and `<source>` elements from the page DOM.
3. Ranking detected links by likely usefulness.
4. Showing them in a popup or side panel.
5. Letting the user copy a URL quickly.

## 5. Desktop App Details

### Main file

The desktop entry point is `app.py`. It is a Tkinter GUI that orchestrates the whole pipeline from download to PDF export.

### User interface

The UI contains:

- A multiline input for video links.
- A drag-and-drop area for local video files.
- A checkbox to delete the source video after processing.
- A Start button.
- A progress bar.
- A live log window.

### Core processing stages

The desktop app uses these core functions:

- `download_video()`: downloads media with `yt-dlp`.
- `extract_audio()`: converts video to WAV with `ffmpeg`.
- `transcribe()`: transcribes audio with Whisper and saves a transcript text file.
- `extract_chapters()`: makes a simple heuristic list of possible chapter candidates from the transcript.
- `generate_notes()`: asks Gemini to produce clean Markdown study notes.
- `export_pdf()`: renders Markdown into a styled PDF using ReportLab.

### Desktop behavior

The desktop app runs Whisper locally and uses GPU acceleration if PyTorch sees CUDA. If Gemini is unavailable, the app falls back to a basic transcript-based summary rather than failing completely.

### Desktop output files

The desktop app writes to these folders:

- `videos/`: downloaded source video files.
- `audio/`: extracted WAV audio.
- `transcripts/`: raw transcript text.
- `notes/`: generated Markdown notes.
- `pdf/`: generated PDF files.

## 6. Web App Details

### Main app

The browser application lives in `web/src/app/page.tsx`. It is a client-heavy React page that manages the full summarization workflow inside the browser.

### Major features

- URL input and file upload.
- Drag-and-drop file support.
- Client-side audio extraction with FFmpeg WASM.
- Browser-side transcription with Xenova Whisper.
- Gemini note generation through a server route.
- Markdown preview.
- PDF download.
- Job history saved in local storage.
- Shareable history links based on a job ID in the query string.
- Light/dark theme switching.

### State management

The app uses a Zustand store in `web/src/store/useSummarizerStore.ts` to hold:

- Current job state.
- Progress and logs.
- Transcript text.
- Generated title.
- Generated Markdown notes.
- Local history.
- Theme choice.

### Browser workers

The web app uses two Web Workers:

- `web/src/workers/ffmpegWorker.ts`: extracts WAV audio from the source video.
- `web/src/workers/whisperWorker.ts`: transcribes the WAV audio.

This keeps the UI responsive while the heavy work runs off the main thread.

### API routes

The web app includes two server routes:

- `web/src/app/api/generate-notes/route.ts`: sends transcript text to Gemini and returns Markdown notes.
- `web/src/app/api/download-audio/route.ts`: calls a Python helper script to download and convert audio when browser-side access is blocked.

### Server fallback

If a remote video URL cannot be fetched directly in the browser, the app falls back to the Python script at `web/server/download_audio.py`. That script downloads the best audio with `yt-dlp`, converts it to WAV with `ffmpeg`, and returns the WAV bytes as base64.

### Web PDF generation

The browser app does not use ReportLab. Instead, it parses Markdown and creates PDFs with `pdf-lib` in `web/src/lib/pdf.ts`.

## 7. Chrome Extension Details

### Purpose

The extension in `video_link_extractor/` helps users find media URLs on pages that play video content. This is useful when the lecture source is embedded in a site and the direct stream URL is not obvious.

### Components

- `manifest.json`: extension definition and permissions.
- `background.js`: stores detected URLs and handles tab-level link aggregation.
- `content.js`: reads the DOM for video and source tags.
- `popup.html` and `popup.js`: popup UI and link ranking.
- `sidebar.html` and `sidebar.js`: persistent side panel version of the same UI.
- `popup.css`: shared styling.

### Detection strategy

The extension uses two approaches:

1. Network observation through `webRequest`.
2. DOM inspection through a content script.

It classifies detected URLs as direct files, HLS playlists, DASH manifests, segments, subtitles, or audio-only streams, then scores them so the most likely main media URL appears first.

## 8. Sample Data In The Workspace

The repository already contains several generated sample outputs. These show the system being used on MongoDB lecture content.

### Sample transcripts

- `transcripts/U2 Conclusion.txt`
- `transcripts/U2L4 Data Relationships.txt`

### Sample notes

- `notes/Foundations of Data Modeling for MongoDB.md`
- `notes/__MongoDB Document Model and Data Modeling Review__.md`
- `notes/__MongoDB Document Model and Modeling Review__.md`
- `notes/__Modeling Relationships_ Embedding and Referencing__.md`
- `notes/U2 Conclusion_notes.md`

### Sample audio and PDF outputs

- `audio/U2 Conclusion.wav`
- `audio/U2L4 Data Relationships.wav`
- `audio/b17b43f48f7db2b3a88b88f4d0489ad1ddf456a8.wav`
- `pdf/__MongoDB Document Model and Modeling Review__.pdf`

These artifacts show the project’s expected output shape: a transcript, a polished note document, and a printable PDF.

## 9. Content Theme Of The Existing Samples

The currently checked-in notes and transcripts focus on MongoDB document modeling, especially:

- Entities and attributes.
- One-to-one, one-to-many, and many-to-many relationships.
- Embedding versus referencing.
- BSON versus JSON.
- Document, collection, and database hierarchy.

That does not mean the code is limited to MongoDB. It means the current sample material in the repo happens to be about that topic.

## 10. External Dependencies And Runtime Requirements

### Desktop app requirements

The desktop app expects:

- Python 3.10+.
- `ffmpeg` on `PATH`.
- Internet access for downloads and Gemini calls.
- A display environment for Tkinter.

Python packages used by the desktop app include:

- `google-generativeai`
- `openai-whisper`
- `yt-dlp`
- `torch`
- `reportlab`
- `tkinterdnd2`

### Web app requirements

The web app expects:

- Node.js and npm.
- A Gemini API key in the environment.
- Optionally `GEMINI_MODEL`.
- For server fallback, Python, `yt-dlp`, and `ffmpeg` available on the machine running Next.js.

### Browser extension requirements

The extension runs in Chrome or a Chromium-based browser with Manifest V3 support.

## 11. Configuration And Environment Variables

### Desktop app

The desktop app currently has the Gemini API key hardcoded in `app.py`. That works technically, but it is not a safe long-term configuration strategy.

### Web app

The web app correctly expects environment variables:

- `GEMINI_API_KEY`
- `GEMINI_MODEL` optional, defaults to `gemini-3-flash-preview`

## 12. Important Design Choices

### Why the desktop app exists

The desktop app is the simplest way to run the pipeline locally with fewer browser limitations. It can directly use local files, Whisper, and ReportLab without needing a browser runtime.

### Why the web app exists

The web app provides a more modern interactive experience and shifts most of the processing into the browser. That makes it easier to use on a system where the user wants a single page workflow.

### Why the extension exists

The extension complements the summarizer by helping users find the media source URL when a video is embedded or obscured behind page scripting.

## 13. Strengths

The project has several clear strengths:

- It supports both URL-based and local-file-based workflows.
- It offers a desktop option and a browser option.
- It provides a PDF export, not just plain text output.
- It keeps a local history of prior jobs in the web app.
- It uses workers in the browser so the UI stays responsive.
- It has a practical helper extension for extracting media links.

## 14. Limitations And Risks

The current codebase also has some clear limitations:

- The desktop app stores a Gemini API key directly in source code.
- The desktop app depends on external network services for note generation.
- Browser-side processing can be limited by video size and cross-origin restrictions.
- Whisper transcription is computationally heavy and can be slow on weaker machines.
- The browser model and FFmpeg workers load lazily, so the first run can feel slow.
- The web server fallback depends on Python, `yt-dlp`, and `ffmpeg` being installed on the host machine.

## 15. Security And Maintenance Notes

The most important maintenance issue is the hardcoded Gemini key in `app.py`. That should be moved to an environment variable so the repository does not store credentials in source.

The desktop app also imports `google.generativeai`, which the README notes is showing deprecation warnings. The web app already uses `@google/generative-ai` in its server route, which is a cleaner pattern for the browser-side architecture.

The project also generates a lot of large binary output. The `.gitignore` correctly excludes `videos/`, `audio/`, `transcripts/`, `notes/`, `pdf/`, local virtual environments, and common cache folders.

## 16. How To Run Each Part

### Desktop app

1. Install Python dependencies.
2. Ensure `ffmpeg` is installed.
3. Run `python app.py` from the repository root.

### Web app

1. Change into `web/`.
2. Run `npm install`.
3. Set `GEMINI_API_KEY` in the environment.
4. Run `npm run dev`.

### Chrome extension

1. Open Chrome and go to `chrome://extensions`.
2. Enable Developer mode.
3. Load the unpacked folder `video_link_extractor/`.

## 17. Key Files At A Glance

- `app.py`: desktop orchestration and PDF generation.
- `README.md`: desktop app overview and setup.
- `web/src/app/page.tsx`: main browser UI and pipeline.
- `web/src/app/api/generate-notes/route.ts`: Gemini note generation endpoint.
- `web/src/app/api/download-audio/route.ts`: server audio fallback.
- `web/src/lib/pdf.ts`: browser PDF exporter.
- `web/src/lib/storage.ts`: local history storage.
- `web/src/store/useSummarizerStore.ts`: app state.
- `web/src/workers/ffmpegWorker.ts`: video-to-audio extraction.
- `web/src/workers/whisperWorker.ts`: speech transcription.
- `video_link_extractor/background.js`: media URL aggregation.
- `video_link_extractor/content.js`: DOM-based URL discovery.
- `video_link_extractor/popup.js`: popup UI behavior.
- `video_link_extractor/sidebar.js`: side panel UI behavior.

## 18. Bottom Line

This repository is a practical lecture-summarization toolkit. The core value is converting videos into study notes and PDFs, while the browser extension helps find video sources in the first place. The desktop app is the most direct end-to-end implementation, and the web app is the most polished interactive version. The sample content in the repository shows the intended use case clearly: educational lecture material, especially around MongoDB and data modeling.