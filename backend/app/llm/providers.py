import os
import re
from typing import Any, Callable, Dict, List, Sequence

import httpx

from backend.app.secrets import get_secret
from .study_tools import normalize_study_pack, parse_structured_payload, sanitize_text


def extract_title_from_markdown(markdown: str) -> str:
    match = re.search(r"^#\s+(.*)$", markdown, re.MULTILINE)
    if match and match.group(1):
        return match.group(1).strip()

    for line in markdown.split("\n"):
        candidate = line.strip()
        if candidate:
            return candidate

    return "AI Video Lecture Notes"


def build_prompt(
    transcript: str,
    chapters: Sequence[str],
    style: str = "student_notes",
    output_language: str = "en",
) -> str:
    chapter_text = "\n".join(f"- {c}" for c in chapters) if chapters else "- No strong chapter splits found"
    return (
        f"""
Create a structured study pack based on the transcript below.

Requirements:
- Output valid JSON only.
- Include these keys: title, tldr, keyConcepts, sections, definitions, quizQuestions, flashcards, notesMarkdown, speakerLabels, chapterCandidates, style, outputLanguage.
- Write the notes in {output_language}.
- Use the note style: {style}.
- Keep quiz questions grounded in the transcript.
- Include flashcards for important terms and definitions.
- Include speaker labels when the transcript suggests multiple speakers.

Output format (in this exact order):
1) Return one JSON object.
2) Do not wrap the JSON in markdown fences.
3) Do not add commentary outside the JSON object.

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


def _ollama_client(prompt: str) -> str:
    model = os.getenv("OLLAMA_MODEL", "llama3.1")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }

    with httpx.Client(timeout=90) as client:
        response = client.post(f"{base_url.rstrip('/')}/api/generate", json=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"Ollama request failed ({response.status_code}).")
        data = response.json()

    return str(data.get("response", ""))


def _generate_markdown(prompt: str, provider: str) -> str:
    if provider == "gemini":
        return _gemini_client(prompt)
    if provider == "openai":
        return _openai_client(prompt)
    if provider == "claude":
        return _claude_client(prompt)
    if provider == "ollama":
        return _ollama_client(prompt)
    raise RuntimeError(f"Unknown LLM provider: {provider}")


def _generate_with_provider(
    provider: str,
    transcript: str,
    chapters: Sequence[str],
    style: str = "student_notes",
    output_language: str = "en",
) -> Dict[str, Any]:
    prompt = build_prompt(transcript, chapters, style=style, output_language=output_language)
    raw_response = _generate_markdown(prompt, provider)
    structured = parse_structured_payload(raw_response)

    if structured:
        return normalize_study_pack(
            structured,
            transcript=transcript,
            chapters=chapters,
            style=style,
            output_language=output_language,
        )

    markdown = sanitize_text(raw_response or "")
    if not markdown:
        raise RuntimeError("empty response")

    return normalize_study_pack(
        {
            "title": extract_title_from_markdown(markdown),
            "notesMarkdown": markdown,
        },
        transcript=transcript,
        chapters=chapters,
        style=style,
        output_language=output_language,
    )


def generate_with_gemini(transcript: str, chapters: Sequence[str], style: str = "student_notes", output_language: str = "en") -> Dict[str, Any]:
    return _generate_with_provider("gemini", transcript, chapters, style=style, output_language=output_language)


def generate_with_openai(transcript: str, chapters: Sequence[str], style: str = "student_notes", output_language: str = "en") -> Dict[str, Any]:
    return _generate_with_provider("openai", transcript, chapters, style=style, output_language=output_language)


def generate_with_claude(transcript: str, chapters: Sequence[str], style: str = "student_notes", output_language: str = "en") -> Dict[str, Any]:
    return _generate_with_provider("claude", transcript, chapters, style=style, output_language=output_language)


def generate_with_ollama(transcript: str, chapters: Sequence[str], style: str = "student_notes", output_language: str = "en") -> Dict[str, Any]:
    return _generate_with_provider("ollama", transcript, chapters, style=style, output_language=output_language)


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


def generate_notes(transcript: str, chapters: Sequence[str], style: str = "student_notes", output_language: str = "en") -> Dict[str, Any]:
    errors: List[str] = []

    for provider in _provider_sequence():
        handler = PROVIDERS.get(provider)
        if not handler:
            continue
        try:
            return handler(transcript, chapters, style=style, output_language=output_language)
        except Exception as exc:
            errors.append(f"{provider}: {exc}")
            continue

    error_text = "; ".join(errors) if errors else "No providers configured"
    raise RuntimeError(f"All providers failed: {error_text}")


PROVIDERS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "gemini": generate_with_gemini,
    "openai": generate_with_openai,
    "claude": generate_with_claude,
    "ollama": generate_with_ollama,
}
