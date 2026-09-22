#!/usr/bin/env python3
"""
Premium Clip Cutter
--------------------
A desktop GUI tool: paste a YouTube video / Shorts link, and it will:
  - Download the video
  - Auto-transcribe the voice (Bangla / Hindi / English / most languages,
    auto-detected) using Whisper AI
  - Split the video into clips of a length YOU choose (in seconds)
  - Burn subtitles into every clip
  - Optionally add a text or image watermark to every clip

============================================================
 WINDOWS BUILD / INSTALL
============================================================
The Windows package uses a bundled FFmpeg executable. Build the
standalone application with BUILD_WINDOWS.bat, then install the
created Output\PremiumClipCutter_Setup.exe.

Whisper models are downloaded on first use.
"""

import os
import sys
import math
import shutil
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


# ---------------------------------------------------------------------
# Core processing (same idea as the CLI version, wired to the GUI log)
# ---------------------------------------------------------------------

def resource_path(name):
    """Resolve bundled resources for both normal Python and PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def ffmpeg_path():
    bundled = resource_path(os.path.join("ffmpeg", "ffmpeg.exe"))
    return bundled if os.path.isfile(bundled) else "ffmpeg"


def ffprobe_path():
    bundled = resource_path(os.path.join("ffmpeg", "ffprobe.exe"))
    return bundled if os.path.isfile(bundled) else "ffprobe"


def run(cmd, log):
    cmd = [ffmpeg_path() if x == "__FFMPEG__" else ffprobe_path() if x == "__FFPROBE__" else x for x in cmd]
    log("$ " + " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, bufsize=1, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for line in proc.stdout:
        log(line.rstrip())
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")


def download_video(url, workdir, log):
    import yt_dlp
    out_template = os.path.join(workdir, "source.%(ext)s")
    log("Downloading with yt-dlp...")
    opts = {
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": out_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": os.path.dirname(ffmpeg_path()) if os.path.isabs(ffmpeg_path()) else None,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    for f in os.listdir(workdir):
        if f.startswith("source.") and f.lower().endswith((".mp4", ".mkv", ".webm", ".mov")):
            return os.path.join(workdir, f)
    raise RuntimeError("Download failed - could not find the video file. Check the link.")


def get_duration(path):
    result = subprocess.run(
        ["__FFPROBE__", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True
    )
    return float(result.stdout.strip())


def transcribe(path, model_size, log):
    import whisper
    log(f"Loading Whisper model '{model_size}' (first run downloads it)...")
    model = whisper.load_model(model_size)
    log("Transcribing audio - language is auto-detected "
        "(Bangla / Hindi / English / etc all supported)...")
    result = model.transcribe(path, verbose=False)
    log(f"Detected language: {result.get('language', 'unknown')}")
    return result["segments"]


def fmt_ts(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:06.3f}".replace(".", ",")


def write_srt(segments, path, clip_start, clip_end):
    idx = 1
    with open(path, "w", encoding="utf-8") as f:
        for seg in segments:
            if seg["end"] <= clip_start or seg["start"] >= clip_end:
                continue
            start = max(seg["start"], clip_start) - clip_start
            end = min(seg["end"], clip_end) - clip_start
            if end <= start:
                continue
            f.write(f"{idx}\n")
            f.write(f"{fmt_ts(start)} --> {fmt_ts(end)}\n")
            f.write(seg["text"].strip() + "\n\n")
            idx += 1


POSITION_MAP = {
    "Top Left":     "20:20",
    "Top Right":    "W-w-20:20",
    "Bottom Left":  "20:H-h-20",
    "Bottom Right": "W-w-20:H-h-20",
    "Center":       "(W-w)/2:(H-h)/2",
}


def make_clip(source, start, length, out_path, srt_path, opts, log):
    """opts: dict with burn_subs, wm_text, wm_image, wm_position"""
    burn_subs = opts["burn_subs"]
    wm_text = opts.get("wm_text", "").strip()
    wm_image = opts.get("wm_image", "").strip()
    position = POSITION_MAP.get(opts.get("wm_position", "Bottom Right"), "W-w-20:H-h-20")

    vf_parts = []
    if burn_subs:
        srt_escaped = os.path.abspath(srt_path).replace("\\", "/").replace(":", "\\:")
        vf_parts.append(
            f"subtitles='{srt_escaped}':force_style="
            f"'FontSize=22,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BorderStyle=3'"
        )
    if wm_text:
        safe_text = wm_text.replace("'", "\\'").replace(":", "\\:")
        tx, ty = position.split(":")
        vf_parts.append(
            f"drawtext=text='{safe_text}':fontcolor=white@0.85:fontsize=28:"
            f"box=1:boxcolor=black@0.35:boxborderw=8:x={tx}:y={ty}"
        )

    if wm_image and os.path.isfile(wm_image):
        # needs a second input -> use filter_complex
        vf_chain = ",".join(vf_parts) if vf_parts else None
        filter_complex = ""
        if vf_chain:
            filter_complex += f"[0:v]{vf_chain}[v0];[v0][1:v]overlay={position}[v]"
        else:
            filter_complex += f"[0:v][1:v]overlay={position}[v]"
        cmd = ["__FFMPEG__", "-y", "-ss", str(start), "-t", str(length), "-i", source,
               "-i", wm_image, "-filter_complex", filter_complex, "-map", "[v]",
               "-map", "0:a?", "-c:v", "libx264", "-preset", "fast", "-crf", "20",
               "-c:a", "aac", out_path]
        run(cmd, log)
        return

    if vf_parts:
        vf = ",".join(vf_parts)
        run(["__FFMPEG__", "-y", "-ss", str(start), "-t", str(length), "-i", source,
             "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "20",
             "-c:a", "aac", out_path], log)
    else:
        run(["__FFMPEG__", "-y", "-ss", str(start), "-t", str(length), "-i", source,
             "-c", "copy", out_path], log)


def process(url, length, model_size, outdir, opts, log, on_done, on_error):
    try:
        outdir = os.path.abspath(os.path.expanduser(outdir))
        workdir = os.path.join(os.environ.get("TEMP", os.getcwd()), "PremiumClipCutter_temp")
        os.makedirs(workdir, exist_ok=True)
        os.makedirs(outdir, exist_ok=True)

        log("Step 1/3: Downloading video...")
        source = download_video(url, workdir, log)

        log("Step 2/3: Transcribing (generating subtitles)...")
        segments = transcribe(source, model_size, log)

        duration = get_duration(source)
        n_clips = math.ceil(duration / length)
        log(f"Video length: {duration:.1f}s -> {n_clips} clip(s) of {length}s each")

        log("Step 3/3: Cutting clips + writing subtitles + watermark...")
        for i in range(n_clips):
            start = i * length
            clip_len = min(length, duration - start)
            clip_name = f"clip_{i+1:03}"
            srt_path = os.path.join(outdir, clip_name + ".srt")
            out_path = os.path.join(outdir, clip_name + ".mp4")
            write_srt(segments, srt_path, start, start + clip_len)
            make_clip(source, start, clip_len, out_path, srt_path, opts, log)
            log(f"  -> {out_path}")

        shutil.rmtree(workdir, ignore_errors=True)
        log("\nDone! All clips are in: " + os.path.abspath(outdir))
        on_done(outdir)
    except Exception as e:
        on_error(str(e))


# ---------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Premium Clip Cutter")
        try:
            icon = resource_path("app.ico")
            if os.path.isfile(icon):
                self.iconbitmap(icon)
        except Exception:
            pass
        self.geometry("720x680")
        self.resizable(False, False)

        pad = {"padx": 10, "pady": 6}

        tk.Label(self, text="Premium Clip Cutter", font=("Segoe UI", 18, "bold")).pack(pady=(14, 2))
        tk.Label(self, text="YouTube video / Shorts link paste korun -> clip + subtitle + watermark",
                 font=("Segoe UI", 9)).pack(pady=(0, 10))

        form = tk.Frame(self)
        form.pack(fill="x", **pad)

        tk.Label(form, text="YouTube / Shorts Link:", anchor="w").grid(row=0, column=0, sticky="w")
        self.url_entry = tk.Entry(form, width=70)
        self.url_entry.grid(row=1, column=0, columnspan=3, sticky="we", pady=(0, 10))

        tk.Label(form, text="Clip Length (seconds):", anchor="w").grid(row=2, column=0, sticky="w")
        self.length_entry = tk.Entry(form, width=10)
        self.length_entry.insert(0, "60")
        self.length_entry.grid(row=2, column=1, sticky="w")

        tk.Label(form, text="Subtitle Quality (Whisper model):", anchor="w").grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.model_var = tk.StringVar(value="base")
        ttk.Combobox(form, textvariable=self.model_var, width=14, state="readonly",
                     values=["tiny", "base", "small", "medium", "large"]).grid(row=3, column=1, sticky="w", pady=(10, 0))
        tk.Label(form, text="(bigger = better accuracy, slower)", fg="gray").grid(row=3, column=2, sticky="w", pady=(10, 0))

        self.burn_var = tk.BooleanVar(value=True)
        tk.Checkbutton(form, text="Burn subtitles into the video (recommended)",
                        variable=self.burn_var).grid(row=4, column=0, columnspan=3, sticky="w", pady=(10, 0))

        # Watermark section
        wm_frame = tk.LabelFrame(self, text="Watermark (optional)", padx=10, pady=10)
        wm_frame.pack(fill="x", padx=10, pady=10)

        tk.Label(wm_frame, text="Watermark Text:").grid(row=0, column=0, sticky="w")
        self.wm_text_entry = tk.Entry(wm_frame, width=40)
        self.wm_text_entry.grid(row=0, column=1, columnspan=2, sticky="w")

        tk.Label(wm_frame, text="Watermark Image (logo):").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.wm_image_entry = tk.Entry(wm_frame, width=40)
        self.wm_image_entry.grid(row=1, column=1, sticky="w", pady=(8, 0))
        tk.Button(wm_frame, text="Browse...", command=self.browse_image).grid(row=1, column=2, padx=(6, 0), pady=(8, 0))

        tk.Label(wm_frame, text="Position:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.wm_pos_var = tk.StringVar(value="Bottom Right")
        ttk.Combobox(wm_frame, textvariable=self.wm_pos_var, width=16, state="readonly",
                     values=list(POSITION_MAP.keys())).grid(row=2, column=1, sticky="w", pady=(8, 0))

        # Output folder
        out_frame = tk.Frame(self)
        out_frame.pack(fill="x", padx=10, pady=(0, 6))
        tk.Label(out_frame, text="Output Folder:").grid(row=0, column=0, sticky="w")
        self.outdir_entry = tk.Entry(out_frame, width=50)
        self.outdir_entry.insert(0, "clips_output")
        self.outdir_entry.grid(row=0, column=1, sticky="w")
        tk.Button(out_frame, text="Browse...", command=self.browse_outdir).grid(row=0, column=2, padx=(6, 0))

        # Start button
        self.start_btn = tk.Button(self, text="Start", font=("Segoe UI", 12, "bold"),
                                    bg="#d81f26", fg="white", height=1, command=self.start)
        self.start_btn.pack(pady=8, ipadx=30)

        # Log box
        log_frame = tk.Frame(self)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log_box = tk.Text(log_frame, height=12, bg="#111", fg="#0f0", font=("Consolas", 9))
        self.log_box.pack(fill="both", expand=True)

    def browse_image(self):
        path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg")])
        if path:
            self.wm_image_entry.delete(0, tk.END)
            self.wm_image_entry.insert(0, path)

    def browse_outdir(self):
        path = filedialog.askdirectory()
        if path:
            self.outdir_entry.delete(0, tk.END)
            self.outdir_entry.insert(0, path)

    def log(self, msg):
        self.after(0, self._append_log, msg)

    def _append_log(self, msg):
        self.log_box.insert(tk.END, msg + "\n")
        self.log_box.see(tk.END)

    def start(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "YouTube / Shorts link din")
            return
        try:
            length = int(self.length_entry.get().strip())
            if length <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Clip length ekta shothik number hote hobe (seconds)")
            return

        opts = {
            "burn_subs": self.burn_var.get(),
            "wm_text": self.wm_text_entry.get(),
            "wm_image": self.wm_image_entry.get(),
            "wm_position": self.wm_pos_var.get(),
        }
        model_size = self.model_var.get()
        outdir = self.outdir_entry.get().strip() or "clips_output"

        self.start_btn.config(state="disabled", text="Processing...")
        self.log_box.delete("1.0", tk.END)

        def on_done(outdir_result):
            def finish():
                self.start_btn.config(state="normal", text="Start")
                messagebox.showinfo("Done", f"Clips ready in:\n{os.path.abspath(outdir_result)}")
            self.after(0, finish)

        def on_error(msg):
            def fail():
                self.start_btn.config(state="normal", text="Start")
                messagebox.showerror("Error", msg)
            self.after(0, fail)

        t = threading.Thread(
            target=process,
            args=(url, length, model_size, outdir, opts, self.log, on_done, on_error),
            daemon=True,
        )
        t.start()


if __name__ == "__main__":
    App().mainloop()
