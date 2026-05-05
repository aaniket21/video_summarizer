/* eslint-disable @typescript-eslint/no-explicit-any */
import { NextResponse } from "next/server";
import { GoogleGenerativeAI } from "@google/generative-ai";

const GEMINI_MODEL = process.env.GEMINI_MODEL || "gemini-3-flash-preview";

function sanitize(text: string) {
  return text.replace(/\r\n/g, "\n").trim();
}

function extractTitleFromMarkdown(md: string): string {
  const m = md.match(/^#\s+(.*)$/m);
  if (m?.[1]) return m[1].trim();
  // Fallback: first non-empty line
  const first = md
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.length > 0);
  return first || "AI Video Lecture Notes";
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const transcript = sanitize(String(body?.transcript || ""));
    const chapters = Array.isArray(body?.chapters) ? body.chapters : [];

    if (!process.env.GEMINI_API_KEY) {
      return NextResponse.json(
        { error: "GEMINI_API_KEY is not configured on the server." },
        { status: 500 },
      );
    }
    if (!transcript) {
      return NextResponse.json(
        { error: "Missing transcript." },
        { status: 400 },
      );
    }

    const chapterText = chapters?.length
      ? chapters.map((c: string) => `- ${c}`).join("\n")
      : "- No strong chapter splits found";

    const prompt = `
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
${chapterText}

Transcript:
${transcript}
`.trim();

    const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
    const model = genAI.getGenerativeModel({ model: GEMINI_MODEL });

    const result = await model.generateContent(prompt);
    const markdown = sanitize(result?.response?.text?.() || "");
    if (!markdown) {
      return NextResponse.json(
        { error: "Gemini returned empty notes." },
        { status: 500 },
      );
    }

    const title = extractTitleFromMarkdown(markdown);
    return NextResponse.json({ title, notesMarkdown: markdown });
  } catch (e: any) {
    return NextResponse.json(
      { error: e?.message ? String(e.message) : "Failed to generate notes." },
      { status: 500 },
    );
  }
}

