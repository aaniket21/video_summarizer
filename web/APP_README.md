## AI Video Lecture Summarizer (Web App)

### Run locally

```powershell
cd web
npm install
npm run dev
```

Open: `http://localhost:3000`

### Gemini setup (required)

Notes generation is done by the backend route to keep your API key private:

```powershell
$env:GEMINI_API_KEY="YOUR_KEY"
```

Optional:

```powershell
$env:GEMINI_MODEL="gemini-3-flash-preview"
```

Backend routes:
- `POST /api/generate-notes`

### Client-first processing (what runs in your browser)

- FFmpeg WASM audio extraction (`src/workers/ffmpegWorker.ts`)
- Whisper transcription via WASM/ONNX (`src/workers/whisperWorker.ts`)
- Markdown preview + PDF generation (`src/lib/pdf.ts`)

### URL support (optional server fallback)

If a video URL can’t be downloaded directly in the browser (common with YouTube due to CORS), the app falls back to:
- `POST /api/download-audio`

That fallback requires the machine running Next.js to have:
- `python` in `PATH`
- Python package: `yt-dlp`
- `ffmpeg` in `PATH`

### Caching + history

Transcript + notes are cached in your browser (`localStorage`). History items can be reloaded.

