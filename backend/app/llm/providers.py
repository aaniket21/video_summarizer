import os
import re
from typing import Callable, Dict, List

import httpx

from backend.app.secrets import get_secret


def sanitize_text(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def extract_title_from_markdown(markdown: str) -> str:
    match = re.search(r"^#\s+(.*)$", markdown, re.MULTILINE)
    if match and match.group(1):
        return match.group(1).strip()

    for line in markdown.split("\n"):
        candidate = line.strip()
        if candidate:
            return candidate

    return "AI Video Lecture Notes"


def build_prompt(transcript: str, chapters: List[str]) -> str:
    chapter_text = "\n".join(f"- {c}" for c in chapters) if chapters else "- No strong chapter splits found"
    return (
        f"""
Create polished lecture notes based on the transcript below.

Requirements:
- Output valid, clean markdown only.
- Use long paragraphs and readable bullet lists.
- Avoid decorative markdown clutter such as repeated separators or excessive bold markers.
- Make it study-friendly and visually structured for PDF export.
- Cover all important details, examples, interview angles, and edge cases.
- Explain complex concepts in a simple way, as if teaching a beginner.
- For code snippets, use markdown code blocks with appropriate language tags.
- If the transcript is too short, expand on key concepts with general knowledge.
- If the transcript is very long, prioritize clarity and conciseness while covering all major points.
- Include a variety of examples and interview questions that could be asked on the topic.

Output format (in this exact order):
1) Title as a single H1 at the very top (start with "# ")
2) Heading "Quick Revision"
3) Heading "Key Concepts"
4) Heading "Detailed Explanation"
5) Heading "Examples"
6) Heading "Interview Questions"
7) Heading "Summary"

Potential chapter candidates:
{chapter_text}

Transcript:
{transcript}
"""
    ).strip()


def _gemini_client(prompt: str) -> str:
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured on the server.")

    try:
        import google.generativeai as genai
        from google.generativeai import GenerativeModel
    except ModuleNotFoundError as exc:
        raise RuntimeError("google-generativeai is not installed on the server.") from exc

    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    model = GenerativeModel(model_name)
    result = model.generate_content(prompt)
    if hasattr(result, "response") and hasattr(result.response, "text"):
        return str(result.response.text())
    if hasattr(result, "text"):
        return str(result.text)
    return ""


def _openai_client(prompt: str) -> str:
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured on the server.")

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }

    with httpx.Client(timeout=60) as client:
        response = client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(f"OpenAI request failed ({response.status_code}).")
        data = response.json()

    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    return str(content or "")


def _claude_client(prompt: str) -> str:
    api_key = get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured on the server.")

    model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }

    with httpx.Client(timeout=60) as client:
        response = client.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(f"Claude request failed ({response.status_code}).")
        data = response.json()

    content_blocks = data.get("content", [])
    if not content_blocks:
        return ""
    return str(content_blocks[0].get("text", ""))


def _generate_markdown(prompt: str, provider: str) -> str:
    if provider == "gemini":
        return _gemini_client(prompt)
    if provider == "openai":
        return _openai_client(prompt)
    if provider == "claude":
        return _claude_client(prompt)
    raise RuntimeError(f"Unknown LLM provider: {provider}")


def _generate_with_provider(provider: str, transcript: str, chapters: List[str]) -> Dict[str, str]:
    prompt = build_prompt(transcript, chapters)
    markdown = _generate_markdown(prompt, provider)
    markdown = sanitize_text(markdown or "")
    if not markdown:
        raise RuntimeError("empty response")
    title = extract_title_from_markdown(markdown)
    return {"title": title, "notesMarkdown": markdown}


def generate_with_gemini(transcript: str, chapters: List[str]) -> Dict[str, str]:
    return _generate_with_provider("gemini", transcript, chapters)


def generate_with_openai(transcript: str, chapters: List[str]) -> Dict[str, str]:
    return _generate_with_provider("openai", transcript, chapters)


def generate_with_claude(transcript: str, chapters: List[str]) -> Dict[str, str]:
    return _generate_with_provider("claude", transcript, chapters)


def _provider_sequence() -> List[str]:
    preferred = os.getenv("LLM_PROVIDER", "gemini").strip().lower() or "gemini"
    fallbacks = os.getenv("LLM_FALLBACKS", "claude,openai")
    ordered: List[str] = []

    def add(name: str) -> None:
        if name and name not in ordered:
            ordered.append(name)

    add(preferred)
    for raw in fallbacks.split(","):
        add(raw.strip().lower())

    return [p for p in ordered if p in PROVIDERS]


def generate_notes(transcript: str, chapters: List[str]) -> Dict[str, str]:
    errors: List[str] = []

    for provider in _provider_sequence():
        handler = PROVIDERS.get(provider)
        if not handler:
            continue
        try:
            return handler(transcript, chapters)
        except Exception as exc:
            errors.append(f"{provider}: {exc}")
            continue

    error_text = "; ".join(errors) if errors else "No providers configured"
    raise RuntimeError(f"All providers failed: {error_text}")


PROVIDERS: Dict[str, Callable[[str, List[str]], Dict[str, str]]] = {
    "gemini": generate_with_gemini,
    "openai": generate_with_openai,
    "claude": generate_with_claude,
}
