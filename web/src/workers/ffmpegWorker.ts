/* eslint-disable @typescript-eslint/no-explicit-any */
/// <reference lib="webworker" />

import { FFmpeg } from "@ffmpeg/ffmpeg";

type WorkerRequest =
  | {
      type: "extract-audio";
      videoBytes: ArrayBuffer;
      originalName?: string;
    }
  | { type: "shutdown" };

type WorkerResponse =
  | { type: "log"; message: string }
  | { type: "progress"; step: "audio_extraction"; progress: number }
  | { type: "audio"; audioWav: ArrayBuffer }
  | { type: "error"; message: string };

const ffmpeg = new FFmpeg();

ffmpeg.on("log", ({ message }: any) => {
  const msg = typeof message === "string" ? message : String(message);
  postMessage({ type: "log", message: msg.slice(0, 300) } satisfies WorkerResponse);
});

ffmpeg.on("progress", ({ progress }: any) => {
  const p = typeof progress === "number" ? progress : 0;
  const pct = p <= 1 ? Math.round(p * 100) : Math.round(p);
  postMessage({
    type: "progress",
    step: "audio_extraction",
    progress: Math.max(0, Math.min(100, pct)),
  } satisfies WorkerResponse);
});

self.onmessage = async (ev: MessageEvent<WorkerRequest>) => {
  try {
    const msg = ev.data;
    if (msg.type === "shutdown") {
      close();
      return;
    }

    if (msg.type !== "extract-audio") return;

    postMessage({ type: "log", message: "Loading FFmpeg WASM..." } satisfies WorkerResponse);

    await ffmpeg.load();

    postMessage({ type: "log", message: "Extracting mono 16kHz WAV..." } satisfies WorkerResponse);

    const input = new Uint8Array(msg.videoBytes);
    await ffmpeg.writeFile("input", input);

    // -ac 1: mono, -ar 16000: 16kHz
    await ffmpeg.exec(["-i", "input", "-ar", "16000", "-ac", "1", "output.wav"]);

    const out = (await ffmpeg.readFile("output.wav")) as Uint8Array;
    const outBuf = (out.buffer as ArrayBuffer).slice(
      out.byteOffset,
      out.byteOffset + out.byteLength,
    );

    // Cleanup FS to reduce memory.
    try {
      await ffmpeg.deleteFile("input");
      await ffmpeg.deleteFile("output.wav");
    } catch {
      // ignore
    }

    postMessage({ type: "progress", step: "audio_extraction", progress: 100 } satisfies WorkerResponse);
    postMessage({ type: "audio", audioWav: outBuf } satisfies WorkerResponse, [outBuf]);
  } catch (e: any) {
    postMessage({
      type: "error",
      message: e?.message ? String(e.message) : "FFmpeg extraction failed",
    } satisfies WorkerResponse);
  }
};

