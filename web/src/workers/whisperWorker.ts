/* eslint-disable @typescript-eslint/no-explicit-any */
/// <reference lib="webworker" />

import { pipeline } from "@xenova/transformers";

type WorkerRequest =
  | { type: "transcribe"; audioWav: ArrayBuffer }
  | { type: "shutdown" };

type WorkerResponse =
  | { type: "log"; message: string }
  | { type: "progress"; step: "transcription"; progress: number }
  | { type: "transcription"; transcript: string }
  | { type: "error"; message: string };

let asr: any = null;
let loadPromise: Promise<any> | null = null;

async function getAsr() {
  if (asr) return asr;
  if (loadPromise) return loadPromise;
  loadPromise = (async () => {
    (self as any).TRANSFORMERS_CACHE = "auto";
    postMessage({
      type: "log",
      message: "Loading Whisper model (WASM/ONNX)...",
    } satisfies WorkerResponse);

    // Choose a reasonably small model for browser use.
    // You can swap this to a bigger model if your machine is strong enough.
    const transcriber = await pipeline(
      "automatic-speech-recognition",
      "Xenova/whisper-tiny.en",
    );
    return transcriber;
  })();
  asr = await loadPromise;
  return asr;
}

self.onmessage = async (ev: MessageEvent<WorkerRequest>) => {
  try {
    const msg = ev.data;
    if (msg.type === "shutdown") {
      close();
      return;
    }

    if (msg.type !== "transcribe") return;

    postMessage({
      type: "progress",
      step: "transcription",
      progress: 8,
    } satisfies WorkerResponse);

    const model = await getAsr();

    postMessage({
      type: "progress",
      step: "transcription",
      progress: 35,
    } satisfies WorkerResponse);

    // Decode WAV bytes to PCM samples.
    // Note: Web Workers can use WebAudio APIs in modern browsers.
    const audioCtx = new (self as any).AudioContext();
    const decoded: AudioBuffer = await audioCtx.decodeAudioData(msg.audioWav.slice(0));
    const samples = decoded.getChannelData(0); // Float32Array
    const sampling_rate = decoded.sampleRate;

    postMessage({
      type: "log",
      message: `Transcribing (${Math.round(samples.length / sampling_rate)}s)...`,
    } satisfies WorkerResponse);

    // Xenova pipeline expects either raw samples or an object depending on backend.
    // This call matches the common "data + sampling_rate" pattern.
    const output = await model(
      { data: samples, sampling_rate },
      {
        chunk_length_s: 30,
        stride_length_s: 5,
        return_timestamps: false,
      },
    );

    postMessage({
      type: "progress",
      step: "transcription",
      progress: 92,
    } satisfies WorkerResponse);

    const transcript =
      (output?.text as string | undefined) ||
      (output?.transcription as string | undefined) ||
      "";

    postMessage(
      { type: "transcription", transcript: transcript.trim() } satisfies WorkerResponse,
    );
  } catch (e: any) {
    postMessage({
      type: "error",
      message: e?.message ? String(e.message) : "Transcription failed",
    } satisfies WorkerResponse);
  }
};

