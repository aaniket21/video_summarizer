import base64
import json
import os
import subprocess
import sys
import tempfile


def download_best_audio(url: str, out_dir: str) -> str:
    # Download audio only (fast) and let ffmpeg convert to WAV.
    # yt-dlp should be installed in your Python environment.
    import yt_dlp  # type: ignore

    outtmpl = os.path.join(out_dir, "%(title)s.%(ext)s")
    ydl_opts = {
        "outtmpl": outtmpl,
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if isinstance(info, dict) and "entries" in info and info["entries"]:
            info = info["entries"][0]
        filename = ydl.prepare_filename(info)
        return filename


def extract_wav(input_path: str, out_wav: str):
    # mono (1 channel) and 16k sample rate to match Whisper assumptions
    cmd = ["ffmpeg", "-i", input_path, "-ar", "16000", "-ac", "1", out_wav, "-y"]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Missing url"}))
        return
    url = sys.argv[1]

    with tempfile.TemporaryDirectory() as tmp:
        audio_path = download_best_audio(url, tmp)
        wav_path = os.path.join(tmp, "audio.wav")
        extract_wav(audio_path, wav_path)

        with open(wav_path, "rb") as f:
            raw = f.read()

        b64 = base64.b64encode(raw).decode("ascii")
        print(json.dumps({"audioWavBase64": b64}))


if __name__ == "__main__":
    main()

