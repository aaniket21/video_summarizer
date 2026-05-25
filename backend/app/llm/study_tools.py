from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Sequence

_STOPWORDS = {
    "a",
    "about",
    "after",
    "again",
    "all",
    "also",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "doing",
    "during",
    "each",
    "for",
    "from",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "him",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "just",
    "like",
    "made",
    "make",
    "may",
    "me",
    "more",
    "most",
    "my",
    "no",
    "not",
    "of",
    "on",
    "one",
    "or",
    "other",
    "our",
    "out",
    "over",
    "said",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "up",
    "use",
    "used",
    "using",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "would",
    "you",
    "your",
}

STYLE_LIBRARY = {
    "student_notes": {
        "name": "Student Notes",
        "description": "Detailed lecture notes with definitions, examples, and revision cues.",
        "section_count": 4,
    },
    "executive_brief": {
        "name": "Executive Brief",
        "description": "Concise one-page summary with the most important takeaways.",
        "section_count": 3,
    },
    "cornell_notes": {
        "name": "Cornell Notes",
        "description": "Cue column plus notes column for active recall.",
        "section_count": 4,
    },
    "mind_map": {
        "name": "Mind Map Outline",
        "description": "Hierarchical headings and branches with minimal prose.",
        "section_count": 5,
    },
    "research_abstract": {
        "name": "Research Abstract",
        "description": "Academic abstract-style notes with methodology and implications.",
        "section_count": 4,
    },
}

SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "pt": "Portuguese",
    "ar": "Arabic",
    "zh": "Chinese (Simplified)",
    "ja": "Japanese",
}


def sanitize_text(text: str) -> str:
    return re.sub(r"\r\n?", "\n", text or "").strip()


def _split_sentences(text: str) -> List[str]:
    cleaned = sanitize_text(text)
    if not cleaned:
        return []
    pieces = re.split(r"(?<=[.!?])\s+", cleaned)
    sentences = [piece.strip() for piece in pieces if piece and piece.strip()]
    if len(sentences) <= 1:
        fallback = [line.strip() for line in cleaned.split("\n") if line.strip()]
        return fallback or sentences
    return sentences


def _split_paragraphs(text: str) -> List[str]:
    cleaned = sanitize_text(text)
    if not cleaned:
        return []
    return [paragraph.strip() for paragraph in re.split(r"\n\s*\n", cleaned) if paragraph.strip()]


