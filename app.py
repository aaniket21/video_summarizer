import os
import re
import subprocess
import threading
from datetime import datetime
from xml.sax.saxutils import escape

import google.generativeai as genai
import torch
import whisper
import yt_dlp
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Preformatted, SimpleDocTemplate, Spacer
from tkinter import *
from tkinter import messagebox, ttk
from tkinterdnd2 import DND_FILES, TkinterDnD

# ======================
# CONFIG
# ======================

GEMINI_API_KEY = "AIzaSyA9hWqSlz9LpPbFyY8Lutc-tee3VW1zKWo"
GEMINI_MODEL = "gemini-3-flash-preview"

BASE = os.path.dirname(os.path.abspath(__file__))
VIDEOS = os.path.join(BASE, "videos")
AUDIO = os.path.join(BASE, "audio")
TRANS = os.path.join(BASE, "transcripts")
NOTES = os.path.join(BASE, "notes")
PDF = os.path.join(BASE, "pdf")

for p in [VIDEOS, AUDIO, TRANS, NOTES, PDF]:
    os.makedirs(p, exist_ok=True)


def sanitize_filename(value: str) -> str:
    clean = re.sub(r"[\\/:*?\"<>|]", "_", value).strip()
    return clean[:120] if clean else "untitled"


def setup_gemini():
    if not GEMINI_API_KEY:
        return None
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        return genai.GenerativeModel(GEMINI_MODEL)
    except Exception:
        return None


gemini = setup_gemini()

# ======================
# WHISPER MODEL
# ======================

device = "cuda" if torch.cuda.is_available() else "cpu"
print("Whisper device:", device)
whisper_model = whisper.load_model("base", device=device)


def log(msg: str) -> None:
    # Tk widgets must be updated from the UI thread.
    root.after(0, lambda: (logbox.insert(END, msg + "\n"), logbox.see(END)))


def set_progress(value: int, maximum: int | None = None) -> None:
    def update() -> None:
        if maximum is not None:
            progress["maximum"] = maximum
        progress["value"] = value

    root.after(0, update)


# ======================
# DOWNLOAD VIDEO
# ======================

def download_video(url: str) -> list[str]:
    opts = {
        "outtmpl": os.path.join(VIDEOS, "%(title)s.%(ext)s"),
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": False,
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if "entries" in info and info["entries"]:
            return [ydl.prepare_filename(e) for e in info["entries"] if e]
        return [ydl.prepare_filename(info)]


def extract_audio(video: str) -> str:
    name = os.path.splitext(os.path.basename(video))[0]
    audio = os.path.join(AUDIO, f"{name}.wav")

    cmd = ["ffmpeg", "-i", video, "-ar", "16000", "-ac", "1", audio, "-y"]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for: {video}")

    return audio


def transcribe(audio: str) -> tuple[str, str]:
    result = whisper_model.transcribe(audio)
    text = result.get("text", "").strip()

    name = os.path.splitext(os.path.basename(audio))[0]
    path = os.path.join(TRANS, f"{name}.txt")

    with open(path, "w", encoding="utf8") as f:
        f.write(text)

    return text, name


def extract_chapters(text: str) -> list[str]:
    lines = text.split(". ")
    return [line.strip() for line in lines if len(line.strip()) > 60][:10]


def generate_notes(transcript: str, chapters: list[str]) -> str:
    chapter_text = "\n".join(f"- {c}" for c in chapters) if chapters else "- No strong chapter splits found"
    prompt = f"""
Create polished lecture notes based on the transcript below.

Requirements:
- Output valid, clean markdown only.
- Use long paragraphs and readable bullet lists. 
- Avoid decorative markdown clutter such as repeated separators or excessive bold markers.
- Make it study-friendly and visually structured for PDF export.
- Cover all important details, examples, interview angles, and edge cases.
- explain complex concepts in a simple way, as if teaching a beginner.
- For code snippets, use markdown code blocks with appropriate language tags.
- If the transcript is too short, expand on the key concepts with general knowledge.
- If the transcript is very long, prioritize clarity and conciseness while covering all major points.
- make sure to include a variety of examples and interview questions that could be asked on the topic.
- explain in descriptive way, avoid just listing points without explanation.
- explain the intuition behind concepts, not just the mechanics.

Sections:
1) Title
2) Quick Revision
3) Key Concepts
4) Detailed Explanation
5) Examples
6) Interview Questions
7) Summary

Potential chapter candidates:
{chapter_text}

Transcript:
{transcript}
""".strip()

    if gemini is None:
        return (
            "# Notes\n\n"
            "Gemini model is not configured. This is a fallback summary from transcript text.\n\n"
            f"{transcript[:5000]}"
        )

    response = gemini.generate_content(prompt)
    return (response.text or "").strip()


def detect_title(transcript: str, fallback_name: str) -> str:
    if gemini is None:
        return fallback_name

    prompt = f"Generate a short lecture title (max 7 words):\n{transcript[:1500]}"
    response = gemini.generate_content(prompt)
    title = (response.text or "").strip().replace("\n", " ")
    return sanitize_filename(title) or fallback_name


def build_pdf_styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "NotesTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=colors.HexColor("#102A43"),
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "NotesSubtitle",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#486581"),
            alignment=TA_CENTER,
            spaceAfter=18,
        ),
        "h1": ParagraphStyle(
            "Heading1Custom",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=22,
            textColor=colors.HexColor("#0B7285"),
            borderPadding=0,
            spaceBefore=14,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "Heading2Custom",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#1D3557"),
            spaceBefore=10,
            spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "Heading3Custom",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#334E68"),
            spaceBefore=8,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "BodyCustom",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=15,
            textColor=colors.HexColor("#1F2933"),
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "BulletCustom",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=15,
            leftIndent=18,
            firstLineIndent=0,
            textColor=colors.HexColor("#1F2933"),
            spaceAfter=4,
        ),
        "code": ParagraphStyle(
            "CodeCustom",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=8.5,
            leading=11,
            leftIndent=12,
            rightIndent=12,
            backColor=colors.HexColor("#F0F4F8"),
            borderColor=colors.HexColor("#D9E2EC"),
            borderWidth=0.6,
            borderPadding=8,
            spaceBefore=6,
            spaceAfter=10,
        ),
        "divider": ParagraphStyle(
            "DividerLabel",
            parent=styles["BodyText"],
            fontSize=1,
            leading=1,
            spaceBefore=4,
            spaceAfter=8,
        ),
    }


