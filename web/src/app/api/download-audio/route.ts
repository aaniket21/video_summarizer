/* eslint-disable @typescript-eslint/no-explicit-any */
import { NextResponse } from "next/server";
import { execFile } from "child_process";
import path from "path";

function runPythonScript(scriptPath: string, args: string[]): Promise<any> {
  return new Promise((resolve, reject) => {
    execFile("python", [scriptPath, ...args], { maxBuffer: 50 * 1024 * 1024 }, (err, stdout, stderr) => {
      if (err) {
        reject(new Error((stderr || stdout || err.message).toString()));
        return;
      }
      try {
        resolve(JSON.parse(String(stdout)));
      } catch (e: any) {
        reject(new Error(`Failed to parse python output: ${e?.message || String(e)}`));
      }
    });
  });
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const url = String(body?.url || "").trim();
    if (!url) {
      return NextResponse.json({ error: "Missing url." }, { status: 400 });
    }

    const scriptPath = path.join(process.cwd(), "server", "download_audio.py");
    const result = await runPythonScript(scriptPath, [url]);
    if (result?.error) {
      return NextResponse.json({ error: String(result.error) }, { status: 500 });
    }
    return NextResponse.json(result);
  } catch (e: any) {
    return NextResponse.json(
      { error: e?.message ? String(e.message) : "Download-audio failed." },
      { status: 500 },
    );
  }
}

