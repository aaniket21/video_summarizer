/* eslint-disable @typescript-eslint/no-explicit-any */
import { PDFDocument, StandardFonts, rgb } from "pdf-lib";

type Block =
  | { type: "h"; level: 1 | 2 | 3; text: string }
  | { type: "p"; text: string }
  | { type: "bullet"; text: string }
  | { type: "numbered"; idx: number; text: string }
  | { type: "code"; text: string }
  | { type: "divider" };

function wrapText(args: {
  text: string;
  font: any;
  fontSize: number;
  maxWidth: number;
}): string[] {
  const { text, font, fontSize, maxWidth } = args;
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let line = "";

  for (const w of words) {
    const next = line ? `${line} ${w}` : w;
    const width = font.widthOfTextAtSize(next, fontSize);
    if (width <= maxWidth) {
      line = next;
    } else {
      if (line) lines.push(line);
      // If a single word is too long, hard-break it.
      if (font.widthOfTextAtSize(w, fontSize) > maxWidth) {
        let chunk = "";
        for (const ch of w) {
          const nextChunk = chunk + ch;
          const chunkWidth = font.widthOfTextAtSize(nextChunk, fontSize);
          if (chunkWidth <= maxWidth) chunk = nextChunk;
          else {
            if (chunk) lines.push(chunk);
            chunk = ch;
          }
        }
        if (chunk) lines.push(chunk);
        line = "";
      } else {
        line = w;
      }
    }
  }
  if (line) lines.push(line);
  return lines;
}

function parseMarkdownToBlocks(md: string): Block[] {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];

  let inCode = false;
  let codeLines: string[] = [];

  let paragraphLines: string[] = [];

  function flushParagraph() {
    const text = paragraphLines.join(" ").trim();
    if (text) blocks.push({ type: "p", text });
    paragraphLines = [];
  }

  for (const raw of lines) {
    const line = raw.trimEnd();

    if (line.startsWith("```")) {
      if (inCode) {
        blocks.push({ type: "code", text: codeLines.join("\n") });
        codeLines = [];
        inCode = false;
      } else {
        flushParagraph();
        inCode = true;
      }
      continue;
    }

    if (inCode) {
      codeLines.push(raw);
      continue;
    }

    const divider = line === "---" || line === "***";
    if (divider) {
      flushParagraph();
      blocks.push({ type: "divider" });
      continue;
    }

    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      flushParagraph();
      const level = Math.min(h[1].length, 3) as 1 | 2 | 3;
      blocks.push({ type: "h", level, text: h[2].trim() });
      continue;
    }

    const bullet = line.match(/^[-*+]\s+(.*)$/);
    if (bullet) {
      flushParagraph();
      blocks.push({ type: "bullet", text: bullet[1].trim() });
      continue;
    }

    const numbered = line.match(/^(\d+)[.)]\s+(.*)$/);
    if (numbered) {
      flushParagraph();
      blocks.push({
        type: "numbered",
        idx: Number(numbered[1]),
        text: numbered[2].trim(),
      });
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      continue;
    }

    paragraphLines.push(line.trim());
  }

  if (inCode) {
    blocks.push({ type: "code", text: codeLines.join("\n") });
  }
  flushParagraph();
  return blocks;
}