def markdown_inline_to_reportlab(text: str) -> str:
    safe = escape(text)
    safe = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', safe)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    safe = re.sub(r"\*(.+?)\*", r"<i>\1</i>", safe)
    return safe


def append_paragraph_buffer(story, buffer, style):
    if not buffer:
        return
    text = " ".join(part.strip() for part in buffer if part.strip())
    if text:
        story.append(Paragraph(markdown_inline_to_reportlab(text), style))
    buffer.clear()


def markdown_to_story(title: str, notes: str):
    styles = build_pdf_styles()
    story = [
        Spacer(1, 0.1 * inch),
        Paragraph(escape(title), styles["title"]),
        Paragraph(
            f"AI lecture notes generated on {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
            styles["subtitle"],
        ),
    ]

    lines = notes.splitlines()
    paragraph_buffer = []
    code_buffer = []
    in_code_block = False

    for raw_line in lines:
        stripped = raw_line.strip()

        if stripped.startswith("```"):
            append_paragraph_buffer(story, paragraph_buffer, styles["body"])
            if in_code_block:
                story.append(Preformatted("\n".join(code_buffer), styles["code"]))
                code_buffer.clear()
                in_code_block = False
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_buffer.append(raw_line.rstrip())
            continue

        if not stripped:
            append_paragraph_buffer(story, paragraph_buffer, styles["body"])
            story.append(Spacer(1, 0.06 * inch))
            continue

        if stripped in {"---", "***"}:
            append_paragraph_buffer(story, paragraph_buffer, styles["body"])
            story.append(Paragraph(" ", styles["divider"]))
            story.append(Spacer(1, 0.04 * inch))
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            append_paragraph_buffer(story, paragraph_buffer, styles["body"])
            level = min(len(heading_match.group(1)), 3)
            heading_text = markdown_inline_to_reportlab(heading_match.group(2).strip())
            story.append(Paragraph(heading_text, styles[f"h{level}"]))
            continue

        bullet_match = re.match(r"^([-*+])\s+(.*)$", stripped)
        if bullet_match:
            append_paragraph_buffer(story, paragraph_buffer, styles["body"])
            bullet_text = markdown_inline_to_reportlab(bullet_match.group(2).strip())
            story.append(Paragraph(bullet_text, styles["bullet"], bulletText="*"))
            continue

        numbered_match = re.match(r"^(\d+)[.)]\s+(.*)$", stripped)
        if numbered_match:
            append_paragraph_buffer(story, paragraph_buffer, styles["body"])
            bullet_text = markdown_inline_to_reportlab(numbered_match.group(2).strip())
            story.append(Paragraph(bullet_text, styles["bullet"], bulletText=f"{numbered_match.group(1)}."))
            continue

        paragraph_buffer.append(stripped)

    append_paragraph_buffer(story, paragraph_buffer, styles["body"])

    if code_buffer:
        story.append(Preformatted("\n".join(code_buffer), styles["code"]))

    return story


