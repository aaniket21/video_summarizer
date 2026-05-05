# AI Video Lecture Summarizer

This project downloads lecture videos or accepts local video files, extracts audio, transcribes speech with Whisper, generates structured study notes with Gemini, and exports the result as both Markdown and PDF.

The application uses a Tkinter desktop UI, so it can be run locally without a web server.

## Features

- Download one or more videos from URLs using `yt-dlp`
- Accept dragged-and-dropped local video files
- Extract mono 16 kHz audio using `ffmpeg`
- Transcribe speech with OpenAI Whisper
- Generate structured lecture notes with Gemini
- Save outputs as Markdown and styled PDF
- Optionally delete source videos after processing

## Project Structure

- [app.py](/D:/ai-tools/video_summarizer/app.py): Main desktop application
- `videos/`: Downloaded or copied source videos
- `audio/`: Extracted `.wav` audio files
- `transcripts/`: Raw transcript `.txt` files
- `notes/`: Generated Markdown notes
- `pdf/`: Generated PDF notes

## How It Works

The application follows this pipeline:

1. Collect input videos from pasted URLs or dragged local files.
2. Download remote videos into the `videos/` folder.
3. Extract audio from each video with `ffmpeg`.
4. Transcribe the audio using the Whisper `base` model.
5. Detect a title and generate notes using Gemini.
6. Save the notes as Markdown in `notes/`.
7. Convert the Markdown-style notes into a styled PDF in `pdf/`.

## Requirements

You need the following installed on Windows:

- Python 3.10+
- `ffmpeg` available in `PATH`
- Internet access for video download and Gemini note generation
- A working display environment for Tkinter

Python packages used by the app:

- `google-generativeai`
- `openai-whisper`
- `yt-dlp`
- `torch`
- `reportlab`
- `tkinterdnd2`

## Installation

Create and activate a virtual environment if you want an isolated setup:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the Python dependencies:

```powershell
pip install google-generativeai openai-whisper yt-dlp torch reportlab tkinterdnd2
```

Install `ffmpeg` and ensure it is available from the terminal:

```powershell
ffmpeg -version
```

## Running the App

Start the desktop application:

```powershell
python app.py
```

In the UI:

1. Paste one video URL per line, or drag local video files into the drop area.
2. Click `Start`.
3. Wait for processing to finish.
4. Open the generated Markdown files in `notes/` or PDFs in `pdf/`.

## PDF Output

The PDF export is designed to be more readable than the raw Markdown output.

It includes:

- A styled title section
- Wrapped paragraphs so text does not overflow the page
- Rendered headings and bullet lists
- Better spacing between sections
- Code block styling for technical content
- Page header and footer chrome for a cleaner look

## Current Implementation Notes

- The app currently loads the Whisper `base` model at startup.
- If CUDA is available through PyTorch, Whisper will use GPU automatically.
- Gemini is currently configured inside [app.py](/D:/ai-tools/video_summarizer/app.py) with a hardcoded API key.
- The code uses the `google.generativeai` package, which now shows a deprecation warning.

## Recommended Improvement

The API key should be moved out of source code and loaded from an environment variable.

Example approach:

```powershell
$env:GEMINI_API_KEY="your-key-here"
python app.py
```

Then update the code to read:

```python
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
```

## Common Issues

### 1. `ffmpeg failed for: ...`

Cause:

- `ffmpeg` is not installed or not available in `PATH`
- The source video is corrupted or unsupported

Fix:

- Install `ffmpeg`
- Verify `ffmpeg -version` works in the terminal

### 2. GUI opens but processing fails during note generation

Cause:

- Gemini API issue
- Invalid API key
- Temporary network problem

Fix:

- Check your API key
- Confirm internet access
- Retry the job

### 3. PDF looks different from Markdown

Cause:

- The PDF renderer supports a clean subset of markdown-like formatting, not every possible Markdown feature

Fix:

- Keep generated notes structured with headings, bullets, short paragraphs, and fenced code blocks

### 4. App seems stuck on startup

Cause:

- Whisper model loading can take time on first run

Fix:

- Wait for model initialization to complete
- On slower machines, the first run can take noticeably longer

## Output Files

Typical generated files:

- `videos/<video-name>.mp4`
- `audio/<video-name>.wav`
- `transcripts/<video-name>.txt`
- `notes/<title>.md`
- `pdf/<title>.pdf`

These are generated artifacts and are ignored by Git in this project.

## Git Notes

The repository should not track large media or generated outputs. The included `.gitignore` excludes:

- Downloaded videos
- Extracted audio
- Generated transcripts
- Generated notes
- Generated PDFs
- Python cache files and local virtual environments

## Future Improvements

- Move Gemini configuration to environment variables
- Migrate from `google.generativeai` to `google.genai`
- Add a `requirements.txt`
- Add retry handling for network-dependent steps
- Add progress details per stage in the UI
- Add support for custom note templates

## Quick Start Summary

```powershell
pip install google-generativeai openai-whisper yt-dlp torch reportlab tkinterdnd2
python app.py
```

Make sure `ffmpeg` is installed before running the app.