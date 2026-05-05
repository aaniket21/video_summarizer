/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import React, { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { useSummarizerStore } from "@/store/useSummarizerStore";
import { loadHistoryFromLocalStorage, loadHistoryItem, saveHistoryItem } from "@/lib/storage";
import { generatePdfFromMarkdown } from "@/lib/pdf";
import type { JobInput, JobStep } from "@/store/useSummarizerStore";

const STEPS: { key: JobStep; label: string }[] = [
  { key: "download", label: "Download" },
  { key: "audio_extraction", label: "Audio Extraction" },
  { key: "transcription", label: "Transcription" },
  { key: "notes_generation", label: "Notes Generation" },
  { key: "pdf_export", label: "PDF Export" },
];

const MAX_VIDEO_BYTES = 200 * 1024 * 1024; // 200MB (practical in-browser FFmpeg limit)

function uid() {
  return Math.random().toString(16).slice(2) + Date.now().toString(16);
}

function base64ToArrayBuffer(b64: string): ArrayBuffer {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

function extractChapters(transcript: string): string[] {
  // Keep it simple (desktop version is also heuristic).
  const lines = transcript.split(". ").map((s) => s.trim());
  return lines.filter((l) => l.length > 60).slice(0, 10);
}

function getStepIndex(step: JobStep) {
  return STEPS.findIndex((s) => s.key === step);
}

function mapWorkerProgressToOverall(step: JobStep, workerProgress0to100: number) {
  // Overall mapping per step.
  const idx = getStepIndex(step);
  if (idx < 0) return workerProgress0to100;
  const base = idx * 20; // 0,20,40,60,80
  const range = 20;
  return Math.min(100, base + Math.round((workerProgress0to100 / 100) * range));
}

export default function Home() {
  const [jobFromShareId, setJobFromShareId] = useState<string | null>(null);
  const {
    job,
    history,
    theme,
    setTheme,
    setJob,
    setStatus,
    setStep,
    setProgress,
    appendLog,
    setError,
    setTranscript,
    setTitle,
    setNotesMarkdown,
    setHistory,
    upsertHistoryItem,
  } = useSummarizerStore();

  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const cancelledRef = useRef(false);

  const workerRefs = useRef<{ ffmpeg?: Worker; whisper?: Worker }>({});

  useEffect(() => {
    const saved = typeof window !== "undefined" ? localStorage.getItem("aitv_theme_v1") : null;
    const initial: "light" | "dark" =
      saved === "light" || saved === "dark"
        ? (saved as "light" | "dark")
        : window.matchMedia?.("(prefers-color-scheme: dark)")?.matches
          ? "dark"
          : "light";
    setTheme(initial);
  }, [setTheme]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("aitv_theme_v1", theme);
  }, [theme]);

  useEffect(() => {
    setHistory(loadHistoryFromLocalStorage());
  }, [setHistory]);

  useEffect(() => {
    try {
      const id = new URL(window.location.href).searchParams.get("job");
      setJobFromShareId(id ? String(id) : null);
    } catch {
      setJobFromShareId(null);
    }
  }, []);

  useEffect(() => {
    if (!jobFromShareId) return;
    const item = loadHistoryItem(jobFromShareId);
    if (!item) return;

    setJob({
      id: item.id,
      createdAt: item.createdAt,
      input: { kind: "url", source: item.source },
      status: "completed",
      step: "pdf_export",
      progress: 100,
      logs: ["Loaded shared history from local storage."],
      transcript: item.transcript,
      title: item.title,
      notesMarkdown: item.notesMarkdown,
    });
    setPdfUrl(null);
  }, [jobFromShareId, setJob]);

  useEffect(() => {
    return () => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    };
  }, [pdfUrl]);

  function resetOutput() {
    setPdfLoading(false);
    if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    setPdfUrl(null);
    setTranscript("");
    setTitle("");
    setNotesMarkdown("");
    setError("");
    setProgress(0);
  }

  function cancelProcessing() {
    cancelledRef.current = true;
    abortRef.current?.abort();
    abortRef.current = null;

    try {
      workerRefs.current.ffmpeg?.terminate();
      workerRefs.current.whisper?.terminate();
    } catch {
      // ignore
    }
    workerRefs.current = {};

    setStatus("cancelled");
    appendLog("Cancelled by user.");
  }

  function getFFmpegWorker() {
    const w = new Worker(new URL("../workers/ffmpegWorker.ts", import.meta.url), { type: "module" });
    workerRefs.current.ffmpeg = w;
    return w;
  }

  function getWhisperWorker() {
    const w = new Worker(new URL("../workers/whisperWorker.ts", import.meta.url), { type: "module" });
    workerRefs.current.whisper = w;
    return w;
  }

  async function runFfmpegExtract(videoBytes: ArrayBuffer) {
    return await new Promise<ArrayBuffer>((resolve, reject) => {
      const w = getFFmpegWorker();

      w.onmessage = (ev) => {
        const data: any = ev.data;
        if (!data) return;
        if (data.type === "log") appendLog(`[ffmpeg] ${data.message}`);
        if (data.type === "progress") setProgress(mapWorkerProgressToOverall("audio_extraction", data.progress));
        if (data.type === "audio") resolve(data.audioWav as ArrayBuffer);
        if (data.type === "error") reject(new Error(data.message || "FFmpeg worker error"));
      };
      w.onerror = () => reject(new Error("FFmpeg worker crashed"));

      w.postMessage({ type: "extract-audio", videoBytes }, [videoBytes]);
    });
  }

  async function runWhisperTranscribe(audioWav: ArrayBuffer) {
    return await new Promise<string>((resolve, reject) => {
      const w = getWhisperWorker();
      w.onmessage = (ev) => {
        const data: any = ev.data;
        if (!data) return;
        if (data.type === "log") appendLog(`[whisper] ${data.message}`);
        if (data.type === "progress") setProgress(mapWorkerProgressToOverall("transcription", data.progress));
        if (data.type === "transcription") resolve(String(data.transcript || ""));
        if (data.type === "error") reject(new Error(data.message || "Whisper worker error"));
      };
      w.onerror = () => reject(new Error("Whisper worker crashed"));
      w.postMessage({ type: "transcribe", audioWav }, [audioWav]);
    });
  }

  async function runClientOrServerAudioFromUrl(url: string): Promise<{ audioWav: ArrayBuffer }> {
    // Try client-side download first; if blocked, use server fallback for extracted WAV.
    setStep("download");
    setProgress(8);
    appendLog("Attempting client-side download (may be blocked by CORS).");

    try {
      const controller = new AbortController();
      abortRef.current = controller;
      const res = await fetch(url, { signal: controller.signal });
      if (!res.ok) throw new Error(`Download failed (${res.status})`);

      const contentLength = Number(res.headers.get("content-length") || "0");
      if (contentLength && contentLength > MAX_VIDEO_BYTES) {
        throw new Error(`Video too large for client FFmpeg (${Math.round(contentLength / (1024 * 1024))}MB).`);
      }

      const bytes = await res.arrayBuffer();
      if (cancelledRef.current) throw new Error("cancelled");

      // Heuristic: if this is already WAV (server fallback), we will skip FFmpeg.
      const header = new TextDecoder().decode(new Uint8Array(bytes.slice(0, 4)));
      if (header === "RIFF") {
        setStep("audio_extraction");
        setProgress(20);
        return { audioWav: bytes };
      }

      appendLog("Client download succeeded. Extracting audio with FFmpeg WASM...");
      setStep("audio_extraction");
      setProgress(20);
      const audioWav = await runFfmpegExtract(bytes);
      return { audioWav };
    } catch (e: any) {
      if (cancelledRef.current) throw e;
      appendLog(`Client download unavailable: ${e?.message || String(e)}.`);
      appendLog("Using server-side audio extraction.");

      const controller = new AbortController();
      abortRef.current = controller;
      const resp = await fetch("/api/download-audio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({ url }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => null);
        throw new Error(err?.error || `Server download failed (${resp.status})`);
      }
      const data = (await resp.json()) as { audioWavBase64: string };
      setStep("audio_extraction");
      setProgress(20);
      return { audioWav: base64ToArrayBuffer(data.audioWavBase64) };
    }
  }

  async function processJob(input: JobInput) {
    const jobId = uid();
    cancelledRef.current = false;
    setPdfLoading(false);
    setPdfUrl(null);
    setError("");

    resetOutput();

    const initSnapshot = {
      id: jobId,
      createdAt: Date.now(),
      input,
      status: "running" as const,
      step: "download" as JobStep,
      progress: 0,
      logs: ["Starting pipeline..."],
      transcript: "",
      title: "",
      notesMarkdown: "",
    };

    setJob(initSnapshot);
    setStatus("running");

    try {
      let audioWavBytes: ArrayBuffer;

      // Download / ingest
      if (input.kind === "file") {
        if (!file) throw new Error("No file selected.");
        if (file.size > MAX_VIDEO_BYTES) {
          throw new Error(
            `Video is too large (${Math.round(file.size / (1024 * 1024))}MB). Try a smaller file or use URL with server fallback.`,
          );
        }
        appendLog("Video file ready in browser. Extracting audio with FFmpeg WASM...");
        setStep("audio_extraction");
        setProgress(20);
        const videoBytes = await file.arrayBuffer();
        audioWavBytes = await runFfmpegExtract(videoBytes);
      } else {
        const res = await runClientOrServerAudioFromUrl(input.source);
        setStep("transcription");
        setProgress(45);
        audioWavBytes = res.audioWav;
      }

      if (cancelledRef.current) return;

      // Transcription
      setStep("transcription");
      setProgress(50);
      appendLog("Transcribing with Whisper in a Web Worker...");
      const transcriptText = await runWhisperTranscribe(audioWavBytes);
      if (cancelledRef.current) return;
      setTranscript(transcriptText);
      appendLog(`Transcription finished (${transcriptText.length} chars).`);

      // Gemini notes
      setStep("notes_generation");
      setProgress(75);
      appendLog("Generating structured notes with Gemini...");

      const chapters = extractChapters(transcriptText);
      const resp = await fetch("/api/generate-notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript: transcriptText, chapters }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => null);
        throw new Error(err?.error || `Gemini failed (${resp.status})`);
      }
      const data = (await resp.json()) as { title: string; notesMarkdown: string };
      setTitle(data.title || "AI Video Lecture Notes");
      setNotesMarkdown(data.notesMarkdown || "");
      appendLog("Notes generation finished.");

      if (cancelledRef.current) return;

      // PDF export
      setStep("pdf_export");
      setProgress(92);
      setPdfLoading(true);
      appendLog("Exporting PDF...");

      const finalTitle = data.title || "AI Video Lecture Notes";
      const pdfBytes = await generatePdfFromMarkdown({
        title: finalTitle,
        markdown: data.notesMarkdown || "",
      });
      const pdfArrayBuffer = (pdfBytes.buffer as ArrayBuffer).slice(
        pdfBytes.byteOffset,
        pdfBytes.byteOffset + pdfBytes.byteLength,
      );
      const blob = new Blob([pdfArrayBuffer], { type: "application/pdf" });
      const nextPdfUrl = URL.createObjectURL(blob);
      setPdfUrl(nextPdfUrl);
      setProgress(100);
      setPdfLoading(false);

      // Save history
      const historyItem = {
        id: jobId,
        createdAt: Date.now(),
        title: finalTitle,
        source: input.kind === "url" ? input.source : file?.name || "local-file",
        transcript: transcriptText,
        notesMarkdown: data.notesMarkdown || "",
      };
      upsertHistoryItem(historyItem);
      saveHistoryItem(historyItem);
      setHistory(loadHistoryFromLocalStorage());

      appendLog("All steps completed successfully.");
      setStatus("completed");

      // Share link feature: job id in URL (loads from local storage only).
      try {
        const nextUrl = new URL(window.location.href);
        nextUrl.searchParams.set("job", jobId);
        window.history.replaceState({}, "", nextUrl.toString());
      } catch {
        // ignore
      }
    } catch (e: any) {
      if (cancelledRef.current) return;
      setError(e?.message ? String(e.message) : "Processing failed.");
      setStatus("error");
      appendLog(`Error: ${e?.message || String(e)}`);
    } finally {
      setPdfLoading(false);
      try {
        workerRefs.current.ffmpeg?.terminate();
        workerRefs.current.whisper?.terminate();
      } catch {
        // ignore
      }
      workerRefs.current = {};
      abortRef.current = null;
    }
  }

  const canStart = Boolean((url.trim().length > 0 && !file) || (file !== null && url.trim().length === 0));

  const notesMarkdown = job?.notesMarkdown || "";
  const transcriptText = job?.transcript || "";
  const title = job?.title || "AI Video Lecture Notes";

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-black dark:text-slate-50">
      <header className="sticky top-0 z-40 backdrop-blur bg-white/70 dark:bg-black/60 border-b border-[var(--border)]">
        <div className="mx-auto max-w-7xl px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl card card-dark flex items-center justify-center">
              <div className="w-2.5 h-2.5 rounded-full bg-teal-500" />
            </div>
            <div>
              <div className="font-semibold leading-tight">AI Video Lecture Summarizer</div>
              <div className="text-xs text-[var(--muted)]">Client-first processing with Web Workers</div>
            </div>
          </div>
          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            className="px-3 py-2 rounded-xl border border-[var(--border)] bg-[var(--card)] hover:bg-white/20 dark:hover:bg-white/10 transition text-sm"
            aria-label="Toggle theme"
          >
            {theme === "dark" ? "Light" : "Dark"} mode
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-5 py-8">
        <motion.section
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="card rounded-2xl p-7 card-dark"
        >
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div>
              <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight">
                Convert videos into structured study notes.
              </h1>
              <p className="mt-2 text-[var(--muted)] max-w-2xl">
                Paste a link or upload a video file. We extract audio in your browser (FFmpeg WASM), transcribe with
                Whisper (WASM), then generate clean markdown notes and a downloadable PDF.
              </p>
            </div>
          </div>
        </motion.section>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mt-6">
          <div className="lg:col-span-7 space-y-6">
            <motion.section
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35 }}
              className="card rounded-2xl p-6"
            >
              <h2 className="font-semibold text-lg">Input</h2>
              <p className="text-sm text-[var(--muted)] mt-1">
                Use either a URL or a video file. Drag-and-drop is supported.
              </p>

              <div className="mt-5 grid grid-cols-1 gap-4">
                <label className="block">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Video URL</span>
                    <span className="text-xs text-[var(--muted)]">Server fallback for blocked sources</span>
                  </div>
                  <textarea
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="Paste a YouTube link or any supported video URL..."
                    rows={3}
                    className="mt-2 w-full rounded-xl border border-[var(--border)] bg-transparent px-4 py-3 outline-none focus:ring-2 focus:ring-teal-500/30"
                  />
                </label>

                <div
                  className={`rounded-2xl border-2 transition px-4 py-4 ${
                    isDragging ? "border-teal-500/70 bg-teal-500/5" : "border-[var(--border)] bg-transparent"
                  }`}
                  onDragEnter={(e) => {
                    e.preventDefault();
                    setIsDragging(true);
                  }}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setIsDragging(true);
                  }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setIsDragging(false);
                    const dropped = e.dataTransfer.files?.[0];
                    if (dropped) {
                      setFile(dropped);
                      setUrl("");
                      appendLog(`Added file: ${dropped.name}`);
                    }
                  }}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-sm font-medium">Upload video</div>
                      <div className="text-xs text-[var(--muted)] mt-1">
                        Default browser FFmpeg limit is ~200MB. For larger videos, use URL + server fallback.
                      </div>
                    </div>
                    <div className="text-xs text-[var(--muted)]">
                      {file ? `${Math.round(file.size / (1024 * 1024))}MB` : "Drag & drop here"}
                    </div>
                  </div>

                  <div className="mt-3">
                    <input
                      type="file"
                      accept="video/*"
                      className="block w-full text-sm file:mr-4 file:rounded-xl file:border-0 file:bg-teal-500/15 file:px-3 file:py-2 file:text-teal-500 hover:file:bg-teal-500/25"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (!f) return;
                        setFile(f);
                        setUrl("");
                        appendLog(`Added file: ${f.name}`);
                      }}
                    />
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3 pt-2">
                  <button
                    disabled={!canStart || job?.status === "running"}
                    onClick={() => {
                      const urlInput = url.trim();
                      if (urlInput) processJob({ kind: "url", source: urlInput });
                      else if (file) processJob({ kind: "file", source: file.name, fileName: file.name } as any);
                    }}
                    className="flex items-center gap-2 px-5 py-3 rounded-xl bg-teal-600 hover:bg-teal-600/90 text-white transition disabled:opacity-60 disabled:hover:bg-teal-600"
                  >
                    {job?.status === "running" ? "Processing..." : "Start processing"}
                  </button>

                  <button
                    onClick={cancelProcessing}
                    disabled={job?.status !== "running"}
                    className="px-5 py-3 rounded-xl border border-[var(--border)] bg-[var(--card)] hover:bg-white/10 dark:hover:bg-white/10 transition disabled:opacity-60"
                  >
                    Cancel
                  </button>

                  <button
                    onClick={() => {
                      setJob(null);
                      setPdfUrl(null);
                      setFile(null);
                      setUrl("");
                      resetOutput();
                      appendLog("Cleared current job.");
                    }}
                    className="px-5 py-3 rounded-xl border border-[var(--border)] bg-transparent hover:bg-white/5 dark:hover:bg-white/5 transition"
                  >
                    Clear
                  </button>
                </div>

                {job?.status === "error" && (
                  <div className="text-sm text-red-500 mt-1">{job?.error || "Something went wrong."}</div>
                )}
              </div>
            </motion.section>

            <motion.section
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: job ? 1 : 0.85, y: 0 }}
              transition={{ duration: 0.35 }}
              className="card rounded-2xl p-6"
            >
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="font-semibold text-lg">Progress</h2>
                  <p className="text-sm text-[var(--muted)] mt-1">
                    {job?.status === "running"
                      ? "Watching each pipeline step in real time."
                      : job?.status === "completed"
                        ? "Done. Outputs are ready."
                        : "Ready when you are."}
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-sm text-[var(--muted)]">Overall</div>
                  <div className="font-semibold text-xl">{job?.progress ?? 0}%</div>
                </div>
              </div>

              <div className="mt-5 grid grid-cols-1 sm:grid-cols-5 gap-2">
                {STEPS.map((s, idx) => {
                  const currentStep = job?.step;
                  const currentIdx = currentStep ? getStepIndex(currentStep) : -1;
                  const stepIdx = idx;
                  const status =
                    currentIdx < 0
                      ? "pending"
                      : stepIdx < currentIdx
                        ? "done"
                        : stepIdx > currentIdx
                          ? "pending"
                          : job?.progress === 100
                            ? "done"
                            : "active";
                  const isDone = status === "done";
                  const isActive = status === "active";
                  return (
                    <div key={s.key} className="text-center">
                      <div
                        className={`mx-auto w-9 h-9 rounded-xl flex items-center justify-center border ${
                          isDone
                            ? "border-teal-500/60 bg-teal-500/15 text-teal-500"
                            : isActive
                              ? "border-teal-500/90 bg-teal-500/25 text-teal-400"
                              : "border-[var(--border)] text-[var(--muted)]"
                        }`}
                      >
                        {isDone ? "✓" : idx + 1}
                      </div>
                      <div className="text-[11px] mt-2 text-[var(--muted)]">{s.label}</div>
                    </div>
                  );
                })}
              </div>

              <div className="mt-5">
                <div className="h-3 w-full rounded-full bg-[var(--border)] overflow-hidden">
                  <div
                    className="h-full bg-teal-500 transition-all"
                    style={{ width: `${job?.progress ?? 0}%` }}
                  />
                </div>
              </div>

              <div className="mt-5">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium">Live Logs</div>
                  <div className="text-xs text-[var(--muted)]">{job?.status === "running" ? "Streaming..." : ""}</div>
                </div>

                <div className="mt-2 rounded-xl border border-[var(--border)] bg-black/5 dark:bg-white/5 p-3">
                  <div className="max-h-56 overflow-auto">
                    <div className="font-mono text-[12px] leading-relaxed whitespace-pre-wrap">
                      {(job?.logs || []).slice(-200).map((l, i) => (
                        <div key={i}>{l}</div>
                      ))}
                      {(job?.logs?.length || 0) === 0 && (
                        <div className="text-[var(--muted)]">No logs yet.</div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </motion.section>

            <motion.section className="card rounded-2xl p-6" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-semibold text-lg">Output</h2>
                  <p className="text-sm text-[var(--muted)] mt-1">Preview transcript and AI-generated notes.</p>
                </div>
                {job?.status === "completed" && <div className="text-xs text-[var(--muted)]">{new Date(job.createdAt).toLocaleString()}</div>}
              </div>

              <AnimatePresence>
                {job && job.status !== "idle" ? (
                  <div className="mt-5 space-y-6">
                    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                      <div className="flex items-center justify-between gap-3 flex-wrap">
                        <div>
                          <div className="font-semibold text-lg">{title}</div>
                          <div className="text-xs text-[var(--muted)] mt-1">Markdown notes preview</div>
                        </div>
                        <div className="flex gap-2 flex-wrap justify-end">
                          <button
                            className="px-3 py-2 rounded-xl border border-[var(--border)] hover:bg-white/10 transition text-sm"
                            disabled={!notesMarkdown}
                            onClick={() => navigator.clipboard.writeText(notesMarkdown || "")}
                          >
                            Copy notes
                          </button>
                          <button
                            className="px-3 py-2 rounded-xl border border-[var(--border)] hover:bg-white/10 transition text-sm"
                            disabled={!transcriptText}
                            onClick={() => {
                              const blob = new Blob([transcriptText], { type: "text/plain;charset=utf-8" });
                              const a = document.createElement("a");
                              a.href = URL.createObjectURL(blob);
                              a.download = `${title}_transcript.txt`;
                              a.click();
                            }}
                          >
                            Transcript
                          </button>
                          <button
                            className="px-3 py-2 rounded-xl border border-[var(--border)] hover:bg-white/10 transition text-sm"
                            disabled={!notesMarkdown}
                            onClick={() => {
                              const blob = new Blob([notesMarkdown], { type: "text/markdown;charset=utf-8" });
                              const a = document.createElement("a");
                              a.href = URL.createObjectURL(blob);
                              a.download = `${title}_notes.md`;
                              a.click();
                            }}
                          >
                            Notes (.md)
                          </button>
                        </div>
                      </div>

                      <div className="mt-4">
                        <div className="text-sm font-medium">Notes Preview</div>
                        <div className="mt-2 prose prose-teal dark:prose-invert max-w-none">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{notesMarkdown || "No notes yet."}</ReactMarkdown>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="text-sm font-medium">PDF</div>
                          <div className="text-xs text-[var(--muted)] mt-1">Download-ready PDF</div>
                        </div>
                        <div className="flex gap-2 flex-wrap justify-end">
                          <button
                            className="px-3 py-2 rounded-xl bg-teal-600 hover:bg-teal-600/90 text-white transition text-sm disabled:opacity-60"
                            disabled={!notesMarkdown || pdfLoading}
                            onClick={async () => {
                              // Generate PDF lazily for history-loaded jobs.
                              let currentPdfUrl = pdfUrl;
                              if (!currentPdfUrl && notesMarkdown) {
                                setPdfLoading(true);
                                const pdfBytes = await generatePdfFromMarkdown({
                                  title: title || "AI Video Lecture Notes",
                                  markdown: notesMarkdown,
                                });
                                const pdfArrayBuffer = (pdfBytes.buffer as ArrayBuffer).slice(
                                  pdfBytes.byteOffset,
                                  pdfBytes.byteOffset + pdfBytes.byteLength,
                                );
                                const blob = new Blob([pdfArrayBuffer], {
                                  type: "application/pdf",
                                });
                                currentPdfUrl = URL.createObjectURL(blob);
                                setPdfUrl(currentPdfUrl);
                                setPdfLoading(false);
                              }

                              if (!currentPdfUrl) return;
                              const a = document.createElement("a");
                              a.href = currentPdfUrl;
                              a.download = `${title}_notes.pdf`;
                              a.click();
                            }}
                          >
                            {pdfLoading ? "Generating..." : "Download PDF"}
                          </button>
                          <button
                            className="px-3 py-2 rounded-xl border border-[var(--border)] hover:bg-white/10 transition text-sm"
                            disabled={!job?.id}
                            onClick={() => {
                              if (!job?.id) return;
                              const nextUrl = new URL(window.location.href);
                              nextUrl.searchParams.set("job", job.id);
                              navigator.clipboard.writeText(nextUrl.toString());
                            }}
                          >
                            Share link
                          </button>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                      <div className="text-sm font-medium">Transcript</div>
                      <div className="mt-2 rounded-xl border border-[var(--border)] bg-black/5 dark:bg-white/5 p-3 max-h-56 overflow-auto font-mono text-[12px] whitespace-pre-wrap">
                        {transcriptText || "No transcript yet."}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="mt-6 text-[var(--muted)]">Start processing to generate transcript, notes, and PDF.</div>
                )}
              </AnimatePresence>
            </motion.section>
          </div>

          <aside className="lg:col-span-5 space-y-6">
            <motion.section className="card rounded-2xl p-6" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="font-semibold text-lg">History</h2>
                  <p className="text-sm text-[var(--muted)] mt-1">Saved in your browser (local storage)</p>
                </div>
                <div className="text-xs text-[var(--muted)]">{history.length} items</div>
              </div>

              <div className="mt-4 space-y-3">
                {history.length === 0 ? (
                  <div className="text-sm text-[var(--muted)]">No previous summaries yet.</div>
                ) : (
                  history.slice(0, 12).map((h) => (
                    <button
                      key={h.id}
                      onClick={() => {
                        setPdfLoading(false);
                        setPdfUrl(null);
                        setJob({
                          id: h.id,
                          createdAt: h.createdAt,
                          input: { kind: "url", source: h.source },
                          status: "completed",
                          step: "pdf_export",
                          progress: 100,
                          logs: ["Loaded from local history."],
                          transcript: h.transcript,
                          title: h.title,
                          notesMarkdown: h.notesMarkdown,
                        });
                      }}
                      className="w-full text-left rounded-xl border border-[var(--border)] bg-[var(--card)] hover:bg-white/10 transition p-3"
                    >
                      <div className="font-medium line-clamp-2">{h.title}</div>
                      <div className="text-xs text-[var(--muted)] mt-1">
                        {new Date(h.createdAt).toLocaleDateString()} • {h.source}
                      </div>
                    </button>
                  ))
                )}
              </div>
            </motion.section>

            <motion.section className="card rounded-2xl p-6" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
              <h2 className="font-semibold text-lg">Performance</h2>
              <ul className="mt-3 text-sm text-[var(--muted)] space-y-2 list-disc pl-5">
                <li>FFmpeg + Whisper run in Web Workers to keep the UI responsive.</li>
                <li>Lazy loading: models load on first run inside their workers.</li>
                <li>If URL download is blocked, audio extraction uses server fallback.</li>
              </ul>
            </motion.section>
          </aside>
        </div>
      </main>
    </div>
  );
}