def draw_pdf_chrome(canvas, doc):
    page_width, page_height = letter
    canvas.saveState()

    canvas.setFillColor(colors.HexColor("#F8FBFF"))
    canvas.rect(0, 0, page_width, page_height, stroke=0, fill=1)

    canvas.setFillColor(colors.HexColor("#102A43"))
    canvas.rect(0, page_height - 42, page_width, 42, stroke=0, fill=1)

    canvas.setFillColor(colors.HexColor("#0B7285"))
    canvas.rect(0, page_height - 50, page_width * 0.28, 8, stroke=0, fill=1)

    canvas.setFillColor(colors.HexColor("#486581"))
    canvas.setFont("Helvetica", 9)
    footer = f"Page {doc.page}"
    canvas.drawRightString(page_width - 36, 24, footer)
    canvas.drawString(36, 24, "Video Summarizer Notes")

    canvas.restoreState()


def export_pdf(title: str, notes: str) -> str:
    path = os.path.join(PDF, f"{sanitize_filename(title)}.pdf")
    doc = SimpleDocTemplate(
        path,
        pagesize=letter,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.9 * inch,
        bottomMargin=0.7 * inch,
        title=title,
        author="Aniket",
    )
    story = markdown_to_story(title, notes)
    doc.build(story, onFirstPage=draw_pdf_chrome, onLaterPages=draw_pdf_chrome)
    return path


def process_video(video: str) -> None:
    log(f"Audio extraction: {video}")
    audio = extract_audio(video)

    log("Transcription")
    transcript, base_name = transcribe(audio)

    log("Title detection")
    title = detect_title(transcript, base_name)

    log("Notes generation")
    chapters = extract_chapters(transcript)
    notes = generate_notes(transcript, chapters)

    notes_file = os.path.join(NOTES, f"{sanitize_filename(title)}.md")
    with open(notes_file, "w", encoding="utf8") as f:
        f.write(notes)

    pdf_file = export_pdf(title, notes)
    log(f"Saved notes: {notes_file}")
    log(f"Saved pdf: {pdf_file}")

    if delete_var.get() and os.path.exists(video):
        os.remove(video)
        log(f"Deleted source video: {video}")


def collect_videos() -> list[str]:
    urls = [u.strip() for u in url_box.get("1.0", END).splitlines() if u.strip()]
    videos = []

    for url in urls:
        log(f"Downloading: {url}")
        videos.extend(download_video(url))

    videos.extend(dropped)

    # Preserve order and remove duplicates.
    unique = []
    seen = set()
    for v in videos:
        if v not in seen:
            unique.append(v)
            seen.add(v)
    return unique


def run_pipeline() -> None:
    try:
        videos = collect_videos()
        if not videos:
            root.after(0, lambda: messagebox.showinfo("Info", "No videos provided"))
            return

        set_progress(0, maximum=len(videos))

        for i, video in enumerate(videos, start=1):
            log(f"Processing ({i}/{len(videos)}): {video}")
            process_video(video)
            set_progress(i)

        log("All videos processed")
    except Exception as exc:
        log(f"Error: {exc}")
    finally:
        root.after(0, lambda: start_btn.config(state=NORMAL))


def start() -> None:
    start_btn.config(state=DISABLED)
    threading.Thread(target=run_pipeline, daemon=True).start()


# ======================
# GUI
# ======================

dropped = []


def drop(e) -> None:
    files = root.tk.splitlist(e.data)
    for f in files:
        dropped.append(f)
        log(f"Added {f}")


root = TkinterDnD.Tk()
root.title("AI Video Lecture Summarizer v2")
root.geometry("750x600")

Label(root, text="Video links (one per line)").pack(anchor="w", padx=10, pady=(10, 0))

url_box = Text(root, height=6)
url_box.pack(fill=X, padx=10)

Label(root, text="Drag video files below").pack(anchor="w", padx=10, pady=(10, 0))

frame = Frame(root, height=100, bg="#dddddd")
frame.pack(fill=X, padx=10, pady=5)

frame.drop_target_register(DND_FILES)
frame.dnd_bind("<<Drop>>", drop)

delete_var = BooleanVar()
Checkbutton(root, text="Delete video after processing", variable=delete_var).pack(anchor="w", padx=10)

start_btn = Button(root, text="Start", command=start)
start_btn.pack(pady=10)

progress = ttk.Progressbar(root, length=700)
progress.pack(pady=10, padx=10)

logbox = Text(root, height=20)
logbox.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

root.mainloop()