export async function generatePdfFromMarkdown(args: {
  title: string;
  markdown: string;
  branding?: {
    brandName?: string;
    accentColor?: string;
    footerText?: string;
  };
}): Promise<Uint8Array> {
  const { title, markdown, branding } = args;
  const doc = await PDFDocument.create();

  const pageWidth = 595.28; // A4
  const pageHeight = 841.89;
  const marginX = 48;
  const marginTop = 64;
  const marginBottom = 56;

  let page = doc.addPage([pageWidth, pageHeight]);

  const helv = await doc.embedFont(StandardFonts.Helvetica);
  const helvBold = await doc.embedFont(StandardFonts.HelveticaBold);
  const courier = await doc.embedFont(StandardFonts.Courier);

  const defaultAccent = rgb(0, 0.58, 0.52);
  const textColor = rgb(0.1, 0.16, 0.28);
  const accentColor = branding?.accentColor
    ? (() => {
        const hex = branding.accentColor.trim().replace("#", "");
        if (hex.length === 6) {
          const r = parseInt(hex.slice(0, 2), 16) / 255;
          const g = parseInt(hex.slice(2, 4), 16) / 255;
          const b = parseInt(hex.slice(4, 6), 16) / 255;
          if (!Number.isNaN(r) && !Number.isNaN(g) && !Number.isNaN(b)) {
            return rgb(r, g, b);
          }
        }
        return defaultAccent;
      })()
    : defaultAccent;

  const maxWidth = pageWidth - marginX * 2;
  let y = pageHeight - marginBottom;

  function ensureSpace(heightNeeded: number) {
    if (y - heightNeeded < marginTop) {
      page = doc.addPage([pageWidth, pageHeight]);
      y = pageHeight - marginBottom;
    }
  }

  // Header
  ensureSpace(60);
  y -= 8;
  page.drawText(title, {
    x: marginX,
    y,
    size: 20,
    font: helvBold,
    color: accentColor,
  });
  y -= 26;
  page.drawText(branding?.brandName || "AI Video Lecture Notes", {
    x: marginX,
    y,
    size: 11,
    font: helv,
    color: textColor,
  });
  y -= 20;

  const blocks = parseMarkdownToBlocks(markdown);

  for (const b of blocks) {
    if (b.type === "divider") {
      ensureSpace(18);
      y -= 8;
      // subtle divider line
      page.drawLine({
        start: { x: marginX, y },
        end: { x: marginX + maxWidth, y },
        thickness: 1,
        color: rgb(0.2, 0.3, 0.45),
      });
      y -= 18;
      continue;
    }

    if (b.type === "h") {
      const fontSize = b.level === 1 ? 18 : b.level === 2 ? 14 : 12;
      const leading = fontSize + 6;
      const lines = wrapText({
        text: b.text,
        font: b.level === 1 ? helvBold : helvBold,
        fontSize,
        maxWidth,
      });
      const height = leading * Math.max(1, lines.length);
      ensureSpace(height + 10);

      y -= 2;
      for (const line of lines) {
        page.drawText(line, {
          x: marginX,
          y,
          size: fontSize,
          font: helvBold,
          color: rgb(0.04, 0.2, 0.28),
        });
        y -= leading;
      }
      y -= 4;
      continue;
    }

    if (b.type === "p") {
      const fontSize = 11;
      const leading = 15;
      const lines = wrapText({
        text: b.text,
        font: helv,
        fontSize,
        maxWidth,
      });
      const height = leading * lines.length;
      ensureSpace(height + 8);

      for (const line of lines) {
        page.drawText(line, {
          x: marginX,
          y,
          size: fontSize,
          font: helv,
          color: textColor,
        });
        y -= leading;
      }
      y -= 6;
      continue;
    }

    if (b.type === "bullet" || b.type === "numbered") {
      const fontSize = 11;
      const leading = 15;
      const bulletPrefix = b.type === "bullet" ? "•" : `${b.idx}.`;
      const indent = 18;

      const contentLines = wrapText({
        text: b.text,
        font: helv,
        fontSize,
        maxWidth: maxWidth - indent,
      });

      const height = leading * contentLines.length;
      ensureSpace(height + 6);

      // bullet on first line
      page.drawText(bulletPrefix, {
        x: marginX,
        y,
        size: fontSize,
        font: helv,
        color: teal,
      });
      // first line of content
      if (contentLines.length > 0) {
        page.drawText(contentLines[0], {
          x: marginX + indent,
          y,
          size: fontSize,
          font: helv,
          color: textColor,
        });
      }
      y -= leading;
      for (let i = 1; i < contentLines.length; i++) {
        page.drawText(contentLines[i], {
          x: marginX + indent,
          y,
          size: fontSize,
          font: helv,
          color: textColor,
        });
        y -= leading;
      }
      y -= 6;
      continue;
    }

    if (b.type === "code") {
      const fontSize = 9;
      const leading = 12;
      const codeLines = b.text.split("\n");
      const height = leading * codeLines.length;
      ensureSpace(height + 10);
      // background
      page.drawRectangle({
        x: marginX - 2,
        y: y - height - 2,
        width: maxWidth + 4,
        height: height + 6,
        color: rgb(0.95, 0.97, 1),
        borderColor: rgb(0.8, 0.88, 0.95),
        borderWidth: 0.5,
      });

      let localY = y;
      for (const cl of codeLines) {
        const lines = wrapText({
          text: cl || " ",
          font: courier,
          fontSize,
          maxWidth,
        });
        for (const wrapped of lines) {
          page.drawText(wrapped, {
            x: marginX + 6,
            y: localY,
            size: fontSize,
            font: courier,
            color: rgb(0.06, 0.1, 0.18),
          });
          localY -= leading;
        }
      }
      y = localY - 6;
      continue;
    }
  }

  if (branding?.footerText) {
    const footerPage = doc.getPages()[doc.getPages().length - 1];
    footerPage.drawText(branding.footerText, {
      x: marginX,
      y: marginBottom - 24,
      size: 9,
      font: helv,
      color: rgb(0.35, 0.42, 0.52),
    });
  }

  const bytes = await doc.save();
  return new Uint8Array(bytes);
}

