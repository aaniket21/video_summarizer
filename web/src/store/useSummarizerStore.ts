import { create } from "zustand";

export type JobStep =
  | "download"
  | "audio_extraction"
  | "transcription"
  | "notes_generation"
  | "pdf_export";

export type JobStatus = "idle" | "running" | "completed" | "error" | "cancelled";

export type JobInput =
  | { kind: "url"; source: string }
  | { kind: "file"; source: string; fileName: string };

export type HistoryItem = {
  id: string;
  createdAt: number;
  title: string;
  source: string;
  transcript: string;
  notesMarkdown: string;
};

export type SummarizerSnapshot = {
  id: string;
  createdAt: number;
  input: JobInput;
  status: JobStatus;
  step: JobStep;
  progress: number; // 0..100
  logs: string[];
  transcript: string;
  title: string;
  notesMarkdown: string;
  error?: string;
};

type SummarizerState = {
  theme: "light" | "dark";
  setTheme: (t: "light" | "dark") => void;

  job: SummarizerSnapshot | null;
  history: HistoryItem[];

  setJob: (job: SummarizerSnapshot | null) => void;
  setStatus: (status: JobStatus) => void;
  setStep: (step: JobStep) => void;
  setProgress: (progress: number) => void;
  appendLog: (line: string) => void;
  setError: (error: string) => void;

  setTranscript: (transcript: string) => void;
  setTitle: (title: string) => void;
  setNotesMarkdown: (notesMarkdown: string) => void;

  setHistory: (history: HistoryItem[]) => void;
  upsertHistoryItem: (item: HistoryItem) => void;
};

export const useSummarizerStore = create<SummarizerState>((set) => ({
  theme: "light",

  setTheme: (t) => set({ theme: t }),

  job: null,
  history: [],

  setJob: (job) => set({ job }),

  setStatus: (status) =>
    set((s) => ({
      job: s.job ? { ...s.job, status } : s.job,
    })),

  setStep: (step) =>
    set((s) => ({
      job: s.job ? { ...s.job, step } : s.job,
    })),

  setProgress: (progress) =>
    set((s) => ({
      job: s.job ? { ...s.job, progress } : s.job,
    })),

  appendLog: (line) =>
    set((s) => ({
      job: s.job ? { ...s.job, logs: [...s.job.logs, line] } : s.job,
    })),

  setError: (error) =>
    set((s) => ({
      job: s.job
        ? {
            ...s.job,
            // Only force "error" status when there is an actual error message.
            status: error ? "error" : s.job.status,
            error,
          }
        : s.job,
    })),

  setTranscript: (transcript) =>
    set((s) => ({
      job: s.job ? { ...s.job, transcript } : s.job,
    })),

  setTitle: (title) =>
    set((s) => ({
      job: s.job ? { ...s.job, title } : s.job,
    })),

  setNotesMarkdown: (notesMarkdown) =>
    set((s) => ({
      job: s.job ? { ...s.job, notesMarkdown } : s.job,
    })),

  setHistory: (history) => set({ history }),

  upsertHistoryItem: (item) =>
    set((s) => {
      const existing = s.history.find((h) => h.id === item.id);
      if (existing) {
        return {
          history: s.history.map((h) => (h.id === item.id ? item : h)),
        };
      }
      return { history: [item, ...s.history] };
    }),
}));