def _normalize_words(text: str) -> List[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_\-']+", text.lower())
    return [word for word in words if len(word) > 2 and word not in _STOPWORDS]


def _top_keywords(text: str, limit: int = 8) -> List[str]:
    counts = Counter(_normalize_words(text))
    return [word.replace("_", " ") for word, _ in counts.most_common(limit)]


def _title_case_keyword(keyword: str) -> str:
    if not keyword:
        return keyword
    return " ".join(part.capitalize() for part in keyword.split())


def _truncate(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "..."


def _extract_definitions(sentences: Sequence[str], keywords: Sequence[str]) -> List[Dict[str, str]]:
    definitions: List[Dict[str, str]] = []
    for sentence in sentences:
        if len(definitions) >= 5:
            break
        match = re.search(r"^([A-Za-z][A-Za-z0-9 _\-]{2,60}?)\s+(?:is|are|means|refers to|describes)\s+(.*)$", sentence, re.IGNORECASE)
        if not match:
            continue
        term = _truncate(_title_case_keyword(match.group(1).strip()), 48)
        definition = _truncate(match.group(2).strip().rstrip("."), 180)
        if term and definition:
            definitions.append({"term": term, "definition": definition})

    for keyword in keywords:
        if len(definitions) >= 5:
            break
        term = _title_case_keyword(keyword)
        if any(item["term"].lower() == term.lower() for item in definitions):
            continue
        definitions.append(
            {
                "term": term,
                "definition": f"A core concept discussed in the lecture: {term}.",
            }
        )

    return definitions[:5]


def _build_sections(sentences: Sequence[str], chapters: Sequence[str], style_key: str) -> List[Dict[str, Any]]:
    section_count = STYLE_LIBRARY.get(style_key, STYLE_LIBRARY["student_notes"]).get("section_count", 4)
    candidate_headings = list(chapters[:section_count])
    if not candidate_headings:
        candidate_headings = [
            "Overview",
            "Key Ideas",
            "Examples and Applications",
            "Revision Notes",
        ][:section_count]

    if not sentences:
        return [{"heading": heading, "content": "No transcript content was provided.", "keyPoints": []} for heading in candidate_headings]

    chunk_size = max(1, len(sentences) // max(1, len(candidate_headings)))
    sections: List[Dict[str, Any]] = []
    for index, heading in enumerate(candidate_headings):
        start = index * chunk_size
        end = len(sentences) if index == len(candidate_headings) - 1 else min(len(sentences), (index + 1) * chunk_size)
        chunk = sentences[start:end] or sentences[-chunk_size:]
        content = " ".join(chunk).strip()
        key_points = [_truncate(sentence, 120) for sentence in chunk[:3]]
        sections.append({"heading": heading, "content": content, "keyPoints": key_points})
    return sections


def _build_flashcards(definitions: Sequence[Dict[str, str]], keywords: Sequence[str], title: str) -> List[Dict[str, Any]]:
    flashcards: List[Dict[str, Any]] = []
    for definition in definitions[:5]:
        flashcards.append(
            {
                "front": definition["term"],
                "back": definition["definition"],
                "tags": [title],
            }
        )

    for keyword in keywords[:3]:
        flashcards.append(
            {
                "front": f"Why is {keyword} important?",
                "back": f"{_title_case_keyword(keyword)} is one of the recurring ideas in the transcript.",
                "tags": [title, "quiz"],
            }
        )

    return flashcards[:8]


def _build_quiz_questions(keywords: Sequence[str], definitions: Sequence[Dict[str, str]], title: str) -> List[Dict[str, Any]]:
    questions: List[Dict[str, Any]] = []
    distractors = [_title_case_keyword(keyword) for keyword in keywords[1:4]] or ["General idea", "Supporting detail"]
    for index, definition in enumerate(definitions[:4]):
        correct = definition["term"]
        options = [correct]
        for distractor in distractors:
            if distractor.lower() != correct.lower() and distractor not in options:
                options.append(distractor)
        while len(options) < 4:
            options.append(f"Option {len(options) + 1}")
        questions.append(
            {
                "question": f"What best describes {correct}?",
                "options": options[:4],
                "answerIndex": 0,
                "explanation": definition["definition"],
                "tags": [title],
            }
        )

    if not questions and keywords:
        options = [_title_case_keyword(keyword) for keyword in keywords[:4]]
        while len(options) < 4:
            options.append(f"Option {len(options) + 1}")
        questions.append(
            {
                "question": f"Which topic was emphasized most in {title}?",
                "options": options,
                "answerIndex": 0,
                "explanation": f"The lecture centered on {_title_case_keyword(keywords[0])}.",
                "tags": [title],
            }
        )

    return questions[:5]


def _build_tldr(sentences: Sequence[str], keywords: Sequence[str], style_key: str) -> str:
    if not sentences:
        return "No transcript was provided."
    first_sentences = " ".join(sentences[:2])
    if style_key == "executive_brief":
        return _truncate(first_sentences, 180)
    if keywords:
        return _truncate(f"The lecture focuses on {', '.join(keywords[:3])}.", 180)
    return _truncate(first_sentences, 200)


def _build_markdown(title: str, tldr: str, sections: Sequence[Dict[str, Any]], definitions: Sequence[Dict[str, str]], quiz_questions: Sequence[Dict[str, Any]], flashcards: Sequence[Dict[str, Any]], style_key: str, output_language: str, speaker_labels: Sequence[str]) -> str:
    lines: List[str] = [f"# {title}", "", f"**Style:** {_title_case_keyword(style_key.replace('_', ' '))}", f"**Output language:** {SUPPORTED_LANGUAGES.get(output_language, output_language)}", "", "## Quick Revision", tldr, ""]

    if speaker_labels:
        lines.extend(["## Speaker Notes", ", ".join(speaker_labels), ""])

    if sections:
        for section in sections:
            lines.append(f"## {section['heading']}")
            content = str(section.get("content") or "").strip()
            if content:
                lines.append(content)
            key_points = section.get("keyPoints") or []
            if key_points:
                lines.append("")
                for point in key_points:
                    lines.append(f"- {point}")
            lines.append("")

    if definitions:
        lines.extend(["## Definitions", ""])
        for definition in definitions:
            lines.append(f"- **{definition['term']}**: {definition['definition']}")
        lines.append("")

    if quiz_questions:
        lines.extend(["## Quiz Questions", ""])
        for index, question in enumerate(quiz_questions, start=1):
            lines.append(f"{index}. {question['question']}")
            for option in question.get("options", []):
                lines.append(f"   - {option}")
            lines.append("")

    if flashcards:
        lines.extend(["## Flashcards", ""])
        for flashcard in flashcards:
            lines.append(f"- **{flashcard['front']}** → {flashcard['back']}")
        lines.append("")

    return "\n".join(line for line in lines if line is not None).strip() + "\n"


def detect_speaker_labels(transcript: str) -> List[str]:
    labels: List[str] = []
    for line in sanitize_text(transcript).split("\n"):
        match = re.match(r"^\s*([A-Za-z][A-Za-z0-9 _\-]{0,24}?)(?:\s*[:\-])\s+", line)
        if not match:
            continue
        candidate = match.group(1).strip()
        if candidate and candidate.lower() not in {label.lower() for label in labels}:
            labels.append(candidate)
    if labels:
        return labels[:4]
    if len(_split_paragraphs(transcript)) > 1:
        return ["Speaker 1", "Speaker 2"]
    return ["Speaker 1"]


def normalize_study_pack(
    payload: Dict[str, Any] | None,
    transcript: str,
    chapters: Sequence[str],
    style: str = "student_notes",
    output_language: str = "en",
    source_title: str | None = None,
    source_url: str | None = None,
) -> Dict[str, Any]:
    base_payload = dict(payload or {})
    transcript_text = sanitize_text(transcript)
    sentences = _split_sentences(transcript_text)
    keywords = _top_keywords(transcript_text)
    title = base_payload.get("title") or source_title or (keywords[0].title() if keywords else "AI Video Lecture Notes")
    style_key = style if style in STYLE_LIBRARY else "student_notes"
    speaker_labels = base_payload.get("speakerLabels") or detect_speaker_labels(transcript_text)
    sections = base_payload.get("sections") or _build_sections(sentences, chapters, style_key)
    definitions = base_payload.get("definitions") or _extract_definitions(sentences, keywords)
    tldr = base_payload.get("tldr") or _build_tldr(sentences, keywords, style_key)
    quiz_questions = base_payload.get("quizQuestions") or _build_quiz_questions(keywords, definitions, title)
    flashcards = base_payload.get("flashcards") or _build_flashcards(definitions, keywords, title)
    notes_markdown = base_payload.get("notesMarkdown") or _build_markdown(
        title=title,
        tldr=tldr,
        sections=sections,
        definitions=definitions,
        quiz_questions=quiz_questions,
        flashcards=flashcards,
        style_key=style_key,
        output_language=output_language,
        speaker_labels=speaker_labels,
    )

    if not notes_markdown.endswith("\n"):
        notes_markdown = notes_markdown + "\n"

    chapter_candidates = list(base_payload.get("chapterCandidates") or chapters or [])
    if not chapter_candidates:
        chapter_candidates = [section.get("heading", "") for section in sections if section.get("heading")]

    return {
        "title": title,
        "style": style_key,
        "styleLabel": STYLE_LIBRARY.get(style_key, STYLE_LIBRARY["student_notes"]).get("name", style_key),
        "styleDescription": STYLE_LIBRARY.get(style_key, STYLE_LIBRARY["student_notes"]).get("description", ""),
        "outputLanguage": output_language,
        "outputLanguageLabel": SUPPORTED_LANGUAGES.get(output_language, output_language),
        "sourceTitle": source_title or base_payload.get("sourceTitle") or title,
        "sourceUrl": source_url or base_payload.get("sourceUrl") or "",
        "notesMarkdown": notes_markdown,
        "tldr": tldr,
        "keyConcepts": base_payload.get("keyConcepts") or keywords[:8],
        "sections": sections,
        "definitions": definitions,
        "quizQuestions": quiz_questions,
        "flashcards": flashcards,
        "speakerLabels": speaker_labels,
        "chapterCandidates": chapter_candidates,
        "chatReady": True,
        "transcriptLanguage": base_payload.get("transcriptLanguage") or "auto",
    }


def build_chat_answer(question: str, transcript: str, notes_markdown: str = "", sections: Sequence[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    question_text = sanitize_text(question)
    transcript_text = sanitize_text(transcript)
    all_chunks: List[Dict[str, Any]] = []

    for index, sentence in enumerate(_split_sentences(transcript_text)):
        all_chunks.append({"source": "transcript", "index": index, "text": sentence})
    for index, line in enumerate(_split_sentences(notes_markdown)):
        all_chunks.append({"source": "notes", "index": index, "text": line})
    for section in sections or []:
        content = str(section.get("content") or "").strip()
        if content:
            all_chunks.append({"source": "section", "index": len(all_chunks), "text": f"{section.get('heading', 'Section')}: {content}"})

    query_words = set(_normalize_words(question_text))
    scored: List[tuple[float, Dict[str, Any]]] = []
    for chunk in all_chunks:
        words = set(_normalize_words(chunk["text"]))
        overlap = len(query_words & words)
        coverage = overlap / max(1, len(query_words))
        scored.append((overlap + coverage, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    top_chunks = [chunk for score, chunk in scored[:3] if score > 0]
    if not top_chunks and all_chunks:
        top_chunks = all_chunks[:2]

    if top_chunks:
        summary_bits = [chunk["text"] for chunk in top_chunks[:2]]
        answer = " ".join(summary_bits)
        answer = _truncate(answer, 360)
        if not answer.lower().startswith("based on"):
            answer = f"Based on the transcript, {answer[0].lower() + answer[1:] if answer else answer}"
    else:
        answer = "I could not find a direct match in the transcript, but the notes suggest the topic is covered in the summary."

    citations = [
        {
            "source": chunk["source"],
            "index": chunk["index"],
            "text": _truncate(chunk["text"], 220),
        }
        for chunk in top_chunks
    ]

    return {"answer": answer, "citations": citations}


def parse_structured_payload(text: str) -> Dict[str, Any] | None:
    candidate = sanitize_text(text)
    if not candidate:
        return None

    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate)

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        json_match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if not json_match:
            return None
        try:
            parsed = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            return None

    if isinstance(parsed, dict):
        return parsed
    return None
