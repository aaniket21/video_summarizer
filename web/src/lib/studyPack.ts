export type StudyStyle =
  | "student_notes"
  | "executive_brief"
  | "cornell_notes"
  | "mind_map"
  | "research_abstract";

export type StudySection = {
  heading: string;
  content: string;
  keyPoints: string[];
};

export type StudyDefinition = {
  term: string;
  definition: string;
};

export type StudyQuizQuestion = {
  question: string;
  options: string[];
  answerIndex: number;
  explanation: string;
};

export type StudyFlashcard = {
  front: string;
  back: string;
  tags: string[];
};

export type StudyCitation = {
  source: "transcript" | "notes" | "section";
  index: number;
  text: string;
};

export type StudyPack = {
  title: string;
  style: StudyStyle;
  outputLanguage: string;
  notesMarkdown: string;
  tldr: string;
  keyConcepts: string[];
  sections: StudySection[];
  definitions: StudyDefinition[];
  quizQuestions: StudyQuizQuestion[];
  flashcards: StudyFlashcard[];
  speakerLabels: string[];
  chapterCandidates: string[];
  chatReady: boolean;
};

const STOPWORDS = new Set([
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
]);

function normalizeText(text: string) {
  return (text || "").replace(/\r\n?/g, "\n").trim();
}

function splitSentences(text: string) {
  const cleaned = normalizeText(text);
  if (!cleaned) return [] as string[];
  const sentences = cleaned
    .split(/(?<=[.!?])\s+/)
    .map((part) => part.trim())
    .filter(Boolean);
  if (sentences.length > 1) return sentences;
  return cleaned
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function splitParagraphs(text: string) {
  return normalizeText(text)
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .filter(Boolean);
}

function normalizeWords(text: string) {
  return (text.match(/[A-Za-z][A-Za-z0-9_'-]+/g) || [])
    .map((word) => word.toLowerCase())
    .filter((word) => word.length > 2 && !STOPWORDS.has(word));
}

function topKeywords(text: string, limit = 8) {
  const counts = new Map<string, number>();
  for (const word of normalizeWords(text)) {
    counts.set(word, (counts.get(word) || 0) + 1);
  }
  return Array.from(counts.entries())
    .sort((left, right) => right[1] - left[1])
    .slice(0, limit)
    .map(([word]) => word.replace(/_/g, " "));
}

function titleCaseKeyword(keyword: string) {
  return keyword
    .split(" ")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function truncate(text: string, maxLength: number) {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1).trimEnd()}...`;
}

function detectSpeakerLabels(transcript: string) {
  const labels: string[] = [];
  for (const line of normalizeText(transcript).split("\n")) {
    const match = line.match(/^\s*([A-Za-z][A-Za-z0-9 _-]{0,24}?)(?:\s*[:\-])\s+/);
    if (!match) continue;
    const candidate = match[1].trim();
    if (candidate && !labels.some((label) => label.toLowerCase() === candidate.toLowerCase())) {
      labels.push(candidate);
    }
  }
  if (labels.length > 0) return labels.slice(0, 4);
  if (splitParagraphs(transcript).length > 1) return ["Speaker 1", "Speaker 2"];
  return ["Speaker 1"];
}

function extractDefinitions(sentences: string[], keywords: string[]) {
  const definitions: StudyDefinition[] = [];
  for (const sentence of sentences) {
    if (definitions.length >= 5) break;
    const match = sentence.match(/^([A-Za-z][A-Za-z0-9 _-]{2,60}?)\s+(?:is|are|means|refers to|describes)\s+(.*)$/i);
    if (!match) continue;
    const term = truncate(titleCaseKeyword(match[1].trim()), 48);
    const definition = truncate(match[2].trim().replace(/[.]+$/, ""), 180);
    if (term && definition) {
      definitions.push({ term, definition });
    }
  }

  for (const keyword of keywords) {
    if (definitions.length >= 5) break;
    const term = titleCaseKeyword(keyword);
    if (definitions.some((item) => item.term.toLowerCase() === term.toLowerCase())) continue;
    definitions.push({ term, definition: `A core concept discussed in the lecture: ${term}.` });
  }

  return definitions.slice(0, 5);
}

function buildSections(sentences: string[], chapterCandidates: string[], style: StudyStyle): StudySection[] {
  const sectionCount = style === "mind_map" ? 5 : style === "executive_brief" ? 3 : style === "research_abstract" ? 4 : 4;
  const headings = chapterCandidates.slice(0, sectionCount);
  const fallbackHeadings = ["Overview", "Key Ideas", "Examples and Applications", "Revision Notes", "Implications"];
  const finalHeadings = headings.length > 0 ? headings : fallbackHeadings.slice(0, sectionCount);

  if (sentences.length === 0) {
    return finalHeadings.map((heading) => ({ heading, content: "No transcript content was provided.", keyPoints: [] }));
  }

  const chunkSize = Math.max(1, Math.floor(sentences.length / Math.max(1, finalHeadings.length)));
  return finalHeadings.map((heading, index) => {
    const start = index * chunkSize;
    const end = index === finalHeadings.length - 1 ? sentences.length : Math.min(sentences.length, (index + 1) * chunkSize);
    const chunk = sentences.slice(start, end).length > 0 ? sentences.slice(start, end) : sentences.slice(-chunkSize);
    return {
      heading,
      content: chunk.join(" ").trim(),
      keyPoints: chunk.slice(0, 3).map((sentence) => truncate(sentence, 120)),
    };
  });
}

function buildQuizQuestions(keywords: string[], definitions: StudyDefinition[], title: string) {
  const distractors = keywords.slice(1, 4).map((keyword) => titleCaseKeyword(keyword));
  const questions: StudyQuizQuestion[] = [];

  for (const definition of definitions.slice(0, 4)) {
    const correct = definition.term;
    const options = [correct];
    for (const distractor of distractors) {
      if (distractor.toLowerCase() !== correct.toLowerCase() && !options.includes(distractor)) {
        options.push(distractor);
      }
    }
    while (options.length < 4) {
      options.push(`Option ${options.length + 1}`);
    }
    questions.push({
      question: `What best describes ${correct}?`,
      options: options.slice(0, 4),
      answerIndex: 0,
      explanation: definition.definition,
    });
  }

  if (questions.length === 0 && keywords.length > 0) {
    const options = keywords.slice(0, 4).map((keyword) => titleCaseKeyword(keyword));
    while (options.length < 4) {
      options.push(`Option ${options.length + 1}`);
    }
    questions.push({
      question: `Which topic was emphasized most in ${title}?`,
      options,
      answerIndex: 0,
      explanation: `The lecture centered on ${titleCaseKeyword(keywords[0])}.`,
    });
  }

  return questions.slice(0, 5);
}

function buildFlashcards(definitions: StudyDefinition[], keywords: string[], title: string) {
  const flashcards: StudyFlashcard[] = definitions.slice(0, 5).map((definition) => ({
    front: definition.term,
    back: definition.definition,
    tags: [title],
  }));

  for (const keyword of keywords.slice(0, 3)) {
    flashcards.push({
      front: `Why is ${keyword} important?`,
      back: `${titleCaseKeyword(keyword)} is one of the recurring ideas in the transcript.`,
      tags: [title, "quiz"],
    });
  }

  return flashcards.slice(0, 8);
}

function buildTldr(sentences: string[], keywords: string[], style: StudyStyle) {
  if (sentences.length === 0) return "No transcript was provided.";
  if (style === "executive_brief") {
    return truncate(sentences.slice(0, 2).join(" "), 180);
  }
  if (keywords.length > 0) {
    return truncate(`The lecture focuses on ${keywords.slice(0, 3).join(", ")}.`, 180);
  }
  return truncate(sentences.slice(0, 2).join(" "), 200);
}

function buildMarkdown(
  title: string,
  tldr: string,
  sections: StudySection[],
  definitions: StudyDefinition[],
  quizQuestions: StudyQuizQuestion[],
  flashcards: StudyFlashcard[],
  style: StudyStyle,
  outputLanguage: string,
  speakerLabels: string[],
) {
  const lines: string[] = [
    `# ${title}`,
    "",
    `**Style:** ${style.replace(/_/g, " ")}`,
    `**Output language:** ${outputLanguage}`,
    "",
    "## Quick Revision",
    tldr,
    "",
  ];

  if (speakerLabels.length > 0) {
    lines.push("## Speaker Notes", speakerLabels.join(", "), "");
  }

  for (const section of sections) {
    lines.push(`## ${section.heading}`);
    if (section.content) {
      lines.push(section.content);
    }
    if (section.keyPoints.length > 0) {
      lines.push("");
      for (const point of section.keyPoints) {
        lines.push(`- ${point}`);
      }
    }
    lines.push("");
  }

  if (definitions.length > 0) {
    lines.push("## Definitions", "");
    for (const definition of definitions) {
      lines.push(`- **${definition.term}**: ${definition.definition}`);
    }
    lines.push("");
  }

  if (quizQuestions.length > 0) {
    lines.push("## Quiz Questions", "");
    quizQuestions.forEach((question, index) => {
      lines.push(`${index + 1}. ${question.question}`);
      question.options.forEach((option) => lines.push(`   - ${option}`));
      lines.push("");
    });
  }

  if (flashcards.length > 0) {
    lines.push("## Flashcards", "");
    flashcards.forEach((card) => {
      lines.push(`- **${card.front}** -> ${card.back}`);
    });
    lines.push("");
  }

  return `${lines.filter(Boolean).join("\n")}\n`;
}

export function buildStudyPack(input: {
  transcript: string;
  notesMarkdown?: string;
  chapters?: string[];
  style?: StudyStyle;
  outputLanguage?: string;
  sourceTitle?: string;
  sourceUrl?: string;
}) : StudyPack {
  const transcript = normalizeText(input.transcript);
  const sentences = splitSentences(transcript);
  const keywords = topKeywords(transcript);
  const style = input.style || "student_notes";
  const outputLanguage = input.outputLanguage || "en";
  const title = input.sourceTitle || (keywords[0] ? titleCaseKeyword(keywords[0]) : "AI Video Lecture Notes");
  const speakerLabels = detectSpeakerLabels(transcript);
  const sections = buildSections(sentences, input.chapters || [], style);
  const definitions = extractDefinitions(sentences, keywords);
  const tldr = buildTldr(sentences, keywords, style);
  const quizQuestions = buildQuizQuestions(keywords, definitions, title);
  const flashcards = buildFlashcards(definitions, keywords, title);
  const notesMarkdown = (input.notesMarkdown && input.notesMarkdown.trim().length > 0)
    ? `${input.notesMarkdown.trim()}\n`
    : buildMarkdown(title, tldr, sections, definitions, quizQuestions, flashcards, style, outputLanguage, speakerLabels);

  const chapterCandidates = (input.chapters && input.chapters.length > 0)
    ? input.chapters
    : sections.map((section) => section.heading);

  return {
    title,
    style,
    outputLanguage,
    notesMarkdown,
    tldr,
    keyConcepts: keywords.slice(0, 8),
    sections,
    definitions,
    quizQuestions,
    flashcards,
    speakerLabels,
    chapterCandidates,
    chatReady: true,
  };
}

export function buildChatAnswer(question: string, transcript: string, notesMarkdown = "", sections: StudySection[] = []): { answer: string; citations: StudyCitation[] } {
  const questionWords = new Set(normalizeWords(question));
  const chunks: StudyCitation[] = [];

  splitSentences(transcript).forEach((sentence, index) => {
    chunks.push({ source: "transcript", index, text: sentence });
  });
  splitSentences(notesMarkdown).forEach((sentence, index) => {
    chunks.push({ source: "notes", index, text: sentence });
  });
  sections.forEach((section, index) => {
    if (section.content) {
      chunks.push({ source: "section", index, text: `${section.heading}: ${section.content}` });
    }
  });

  const scored = chunks
    .map((chunk) => {
      const words = new Set(normalizeWords(chunk.text));
      const overlap = Array.from(questionWords).filter((word) => words.has(word)).length;
      return { score: overlap + overlap / Math.max(1, questionWords.size), chunk };
    })
    .sort((left, right) => right.score - left.score)
    .filter((item) => item.score > 0);

  const topChunks = scored.slice(0, 3).map((item) => item.chunk);
  const selected = topChunks.length > 0 ? topChunks : chunks.slice(0, 2);
  const answerBody = selected.map((chunk) => chunk.text).join(" ").trim();
  const answer = answerBody
    ? `Based on the transcript, ${answerBody.charAt(0).toLowerCase()}${answerBody.slice(1)}`
    : "I could not find a direct match in the transcript, but the notes suggest the topic is covered in the summary.";

  return {
    answer: truncate(answer, 360),
    citations: selected.map((chunk) => ({
      source: chunk.source,
      index: chunk.index,
      text: truncate(chunk.text, 220),
    })),
  };
}

export function buildNotionExport(pack: StudyPack) {
  return {
    title: pack.title,
    language: pack.outputLanguage,
    content: pack.notesMarkdown,
    blocks: pack.sections,
  };
}

export function buildGoogleDocsExport(pack: StudyPack) {
  return {
    title: pack.title,
    language: pack.outputLanguage,
    documentText: pack.notesMarkdown,
    outline: pack.sections.map((section) => section.heading),
  };
}

export function buildObsidianMarkdown(pack: StudyPack, sourceUrl = "") {
  const frontMatter = [
    "---",
    `title: ${pack.title}`,
    `style: ${pack.style}`,
    `language: ${pack.outputLanguage}`,
    `source: ${sourceUrl ? JSON.stringify(sourceUrl) : '""'}`,
    "---",
    "",
  ];
  return `${frontMatter.join("\n")}${pack.notesMarkdown}`;
}
