# py -3.12 -m pip install
"""
Requirements:
1. pip install flask waitress
2. Install FFmpeg and add to System PATH.
"""

import os
import time
import json
import zipfile
import io
import shutil
import platform
import subprocess
import atexit
import signal
import sys
import threading
import uuid
import re
import socket
import ipaddress
from flask import Flask, request, send_file, render_template_string, jsonify, after_this_request
from waitress import serve

# ==========================================
# CONFIGURATION
# ==========================================

progress_store = {}

HIDE_CONSOLE_WINDOW = True

# Network: '0.0.0.0' = accessible from other devices on your LAN
#          '127.0.0.1' = local machine only
HOST = '0.0.0.0'
PORT = 8089

# Video performance. "auto" tests NVIDIA/Intel/AMD hardware encoders and
# safely falls back to libx264. Set to "software" to force CPU encoding.
VIDEO_ENCODER_MODE = "auto"
VIDEO_SOFTWARE_PRESET = "veryfast"  # ultrafast, superfast, veryfast, faster, fast, medium...
VIDEO_DEFAULT_CRF = 23

# Small/medium files are uploaded in full for reliable FFprobe metadata. Large
# files use browser-side width/height detection to avoid uploading them twice.
PROBE_FULL_UPLOAD_LIMIT_MB = 64

FAVICON_BASE64 = """data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAB8AAAAfCAYAA
AAfrhY5AAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAAEnQAABJ0Ad5mH3gAAAEJ
SURBVFhHzZZBDsIwDAT7GCReyJkH84iiVLgyEydZp0FipL3YrsftAbHtCV6P21f2572uJdhYiPCyUTJ
HdOUZKaMcEcqvSJneEU05l1yJJF/5xkz0BSo5H1qZpjwlJux34g/IyUdwPkglnxK3enwuiB2gyZXlo7
7LKV8inkjx6nLWL+Z3cuGZtnwE5xlh7pCzWC0gnGMI+y7xm08sCucNznU/e7SQdWYE5tfKk89o8pmo8
jKz9AAPe58cPvnnlYtZZ783Q3lBOsDTqrOHmLiQk0ciwnlFXpAPKCHsB/HiQiVPHZDIudvxP/9ejZVf
IHpjI5QbV47oSY2u3MgcoUgNSW7YYn9MVUvwBgMDdMKL4QZBAAAAAElFTkSuQmCC"""

FFMPEG_CMD  = shutil.which("ffmpeg")  or "ffmpeg"
FFPROBE_CMD = shutil.which("ffprobe") or "ffprobe"

SETTING_HELP = {
    "Resolution":    "Output size (Width x Height). Format: 1920x1080",
    "Quality":       "Image: 1-100 (100=best). Video CRF: 0-51 (0=lossless, 23=default).",
    "FPS":           "Frames Per Second. Do not exceed source FPS. e.g. 30, 60.",
    "Video Bitrate": "Data per second for video. e.g. 5000k or 5M.",
    "Audio Bitrate": "Data per second for audio. Standard 128k, High 320k.",
    "Sample Rate":   "Audio frequency. Standard 44100 or 48000.",
    "GIF FPS":       "Frames per second for animated GIF. Lower = smaller file. e.g. 10, 15.",
    "GIF Loop":      "0 = loop forever, 1 = play once then stop.",
}

# ==========================================
# FORMAT CLASSES
# ==========================================

class FileFormat:
    def __init__(self, name, media_type, description, pros, cons, settings):
        self.name = name; self.media_type = media_type; self.description = description
        self.pros = pros; self.cons = cons; self.settings = settings

    def to_dict(self):
        return {"name": self.name, "media_type": self.media_type,
                "desc": self.description, "pros": self.pros,
                "cons": self.cons, "settings": self.settings}

# --- Image ---
class WEBP(FileFormat):
    def __init__(self): super().__init__("WEBP","image","Modern superior lossless/lossy compression.","Tiny sizes.","Not on very old OS.",["Resolution","Quality"])
class JFIF(FileFormat):
    def __init__(self): super().__init__("JFIF","image","Standard JPEG wrapper.","Universal.","Lossy.",["Resolution","Quality"])
class JPEG(FileFormat):
    def __init__(self): super().__init__("JPEG","image","Standard lossy format for photography.","Universal.","No transparency.",["Resolution","Quality"])
class JPG(FileFormat):
    def __init__(self): super().__init__("JPG","image","Standard lossy format for photography.","Universal.","No transparency.",["Resolution","Quality"])
class PNG(FileFormat):
    def __init__(self): super().__init__("PNG","image","Lossless with transparency.","Full alpha.","Larger sizes.",["Resolution"])
class GIF(FileFormat):
    def __init__(self): super().__init__("GIF","image","Bitmap format for short animations.","Universally supported.","256 colors max.",["Resolution"])
class SVG(FileFormat):
    def __init__(self): super().__init__("SVG","image","Vector format for 2D graphics.","Infinite scalability.","Not for photos.",[])
class TIFF(FileFormat):
    def __init__(self): super().__init__("TIFF","image","High-quality raster.","Lossless.","Massive sizes.",["Resolution"])
class BMP(FileFormat):
    def __init__(self): super().__init__("BMP","image","Uncompressed bitmap.","Simple, lossless.","Extremely large.",["Resolution"])
class HEIF(FileFormat):
    def __init__(self): super().__init__("HEIF","image","High Efficiency Image File.","Better than JPEG.","Limited old support.",["Resolution","Quality"])
class HEIC(FileFormat):
    def __init__(self): super().__init__("HEIC","image","Apple's HEIF implementation.","Incredible ratio.","Playback issues on old OS.",["Resolution","Quality"])
class RAW(FileFormat):
    def __init__(self): super().__init__("RAW","image","Unprocessed sensor data.","Max data.","Requires special viewers.",["Resolution"])
class AVIF(FileFormat):
    def __init__(self): super().__init__("AVIF","image","Next-gen AV1 based.","Incredible compression.","Slow encode.",["Resolution","Quality"])

# --- Video ---
class MP4(FileFormat):
    def __init__(self): super().__init__("MP4","video","Most widely used container.","Universal.","Licensing.",["Resolution","FPS","Video Bitrate"])
class MOV(FileFormat):
    def __init__(self): super().__init__("MOV","video","Apple QuickTime.","Great for editing.","Larger sizes.",["Resolution","FPS"])
class MKV(FileFormat):
    def __init__(self): super().__init__("MKV","video","Flexible open container.","Unlimited tracks.","Not on all TVs.",["Resolution","FPS"])
class AVI(FileFormat):
    def __init__(self): super().__init__("AVI","video","Legacy Windows multimedia.","Legacy support.","Inefficient.",["Resolution","FPS"])
class WMV(FileFormat):
    def __init__(self): super().__init__("WMV","video","Windows Media Video.","Good for Windows.","Poor elsewhere.",["Resolution","FPS"])
class WEBM(FileFormat):
    def __init__(self): super().__init__("WEBM","video","Open web format.","HTML5 integration.","Less HW accel.",["Resolution","FPS","Video Bitrate"])
class FLV(FileFormat):
    def __init__(self): super().__init__("FLV","video","Legacy Flash format.","Legacy web.","Obsolete.",["Resolution"])
class AVCHD(FileFormat):
    def __init__(self): super().__init__("AVCHD","video","Camcorder HD standard.","High def recording.","Fragmented structure.",["Resolution","FPS"])
class MPEG2(FileFormat):
    def __init__(self): super().__init__("MPEG-2","video","Legacy DVD standard.","Old hardware compat.","Inefficient.",["Resolution","Video Bitrate"])
class THREE_GP(FileFormat):
    def __init__(self): super().__init__("3GP","video","3G phone container.","Tiny sizes.","Terrible quality.",["Resolution"])
class ANIMGIF(FileFormat):
    def __init__(self): super().__init__("Animated GIF","video","High-quality animated GIF from any video source. Uses palette optimisation for best colour accuracy.","Universally supported.","Large files, 256-colour limit.",["Resolution","GIF FPS","GIF Loop"])

# --- Audio ---
class MP3(FileFormat):
    def __init__(self): super().__init__("MP3","audio","Universal lossy audio.","Every device.","Lossy.",["Audio Bitrate","Sample Rate"])
class OGG(FileFormat):
    def __init__(self): super().__init__("OGG","audio","Open-source lossy.","Better than MP3.","Not everywhere.",["Audio Bitrate"])

FORMATS = [
    WEBP(),JFIF(),JPEG(),JPG(),PNG(),GIF(),SVG(),TIFF(),BMP(),HEIF(),HEIC(),RAW(),AVIF(),
    MP4(),MOV(),MKV(),AVI(),WMV(),WEBM(),FLV(),AVCHD(),MPEG2(),THREE_GP(),ANIMGIF(),MP3(),OGG()
]

# ==========================================
# CLEANUP
# ==========================================
app = Flask(__name__)
BASE_TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_conversions")

def wipe_temp_folder():
    """Full wipe — only on server startup/shutdown."""
    if os.path.exists(BASE_TEMP_DIR):
        try: shutil.rmtree(BASE_TEMP_DIR)
        except: pass
    os.makedirs(BASE_TEMP_DIR, exist_ok=True)

def wipe_session(session_id):
    """Delete only one user's session folder."""
    if not session_id or not re.match(r'^[a-f0-9\-]+$', session_id):
        return
    session_dir = os.path.join(BASE_TEMP_DIR, session_id)
    if os.path.exists(session_dir):
        try: shutil.rmtree(session_dir)
        except: pass
    progress_store.pop(session_id, None)

atexit.register(wipe_temp_folder)
signal.signal(signal.SIGTERM, lambda n, f: sys.exit(0))
signal.signal(signal.SIGINT,  lambda n, f: sys.exit(0))
wipe_temp_folder()

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_duration(file_path):
    try:
        cmd = [FFPROBE_CMD,"-v","error","-show_entries","format=duration",
               "-of","default=noprint_wrappers=1:nokey=1",file_path]
        si = None
        if HIDE_CONSOLE_WINDOW and platform.system()=="Windows":
            si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        r = subprocess.run(cmd, capture_output=True, startupinfo=si)
        return float(r.stdout.decode().strip())
    except: return 0

def parse_ffmpeg_time(line):
    m = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line)
    if m: return int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))
    return None

def run_command(cmd_list):
    si = None
    if HIDE_CONSOLE_WINDOW and platform.system()=="Windows":
        si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return subprocess.run(cmd_list, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=si)

def validate_settings(val, type_name):
    if not val: return None
    val = val.strip()
    if val.startswith('-'): raise ValueError(f"{type_name} cannot be negative.")
    if type_name == "Resolution":
        if 'x' not in val: raise ValueError("Resolution must be WxH e.g. 1920x1080")
        w, h = map(int, val.split('x'))
        if w<=0 or h<=0: raise ValueError("Resolution values must be positive.")
    if type_name in ["FPS","Sample Rate","Video Bitrate","Audio Bitrate","Quality","GIF FPS"]:
        clean = val.lower().replace('k','').replace('m','')
        if float(clean) <= 0: raise ValueError(f"{type_name} must be positive.")
    return val

def make_startupinfo():
    if HIDE_CONSOLE_WINDOW and platform.system()=="Windows":
        si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return si
    return None

_VIDEO_ENCODER_CACHE = None

def _encoder_smoke_test(encoder):
    """Return True only when FFmpeg can actually initialise this encoder."""
    cmd = [
        FFMPEG_CMD, "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=black:s=64x64:r=1:d=0.15",
        "-frames:v", "1", "-an", "-c:v", encoder,
        "-f", "null", "-"
    ]
    try:
        result = subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            startupinfo=make_startupinfo(), timeout=12
        )
        return result.returncode == 0
    except Exception:
        return False

def get_fast_h264_encoder():
    """Choose a working H.264 encoder once, preferring GPU hardware."""
    global _VIDEO_ENCODER_CACHE
    if _VIDEO_ENCODER_CACHE:
        return _VIDEO_ENCODER_CACHE

    candidates = ["libx264"]
    if VIDEO_ENCODER_MODE.strip().lower() == "auto":
        candidates = ["h264_nvenc", "h264_qsv", "h264_amf", "libx264"]

    for encoder in candidates:
        if _encoder_smoke_test(encoder):
            _VIDEO_ENCODER_CACHE = encoder
            print(f"Video encoder selected: {encoder}")
            return encoder

    _VIDEO_ENCODER_CACHE = "libx264"
    print("⚠️  No tested hardware encoder was available; using libx264.")
    return _VIDEO_ENCODER_CACHE

def append_h264_speed_options(cmd, encoder):
    cmd.extend(["-c:v", encoder])
    if encoder == "h264_nvenc":
        cmd.extend(["-preset", "p4"])
    elif encoder == "h264_qsv":
        cmd.extend(["-preset", "veryfast"])
    elif encoder == "h264_amf":
        cmd.extend(["-quality", "speed"])
    else:
        cmd.extend(["-preset", VIDEO_SOFTWARE_PRESET, "-threads", "0"])

def append_video_quality_options(cmd, encoder, quality):
    q = str(quality or VIDEO_DEFAULT_CRF)
    if encoder == "h264_nvenc":
        cmd.extend(["-rc", "vbr", "-cq", q, "-b:v", "0"])
    elif encoder == "h264_qsv":
        cmd.extend(["-global_quality", q])
    elif encoder == "h264_amf":
        cmd.extend(["-qp_i", q, "-qp_p", q])
    else:
        cmd.extend(["-crf", q])

def background_convert(job_id, session_dir, files_data, output_format, settings_form):
    total_files = len(files_data)
    results = []

    out_fmt_obj = next((f for f in FORMATS if f.name == output_format), None)
    out_type    = out_fmt_obj.media_type if out_fmt_obj else "unknown"
    is_animgif  = (output_format == "Animated GIF")

    # Resolve file extension
    ext = output_format.lower()
    if ext == "mpeg-2":      ext = "mpg"
    if ext == "avchd":       ext = "m2ts"
    if ext == "animated gif": ext = "gif"

    try:
        for index, (orig_name, in_path, out_path, out_filename) in enumerate(files_data):
            duration = get_duration(in_path)

            # ---- Clip timing ----
            clip_start_raw = settings_form.get(f"setting_{index}_ClipStart", "").strip()
            clip_end_raw   = settings_form.get(f"setting_{index}_ClipEnd",   "").strip()
            clip_start = float(clip_start_raw) if clip_start_raw else 0.0
            clip_end   = float(clip_end_raw)   if clip_end_raw   else 0.0
            has_clip   = (clip_start > 0 or (clip_end > 0 and clip_end < duration))

            # Build base cmd: fast -ss seek before -i
            cmd = [FFMPEG_CMD, "-y"]
            if has_clip and clip_start > 0:
                cmd.extend(["-ss", f"{clip_start:.4f}"])
            cmd.extend(["-i", in_path])
            if has_clip and clip_end > 0:
                clip_dur = clip_end - clip_start
                if clip_dur > 0:
                    cmd.extend(["-t", f"{clip_dur:.4f}"])

            # ---- Build vf filter chain ----
            vf_parts = []

            crop_raw = settings_form.get(f"setting_{index}_Crop", "").strip()
            if crop_raw and out_type in ["video","image"]:
                parts = crop_raw.split(":")
                if len(parts) == 4:
                    cx, cy, cw, ch = parts
                    vf_parts.append(f"crop={cw}:{ch}:{cx}:{cy}")

            res = settings_form.get(f"setting_{index}_Resolution", "").strip()

            if is_animgif:
                gif_fps = settings_form.get(f"setting_{index}_GIF_FPS", "").strip() or "12"
                vf_parts.append(f"fps={gif_fps}")
                if res:
                    vf_parts.append(f"scale={validate_settings(res,'Resolution')}:flags=lanczos")
                else:
                    vf_parts.append("scale=480:-1:flags=lanczos")
                base_chain = ",".join(vf_parts)
                vf_str = f"{base_chain},split[s0][s1];[s0]palettegen=max_colors=256[p];[s1][p]paletteuse=dither=bayer"
                gif_loop = settings_form.get(f"setting_{index}_GIF_Loop", "").strip() or "0"
                cmd.extend(["-vf", vf_str, "-loop", gif_loop])
            else:
                if res and out_type in ["video","image"]:
                    vf_parts.append(f"scale={validate_settings(res,'Resolution')}")
                if vf_parts:
                    cmd.extend(["-vf", ",".join(vf_parts)])

                # Encoder / quality. Common H.264 containers use a tested GPU
                # encoder when available, otherwise a much faster CPU preset.
                q = settings_form.get(f"setting_{index}_Quality", "").strip()
                qv = validate_settings(q, "Quality") if q else None
                vb = settings_form.get(f"setting_{index}_Video_Bitrate","").strip()
                vbv = validate_settings(vb, "Video Bitrate") if vb else None
                selected_encoder = None

                if out_type == "image" and qv:
                    cmd.extend(["-q:v", qv])
                elif out_type == "video":
                    if output_format in {"MP4", "MOV", "MKV"}:
                        selected_encoder = get_fast_h264_encoder()
                        append_h264_speed_options(cmd, selected_encoder)
                        cmd.extend(["-pix_fmt", "yuv420p", "-c:a", "aac"])
                    elif output_format == "WEBM":
                        cmd.extend(["-c:v", "libvpx-vp9", "-deadline", "good",
                                    "-cpu-used", "5", "-row-mt", "1", "-threads", "0"])

                    if vbv:
                        cmd.extend(["-b:v", vbv])
                    elif selected_encoder:
                        append_video_quality_options(cmd, selected_encoder, qv)
                    elif qv:
                        cmd.extend(["-crf", qv])

                # FPS / audio
                fps = settings_form.get(f"setting_{index}_FPS","").strip()
                if fps and out_type=="video": cmd.extend(["-r", validate_settings(fps,"FPS")])
                ab = settings_form.get(f"setting_{index}_Audio_Bitrate","").strip()
                if ab: cmd.extend(["-b:a", validate_settings(ab,"Audio Bitrate")])
                sr = settings_form.get(f"setting_{index}_Sample_Rate","").strip()
                if sr: cmd.extend(["-ar", validate_settings(sr,"Sample Rate")])

                if output_format in {"MP4", "MOV"}:
                    cmd.extend(["-movflags", "+faststart"])

            cmd.append(out_path)
            print(f"[JOB {job_id[:8]}] CMD: {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd, stderr=subprocess.PIPE,
                universal_newlines=True, startupinfo=make_startupinfo()
            )

            stderr_lines = []
            eff_duration = (clip_end - clip_start) if has_clip and clip_end > 0 else duration
            for line in process.stderr:
                stderr_lines.append(line)
                t = parse_ffmpeg_time(line)
                if t is not None and eff_duration > 0:
                    file_pct  = min(t / eff_duration, 1.0)
                    total_pct = (index + file_pct) / total_files * 100
                    progress_store[job_id]["percent"] = min(round(total_pct, 1), 99.9)

            process.wait()

            if process.returncode != 0:
                err = "".join(stderr_lines[-25:])
                print(f"[JOB {job_id[:8]}] ERROR exit={process.returncode}\n{err}")
                progress_store[job_id].update({"status":"error",
                    "message": f"FFmpeg failed on '{orig_name}' (exit {process.returncode}). Check console."})
                return

            if os.path.exists(in_path): os.remove(in_path)

            if duration == 0 or is_animgif:  # images / gif have no duration progress
                pct = (index + 1) / total_files * 100
                progress_store[job_id]["percent"] = min(round(pct,1), 99.9)

            if os.path.exists(out_path):
                print(f"[JOB {job_id[:8]}] OK → {out_filename}")
                results.append({"original_name": orig_name, "id": out_filename, "ext": ext})
            else:
                progress_store[job_id].update({"status":"error",
                    "message": f"Conversion of '{orig_name}' produced no output. Check console."})
                return

        progress_store[job_id].update({"percent":100, "status":"completed", "results":results})
        print(f"[JOB {job_id[:8]}] Done — {total_files} file(s).")

    except Exception:
        import traceback
        tb = traceback.format_exc()
        print(f"[JOB {job_id[:8]}] EXCEPTION:\n{tb}")
        progress_store[job_id].update({"status":"error", "message": tb.splitlines()[-1]})

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<link rel="icon" href="{{ favicon }}">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fully Local File Converter</title>
<style>
:root{--bg:#0f172a;--panel:#1e293b;--text:#f8fafc;--text-muted:#94a3b8;--primary:#3b82f6;--primary-hover:#2563eb;--success:#10b981;--border:#334155;--item-bg:#334155;--danger:#ef4444;}
[data-theme="light"]{--bg:#f8fafc;--panel:#ffffff;--text:#0f172a;--text-muted:#64748b;--primary:#2563eb;--primary-hover:#1d4ed8;--success:#059669;--border:#cbd5e1;--item-bg:#e2e8f0;--danger:#dc2626;}
*{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',system-ui,sans-serif;}
body{background:var(--bg);color:var(--text);padding:2rem 1rem;transition:background .3s,color .3s;}
.container{max-width:1000px;margin:0 auto;position:relative;}
h1{text-align:center;margin-bottom:.5rem;font-weight:600;}
p.subtitle{text-align:center;color:var(--text-muted);margin-bottom:2rem;}
.theme-toggle{position:absolute;top:0;right:0;background:var(--panel);border:1px solid var(--border);color:var(--text);padding:.5rem 1rem;border-radius:8px;cursor:pointer;font-size:1.2rem;}
.upload-area{border:2px dashed var(--border);border-radius:12px;padding:3rem;text-align:center;cursor:pointer;background:rgba(30,41,59,.1);transition:all .3s;position:relative;}
.upload-area:hover{border-color:var(--primary);}
.upload-area input[type=file]{position:absolute;top:0;left:0;width:100%;height:100%;opacity:0;cursor:pointer;z-index:10;}
.uploaded-files-container{margin-top:1rem;margin-bottom:2rem;}
.file-item{display:flex;justify-content:space-between;align-items:center;background:var(--panel);padding:.75rem 1rem;border-radius:8px;border:1px solid var(--border);margin-bottom:.5rem;}
.file-item-name{font-weight:500;font-size:.95rem;}
.btn-small{padding:.4rem .8rem;background:var(--primary);color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:.9rem;}
.btn-danger{background:var(--danger);}
.clear-block{display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;}
.panels-wrapper{display:flex;gap:1rem;align-items:stretch;margin-bottom:2rem;flex-direction:column;}
@media(min-width:768px){.panels-wrapper{flex-direction:row;align-items:center;}}
.panel{flex:1;background:var(--panel);border-radius:12px;padding:1.5rem;border:1px solid var(--border);}
.panel h3{margin-bottom:1rem;color:var(--primary);font-size:1.1rem;text-transform:uppercase;letter-spacing:1px;}
select{width:100%;padding:.75rem;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:1rem;margin-bottom:1rem;outline:none;cursor:pointer;}
.badge{display:inline-block;padding:.25rem .75rem;border-radius:999px;background:var(--item-bg);font-size:.8rem;margin-bottom:1rem;text-transform:uppercase;}
.desc{font-size:.95rem;line-height:1.5;margin-bottom:1rem;color:var(--text-muted);}
.pros-cons{font-size:.85rem;line-height:1.4;}
.pros{color:#34d399;margin-bottom:.5rem;}
.cons{color:#fb7185;}
.switch-btn{background:var(--border);border:none;color:#fff;width:50px;height:50px;border-radius:50%;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:1.5rem;margin:0 auto;z-index:10;}
.settings-bar{background:var(--panel);border-radius:12px;padding:1.5rem;border:1px solid var(--border);margin-bottom:2rem;display:none;}
.settings-header-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;}
.toggle-all-btn{background:transparent;border:1px solid var(--primary);color:var(--primary);padding:.4rem .8rem;border-radius:6px;cursor:pointer;font-size:.85rem;}
.accordion-group{border:1px solid var(--border);border-radius:8px;margin-bottom:.5rem;overflow:hidden;}
.accordion-header{background:var(--item-bg);padding:.75rem 1rem;cursor:pointer;display:flex;justify-content:space-between;align-items:center;font-weight:600;gap:.5rem;}
.accordion-body{background:var(--bg);padding:1rem;display:flex;gap:1.5rem;overflow-x:auto;border-top:1px solid var(--border);flex-wrap:wrap;}
.setting-item{display:flex;flex-direction:column;min-width:140px;}
.setting-item label{font-size:.85rem;color:var(--text-muted);margin-bottom:.5rem;cursor:help;}
.setting-item input{padding:.5rem;border-radius:6px;border:1px solid var(--border);background:var(--panel);color:var(--text);outline:none;font-weight:600;}
.actions{display:flex;gap:1rem;background:var(--panel);border-radius:12px;padding:1.5rem;border:1px solid var(--border);}
.convert-btn{flex:1;padding:1rem;border:none;border-radius:8px;background:var(--success);color:#fff;font-size:1.1rem;font-weight:600;cursor:pointer;}
.convert-btn:disabled{background:var(--border);cursor:not-allowed;}
.loading-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(15,23,42,.8);display:none;align-items:center;justify-content:center;z-index:1000;flex-direction:column;}
.spinner{border:4px solid var(--border);border-top:4px solid var(--primary);border-radius:50%;width:50px;height:50px;animation:spin 1s linear infinite;margin-bottom:1rem;}
@keyframes spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
.progress-container{width:80%;max-width:400px;background:var(--border);border-radius:10px;height:20px;margin-top:1rem;overflow:hidden;}
#progressBarInner{width:0%;height:100%;background:var(--success);transition:width .3s ease;}
#results_container{display:none;}
.result-item{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem;background:var(--panel);padding:1rem;border-radius:8px;border:1px solid var(--border);margin-bottom:1rem;}
.name-container{flex:1;display:flex;align-items:center;min-width:250px;}
.edit-input{background:var(--bg);color:var(--text);border:1px solid var(--border);padding:.6rem;border-radius:6px;font-size:1rem;font-weight:600;flex:1;outline:none;}
.ext-span{color:var(--text-muted);font-size:1.1rem;margin-left:.5rem;font-weight:600;}
.results-actions{display:flex;gap:1rem;margin-top:2rem;}
/* ---- Preview button + edit badge ---- */
.preview-btn{background:var(--border);border:none;color:var(--text);padding:.3rem .65rem;border-radius:5px;cursor:pointer;font-size:.8rem;white-space:nowrap;flex-shrink:0;}
.preview-btn:hover{background:var(--primary);color:#fff;}
.edit-badge{display:none;margin-left:6px;background:var(--primary);color:#fff;font-size:.7rem;padding:.1rem .45rem;border-radius:999px;white-space:nowrap;flex-shrink:0;}
/* ---- Modal ---- */
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.88);z-index:3000;align-items:center;justify-content:center;padding:1rem;overscroll-behavior:contain;}
.modal-box{background:var(--panel);border-radius:16px;border:1px solid var(--border);width:100%;max-width:860px;max-height:92vh;overflow-y:auto;padding:1.5rem;position:relative;-webkit-overflow-scrolling:touch;overscroll-behavior:contain;}
html.crop-modal-open,body.crop-modal-open{overflow:hidden!important;overscroll-behavior:none!important;}
.modal-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;gap:1rem;}
.modal-header span{font-weight:600;font-size:1rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.modal-close{background:transparent;border:1px solid var(--border);color:var(--text);width:36px;height:36px;border-radius:8px;cursor:pointer;font-size:1.2rem;flex-shrink:0;}
.preview-zone{background:#000;border-radius:8px;overflow:hidden;text-align:center;position:relative;margin-bottom:1rem;min-height:120px;display:flex;align-items:center;justify-content:center;}
.image-crop-zone{overflow:visible;padding:28px;touch-action:none;overscroll-behavior:none;-webkit-user-select:none;user-select:none;}
.crop-canvas-shell{position:relative;display:inline-block;max-width:100%;line-height:0;overflow:visible;touch-action:none;overscroll-behavior:none;}
.video-crop-shell{display:none;margin:.5rem auto 0;}
.crop-canvas{cursor:crosshair;display:block;width:100%;height:auto;max-width:100%;touch-action:none;overscroll-behavior:none;-webkit-user-select:none;user-select:none;}
.crop-touch-layer{position:absolute;inset:0;z-index:20;overflow:visible;touch-action:none;overscroll-behavior:none;-webkit-user-select:none;user-select:none;cursor:move;}
.crop-touch-rect{position:absolute;border:2px solid rgba(255,255,255,.9);box-shadow:0 0 0 1px rgba(0,0,0,.45);pointer-events:none;}
.crop-touch-handle{position:absolute;width:48px;height:48px;transform:translate(-50%,-50%);border:0;background:transparent;padding:0;margin:0;z-index:22;touch-action:none;-webkit-user-select:none;user-select:none;}
.crop-touch-handle::after{content:'';position:absolute;left:50%;top:50%;width:14px;height:14px;transform:translate(-50%,-50%);border-radius:50%;background:#fff;border:2px solid #1f2937;box-shadow:0 1px 5px rgba(0,0,0,.65);}
.crop-touch-handle[data-handle=nw],.crop-touch-handle[data-handle=se]{cursor:nwse-resize;}
.crop-touch-handle[data-handle=ne],.crop-touch-handle[data-handle=sw]{cursor:nesw-resize;}
.crop-touch-handle[data-handle=n],.crop-touch-handle[data-handle=s]{cursor:ns-resize;}
.crop-touch-handle[data-handle=e],.crop-touch-handle[data-handle=w]{cursor:ew-resize;}
#previewVideo{max-width:100%;max-height:340px;display:block;}
.capture-btn{background:var(--item-bg);border:1px solid var(--border);color:var(--text);padding:.45rem .9rem;border-radius:6px;cursor:pointer;font-size:.85rem;margin:.5rem 0;}
.capture-btn:hover{background:var(--primary);color:#fff;}
/* ---- Clip timeline ---- */
.clip-section{margin-top:.5rem;}
.clip-section h4{color:var(--primary);font-size:.95rem;margin-bottom:.6rem;}
.clip-timeline{position:relative;height:52px;background:var(--item-bg);border-radius:6px;cursor:pointer;user-select:none;margin-bottom:.75rem;touch-action:none;overscroll-behavior:none;-webkit-user-select:none;}
#clipRange{position:absolute;top:4px;bottom:4px;background:var(--primary);opacity:.35;pointer-events:none;border-radius:4px;}
.clip-handle{position:absolute;top:0;height:52px;width:44px;cursor:ew-resize;transform:translateX(-50%);z-index:4;touch-action:none;background:transparent;}
.clip-handle::before{content:'';position:absolute;left:50%;top:4px;bottom:4px;width:13px;transform:translateX(-50%);background:var(--primary);border-radius:4px;box-shadow:0 1px 4px rgba(0,0,0,.35);}
.clip-handle::after{content:'|||';position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);color:rgba(255,255,255,.78);font-size:7px;letter-spacing:-1px;}
#clipPlayhead{position:absolute;top:0;bottom:0;width:2px;background:rgba(255,255,255,.75);pointer-events:none;z-index:3;}
.clip-info{display:flex;gap:1.5rem;align-items:center;flex-wrap:wrap;font-size:.88rem;}
.clip-info>span{display:flex;align-items:center;gap:.4rem;color:var(--text-muted);}
.clip-info input[type=text]{width:110px;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:.3rem .5rem;border-radius:5px;font-family:monospace;font-size:.85rem;}
/* ---- Crop info ---- */
.crop-section h4{color:var(--primary);font-size:.95rem;margin:.75rem 0 .5rem;}
.crop-coords{display:flex;gap:1rem;flex-wrap:wrap;align-items:flex-end;}
.crop-coords>div{display:flex;flex-direction:column;gap:.3rem;}
.crop-coords label{font-size:.78rem;color:var(--text-muted);}
.crop-coords input[type=number]{width:80px;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:.35rem .5rem;border-radius:5px;font-weight:600;}
.crop-hint{font-size:.78rem;color:var(--text-muted);margin-top:.4rem;}
.modal-actions{display:flex;gap:1rem;margin-top:1.25rem;justify-content:flex-end;}
.now-btn{background:transparent;border:1px solid var(--primary);color:var(--primary);padding:.15rem .45rem;border-radius:4px;cursor:pointer;font-size:.75rem;white-space:nowrap;}
.now-btn:hover{background:var(--primary);color:#fff;}
.crop-section-header{display:flex;align-items:center;gap:.6rem;margin:.75rem 0 .5rem;}
.crop-section-header h4{margin:0;color:var(--primary);font-size:.95rem;}
.collapse-btn{background:transparent;border:1px solid var(--border);color:var(--text-muted);padding:.1rem .5rem;border-radius:4px;cursor:pointer;font-size:.75rem;}
.collapse-btn:hover{border-color:var(--primary);color:var(--primary);}
</style>
</head>
<body>

<!-- Loading overlay -->
<div class="loading-overlay" id="loading">
  <div class="spinner"></div>
  <h2 id="loading-text">Processing...</h2>
  <div class="progress-container"><div id="progressBarInner"></div></div>
</div>

<!-- Preview / Edit Modal -->
<div id="previewModal" class="modal-overlay">
  <div class="modal-box">
    <div class="modal-header">
      <span id="modalFileName">preview</span>
      <button class="modal-close" onclick="closePreviewModal()">✕</button>
    </div>

    <!-- Image preview area -->
    <div id="imagePreviewWrap" style="display:none;">
      <div class="preview-zone image-crop-zone" id="imageCropZone">
        <div class="crop-canvas-shell" id="imageCropShell">
          <canvas id="imageCropCanvas" class="crop-canvas"></canvas>
          <div id="imageCropTouchLayer" class="crop-touch-layer" aria-label="Touch crop controls">
            <div id="imageCropTouchRect" class="crop-touch-rect"></div>
            <button type="button" class="crop-touch-handle" data-handle="nw" aria-label="Crop handle nw"></button><button type="button" class="crop-touch-handle" data-handle="n" aria-label="Crop handle n"></button><button type="button" class="crop-touch-handle" data-handle="ne" aria-label="Crop handle ne"></button><button type="button" class="crop-touch-handle" data-handle="e" aria-label="Crop handle e"></button><button type="button" class="crop-touch-handle" data-handle="se" aria-label="Crop handle se"></button><button type="button" class="crop-touch-handle" data-handle="s" aria-label="Crop handle s"></button><button type="button" class="crop-touch-handle" data-handle="sw" aria-label="Crop handle sw"></button><button type="button" class="crop-touch-handle" data-handle="w" aria-label="Crop handle w"></button>
          </div>
        </div>
      </div>
    </div>

    <!-- Video preview area -->
    <div id="videoPreviewWrap" style="display:none;">
      <div class="preview-zone" style="flex-direction:column;">
        <video id="previewVideo" controls></video>
      </div>
      <div style="display:flex;align-items:center;gap:.6rem;margin:.4rem 0 .3rem;">
        <span style="font-size:.9rem;color:var(--text-muted);">Crop preview</span>
        <button type="button" class="collapse-btn" id="videoCropCollapseBtn" onclick="toggleVideoCropCanvas()">▲ Collapse</button>
      </div>
      <div id="videoCropWrap">
        <button type="button" class="capture-btn" onclick="captureVideoFrame()">📷 Capture Current Frame for Crop</button>
        <div class="crop-canvas-shell video-crop-shell" id="videoCropShell">
          <canvas id="videoCropCanvas" class="crop-canvas"></canvas>
          <div id="videoCropTouchLayer" class="crop-touch-layer" aria-label="Video touch crop controls">
            <div id="videoCropTouchRect" class="crop-touch-rect"></div>
            <button type="button" class="crop-touch-handle" data-handle="nw" aria-label="Video crop handle nw"></button><button type="button" class="crop-touch-handle" data-handle="n" aria-label="Video crop handle n"></button><button type="button" class="crop-touch-handle" data-handle="ne" aria-label="Video crop handle ne"></button><button type="button" class="crop-touch-handle" data-handle="e" aria-label="Video crop handle e"></button><button type="button" class="crop-touch-handle" data-handle="se" aria-label="Video crop handle se"></button><button type="button" class="crop-touch-handle" data-handle="s" aria-label="Video crop handle s"></button><button type="button" class="crop-touch-handle" data-handle="sw" aria-label="Video crop handle sw"></button><button type="button" class="crop-touch-handle" data-handle="w" aria-label="Video crop handle w"></button>
          </div>
        </div>
      </div>

      <!-- Clip section -->
      <div class="clip-section">
        <h4>✂️ Clip</h4>
        <div class="clip-timeline" id="clipTimeline">
          <div id="clipRange"></div>
          <div class="clip-handle" id="clipStartHandle" data-clip-handle="start" role="slider" aria-label="Clip start" style="left:0%"></div>
          <div class="clip-handle" id="clipEndHandle" data-clip-handle="end" role="slider" aria-label="Clip end" style="left:100%"></div>
          <div id="clipPlayhead" style="left:0%"></div>
        </div>
        <div class="clip-info">
          <span>Start: <input type="text" id="clipStartInput" value="00:00:00.00" onchange="onClipInputChange()"> <button type="button" class="now-btn" onclick="setClipToCurrentTime('start')" title="Set to current playback position">▶ Now</button></span>
          <span>End: <input type="text" id="clipEndInput" value="00:00:00.00" onchange="onClipInputChange()"> <button type="button" class="now-btn" onclick="setClipToCurrentTime('end')" title="Set to current playback position">▶ Now</button></span>
          <span style="color:var(--text);">Clip length: <strong id="clipDuration">—</strong></span>
        </div>
      </div>
      <div style="margin-top:.5rem;">
        <button type="button" class="capture-btn" id="cropPreviewBtn" onclick="toggleVideoCropPreview()" style="margin:0;">👁 Preview Crop</button>
      </div>
    </div>

    <!-- Crop section (both types) -->
    <div class="crop-section">
      <div class="crop-section-header">
        <h4>🖼️ Crop</h4>
      </div>
      <div id="cropSectionBody">
        <div class="crop-coords">
          <div><label>X (left)</label><input type="number" id="cropX" min="0" value="0" onchange="onCropInputChange()"></div>
          <div><label>Y (top)</label><input type="number" id="cropY" min="0" value="0"  onchange="onCropInputChange()"></div>
          <div><label>Width</label><input  type="number" id="cropW" min="1" value="0"  onchange="onCropInputChange()"></div>
          <div><label>Height</label><input type="number" id="cropH" min="1" value="0"  onchange="onCropInputChange()"></div>
        </div>
        <p class="crop-hint">Drag the handles on the preview above. For video, capture a frame first, then drag to set crop.</p>
      </div>
    </div>

    <div class="modal-actions">
      <button type="button" class="btn-small btn-danger" onclick="resetEdits()">↺ Reset</button>
      <button type="button" onclick="applyEdits()" style="padding:.6rem 1.6rem;background:var(--success);color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:600;font-size:.95rem;">✓ Apply</button>
    </div>
  </div>
</div>

<!-- Main UI -->
<div class="container">
  <button class="theme-toggle" id="themeToggle" title="Toggle Mode">☀️</button>
  <h1>Fully Local File Converter</h1>
  <p class="subtitle">Powered by FFmpeg</p>

  <form id="convertForm">
    <div class="upload-area" id="dropzone">
      <input type="file" id="fileInput" name="file" multiple>
      <p style="font-size:1.2rem;margin-bottom:.5rem;">📁 Drop files here or click to browse</p>
      <p style="color:var(--text-muted);font-size:.9rem;">All processing is 100% local — nothing leaves your computer.</p>
    </div>

    <div class="uploaded-files-container" id="uploadedFilesContainer" style="display:none;">
      <div class="clear-block">
        <span id="fileCount">0</span> file(s) selected
        <button type="button" class="btn-small btn-danger" id="clearFilesBtn">Clear All</button>
      </div>
      <div id="uploadedFilesList"></div>
    </div>

    <div class="panels-wrapper">
      <div class="panel" id="input_panel">
        <h3>Input Format</h3>
        <select id="input_format"><option value="">Select Format...</option></select>
        <div id="input_details" style="display:none;">
          <span class="badge" id="input_media"></span>
          <p class="desc" id="input_desc"></p>
          <div class="pros-cons">
            <p class="pros" id="input_pros"></p>
            <p class="cons" id="input_cons"></p>
          </div>
        </div>
      </div>
      <button type="button" class="switch-btn" id="switchBtn" title="Swap formats">⇄</button>
      <div class="panel" id="output_panel">
        <h3>Output Format</h3>
        <select id="output_format" disabled><option value="">Select Format...</option></select>
        <div id="output_details" style="display:none;">
          <span class="badge" id="output_media"></span>
          <p class="desc" id="output_desc"></p>
          <div class="pros-cons">
            <p class="pros" id="output_pros"></p>
            <p class="cons" id="output_cons"></p>
          </div>
        </div>
      </div>
    </div>

    <div class="settings-bar" id="settings_container">
      <div class="settings-header-top">
        <h3 style="margin:0;color:var(--primary);font-size:1.1rem;text-transform:uppercase;letter-spacing:1px;">Output Settings</h3>
        <button type="button" class="toggle-all-btn" id="toggleAllBtn">Expand All</button>
      </div>
      <div id="settings_fields"></div>
    </div>

    <div class="actions">
      <button type="submit" class="convert-btn" id="submitBtn" disabled>CONVERT FILES</button>
    </div>
  </form>

  <div id="results_container">
    <h2>Conversion Complete</h2>
    <p class="subtitle">Rename files below before downloading.</p>
    <div id="results_list"></div>
    <div class="results-actions">
      <button type="button" class="convert-btn" id="convertMoreBtn" style="background:var(--primary);">Convert More Files</button>
      <button type="button" class="convert-btn" id="downloadAllBtn" style="max-width:260px;">Download All (ZIP)</button>
    </div>
  </div>
</div>

<script>
const formatsDB   = {{ formats_json | safe }};
const settingHelp = {{ setting_help | safe }};

let selectedFiles = [];
let fileDefaults  = [];
let fileEdits     = {};   // { index: { crop, clip } }
let currentResults = [];
let isExpandAll   = false;

window.addEventListener('beforeunload', () => {
    navigator.sendBeacon('/reset/' + session_id);
});

const fileInput       = document.getElementById('fileInput');
const inputFormatSel  = document.getElementById('input_format');
const outputFormatSel = document.getElementById('output_format');
const switchBtn       = document.getElementById('switchBtn');
const settingsContainer = document.getElementById('settings_container');
const settingsFields  = document.getElementById('settings_fields');
const submitBtn       = document.getElementById('submitBtn');
const clearFilesBtn   = document.getElementById('clearFilesBtn');
const themeToggle     = document.getElementById('themeToggle');
const toggleAllBtn    = document.getElementById('toggleAllBtn');

themeToggle.addEventListener('click', () => {
    const html = document.documentElement;
    html.setAttribute('data-theme', html.getAttribute('data-theme')==='dark'?'light':'dark');
    themeToggle.innerText = html.getAttribute('data-theme')==='dark'?'☀️':'🌙';
});

function populateSelects(targetSel, filterMedia=null) {
    targetSel.innerHTML = '<option value="">Select Format...</option>';
    formatsDB.forEach(f => {
        if (!filterMedia || filterMedia.includes(f.media_type)) {
            let opt = document.createElement('option');
            opt.value = f.name; opt.innerText = f.name;
            targetSel.appendChild(opt);
        }
    });
}

function probeInBrowser(file) {
    const ext = (file.name.split('.').pop() || '').toLowerCase();
    const imageExts = new Set(['jpg','jpeg','jfif','png','webp','gif','bmp','tif','tiff','avif','heic','heif']);
    const videoExts = new Set(['mp4','mov','m4v','mkv','avi','webm','wmv','flv','mpg','mpeg','ts','mts','m2ts','3gp']);

    if (imageExts.has(ext) && 'createImageBitmap' in window) {
        return createImageBitmap(file).then(bitmap => {
            const meta = {Resolution: `${bitmap.width}x${bitmap.height}`};
            bitmap.close();
            return meta;
        }).catch(() => ({}));
    }

    if (videoExts.has(ext)) {
        return new Promise(resolve => {
            const video = document.createElement('video');
            const url = URL.createObjectURL(file);
            let settled = false;
            const finish = meta => {
                if (settled) return;
                settled = true;
                URL.revokeObjectURL(url);
                video.removeAttribute('src');
                resolve(meta);
            };
            video.preload = 'metadata';
            video.muted = true;
            video.onloadedmetadata = () => finish(
                video.videoWidth && video.videoHeight
                    ? {Resolution: `${video.videoWidth}x${video.videoHeight}`}
                    : {}
            );
            video.onerror = () => finish({});
            video.src = url;
            setTimeout(() => finish({}), 8000);
        });
    }

    return Promise.resolve({});
}

async function probeFileDefaults(file, index) {
    // Populate dimensions immediately without uploading the file.
    const localMeta = await probeInBrowser(file);
    fileDefaults[index] = {...(fileDefaults[index] || {}), ...localMeta};
    if (outputFormatSel.value) renderSettings();

    // FFprobe needs a complete MP4/MOV file because its metadata can be at the
    // end. Never send a truncated first chunk: it produces the reported error.
    const fullProbeLimit = {{ probe_full_upload_limit_bytes }};
    if (file.size > fullProbeLimit) return;

    try {
        const fd = new FormData();
        fd.append('file', file, file.name);
        const res = await fetch('/probe', {method:'POST', body:fd});
        if (res.ok) {
            const serverMeta = await res.json();
            fileDefaults[index] = {...(fileDefaults[index] || {}), ...serverMeta};
            if (outputFormatSel.value) renderSettings();
        }
    } catch(e) { console.warn('Optional metadata probe failed:', e); }
}

function updateDetails(type) {
    const sel = type==='input' ? inputFormatSel : outputFormatSel;
    const fmt = formatsDB.find(f=>f.name===sel.value);
    if (!fmt) return;
    document.getElementById(type+'_details').style.display = 'block';
    document.getElementById(type+'_media').innerText = fmt.media_type;
    document.getElementById(type+'_desc').innerText  = fmt.desc;
    document.getElementById(type+'_pros').innerText  = '+ '+fmt.pros;
    document.getElementById(type+'_cons').innerText  = '- '+fmt.cons;

    if (type === 'input') {
        const validMedias = fmt.media_type==='image' ? ['image'] :
                            fmt.media_type==='audio' ? ['audio'] : ['video','audio'];
        const prev = outputFormatSel.value;
        populateSelects(outputFormatSel, validMedias);
        outputFormatSel.disabled = false;
        if ([...outputFormatSel.options].some(o=>o.value===prev)) {
            outputFormatSel.value = prev; updateDetails('output');
        } else {
            document.getElementById('output_details').style.display = 'none';
            settingsContainer.style.display = 'none';
            submitBtn.disabled = true;
        }
    }
    if (type==='output') { submitBtn.disabled=false; renderSettings(); }
}

toggleAllBtn.addEventListener('click', () => {
    isExpandAll = !isExpandAll;
    toggleAllBtn.innerText = isExpandAll ? 'Collapse All' : 'Expand All';
    document.querySelectorAll('.accordion-body').forEach(el=>el.style.display=isExpandAll?'flex':'none');
    document.querySelectorAll('.accordion-header .arrow').forEach(el=>el.innerText=isExpandAll?'▲':'▼');
});

function renderSettings() {
    const fmt = formatsDB.find(f=>f.name===outputFormatSel.value);
    if (!fmt || selectedFiles.length===0) {
        settingsContainer.style.display='none'; return;
    }

    // Resolution is controlled through Preview & Edit, so it is not a visible
    // accordion setting. Base expand/collapse behaviour on settings that are
    // actually rendered, otherwise an empty arrow/body is shown.
    const visibleSettings = fmt.settings.filter(s => s !== 'Resolution');
    const hasExpandableSettings = visibleSettings.length > 0;

    settingsContainer.style.display = 'block';
    settingsFields.innerHTML = '';
    toggleAllBtn.style.display = hasExpandableSettings ? 'inline-block' : 'none';
    if (!hasExpandableSettings) {
        isExpandAll = false;
        toggleAllBtn.innerText = 'Expand All';
    }

    selectedFiles.forEach((file, index) => {
        const grp = document.createElement('div');
        grp.className = 'accordion-group';

        const header = document.createElement('div');
        header.className = 'accordion-header';
        header.style.cursor = hasExpandableSettings ? 'pointer' : 'default';
        const hasEdit = fileEdits[index] && (fileEdits[index].crop || fileEdits[index].clip);
        header.innerHTML = `
            <div style="display:flex;align-items:center;gap:.5rem;flex:1;min-width:0;overflow:hidden;">
              <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${file.name}</span>
              <span class="edit-badge" id="editBadge_${index}" style="display:${hasEdit?'inline-block':'none'}">✓ edited</span>
            </div>
            <div style="display:flex;align-items:center;gap:.5rem;flex-shrink:0;">
              <button type="button" class="preview-btn" onclick="event.stopPropagation();openPreviewModal(${index})">🔍 Preview &amp; Edit</button>
              ${hasExpandableSettings ? `<span class="arrow">${isExpandAll?'▲':'▼'}</span>` : ''}
            </div>`;

        grp.appendChild(header);

        if (hasExpandableSettings) {
            const body = document.createElement('div');
            body.className = 'accordion-body';
            body.style.display = isExpandAll ? 'flex' : 'none';
            header.onclick = () => {
                const hidden = body.style.display==='none';
                body.style.display = hidden?'flex':'none';
                header.querySelector('.arrow').innerText = hidden?'▲':'▼';
            };

            visibleSettings.forEach(s => {
                let val = (fileDefaults[index]&&fileDefaults[index][s]) ? fileDefaults[index][s] : '';
                if (!val) {
                    if (s==='Quality')     val = outputFormatSel.value.match(/JPEG|JPG|WEBP|AVIF|HEIC/)?'80':'23';
                    if (s==='Sample Rate') val = '44100';
                    if (s==='Audio Bitrate') val = '192k';
                    if (s==='GIF FPS')     val = '12';
                }
                const helpText = settingHelp[s] || '';
                const div = document.createElement('div');
                div.className = 'setting-item';
                if(s === 'GIF Loop'){
                    div.innerHTML = `<label title="${helpText}">GIF Loop ℹ️</label>
                        <select name="setting_${index}_GIF_Loop" style="padding:.5rem;border-radius:6px;border:1px solid var(--border);background:var(--panel);color:var(--text);font-weight:600;outline:none;">
                          <option value="0">Loop forever</option>
                          <option value="1">Play once</option>
                        </select>`;
                } else {
                    div.innerHTML = `
                    <label title="${helpText}">${s} ℹ️</label>
                    <input type="text" title="${helpText}"
                           name="setting_${index}_${s.replace(/ /g,'_')}"
                           value="${val}" placeholder="Default">`;
                }
                body.appendChild(div);
            });

            grp.appendChild(body);
        }
        settingsFields.appendChild(grp);
    });
}

function renderFileList() {
    const list = document.getElementById('uploadedFilesList');
    list.innerHTML = '';
    if (selectedFiles.length===0) {
        document.getElementById('uploadedFilesContainer').style.display='none';
        clearFilesBtn.click(); return;
    }
    document.getElementById('uploadedFilesContainer').style.display='block';
    document.getElementById('fileCount').innerText = selectedFiles.length;
    selectedFiles.forEach((file, index) => {
        const div = document.createElement('div');
        div.className = 'file-item';
        div.innerHTML = `<span class="file-item-name">${file.name}</span>
            <button type="button" class="btn-small btn-danger" onclick="removeSelectedFile(${index})">✕</button>`;
        list.appendChild(div);
    });
}

window.removeSelectedFile = function(index) {
    selectedFiles.splice(index,1); fileDefaults.splice(index,1);
    delete fileEdits[index];
    renderFileList(); if (outputFormatSel.value) renderSettings();
};

fileInput.addEventListener('change', e => {
    const newFiles = Array.from(e.target.files);
    fileInput.value = '';
    if (!newFiles.length) return;

    const firstExt = (selectedFiles.length>0 ? selectedFiles[0] : newFiles[0]).name.split('.').pop().toUpperCase();
    const allMatch = newFiles.every(f => {
        let ex = f.name.split('.').pop().toUpperCase();
        return (ex==='JPG'?'JPEG':ex) === (firstExt==='JPG'?'JPEG':firstExt);
    });
    if (!allMatch) { alert('All files must be the same format.'); return; }

    const isFirst = selectedFiles.length===0;
    const startIdx = selectedFiles.length;
    selectedFiles.push(...newFiles);
    renderFileList();
    newFiles.forEach((f,i)=>{ fileDefaults.push({}); probeFileDefaults(f, startIdx+i); });

    if (isFirst) {
        populateSelects(inputFormatSel);
        let ext = firstExt==='JPG'?'JPEG':firstExt;
        let matched = formatsDB.find(f=>f.name===ext || f.name.replace('-','')===ext);
        if (matched) { inputFormatSel.value=matched.name; updateDetails('input'); }
        else { alert('Extension unrecognized — select Input Format manually.'); inputFormatSel.disabled=false; }
        inputFormatSel.disabled=true; switchBtn.disabled=true;
    }
});

clearFilesBtn.addEventListener('click', () => {
    selectedFiles=[]; fileDefaults=[]; fileEdits={};
    renderFileList();
    inputFormatSel.disabled=false; switchBtn.disabled=false;
    populateSelects(inputFormatSel);
    inputFormatSel.value=''; outputFormatSel.value='';
    ['input_details','output_details'].forEach(id=>document.getElementById(id).style.display='none');
    submitBtn.disabled=true; settingsContainer.style.display='none';
});

outputFormatSel.addEventListener('change', ()=>updateDetails('output'));
inputFormatSel.addEventListener('change', ()=>updateDetails('input'));
switchBtn.addEventListener('click', ()=>{
    if (selectedFiles.length>0) return;
    const ti=inputFormatSel.value, to=outputFormatSel.value;
    if (!ti||!to) return;
    populateSelects(inputFormatSel); inputFormatSel.value=to; updateDetails('input');
    if ([...outputFormatSel.options].some(o=>o.value===ti)) { outputFormatSel.value=ti; updateDetails('output'); }
});

// =====================================================================
// SUBMIT
// =====================================================================
// crypto.randomUUID() is normally unavailable on plain HTTP LAN origins
// (for example http://192.168.x.x), even though it works on localhost.
// If it throws here, the submit listener below is never attached and the
// browser performs a normal form submission, which looks like a page reload.
function createSessionId() {
    if (globalThis.crypto && typeof globalThis.crypto.randomUUID === 'function') {
        return globalThis.crypto.randomUUID();
    }

    const bytes = new Uint8Array(16);
    if (globalThis.crypto && typeof globalThis.crypto.getRandomValues === 'function') {
        globalThis.crypto.getRandomValues(bytes);
    } else {
        // Last-resort compatibility fallback for older/insecure LAN browsers.
        for (let i = 0; i < bytes.length; i++) {
            bytes[i] = Math.floor(Math.random() * 256);
        }
    }

    // RFC 4122 version 4 UUID bits.
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0'));
    return `${hex.slice(0,4).join('')}-${hex.slice(4,6).join('')}-${hex.slice(6,8).join('')}-${hex.slice(8,10).join('')}-${hex.slice(10,16).join('')}`;
}

const session_id = createSessionId();

document.getElementById('convertForm').addEventListener('submit', async e => {
    e.preventDefault();
    const formData = new FormData();
    formData.append('session_id', session_id);
    formData.append('output_format', outputFormatSel.value);

    // Attach files from JS array (file input was cleared after selection)
    selectedFiles.forEach((file, index) => {
        formData.append('file', file, file.name);
        const edits = fileEdits[index] || {};
        if (edits.crop) {
            const {x,y,w,h} = edits.crop;
            formData.append(`setting_${index}_Crop`, `${x}:${y}:${w}:${h}`);
        }
        if (edits.clip) {
            if (edits.clip.start > 0)
                formData.append(`setting_${index}_ClipStart`, edits.clip.start.toFixed(4));
            formData.append(`setting_${index}_ClipEnd`, edits.clip.end.toFixed(4));
        }
    });
    // Append remaining settings inputs
    new FormData(e.target).forEach((val, key) => {
        if (key!=='file' && key!=='output_format') formData.append(key, val);
    });

    document.getElementById('progressBarInner').style.width = '0%';
    document.getElementById('loading-text').innerText = 'Uploading & Starting...';
    document.getElementById('loading').style.display  = 'flex';

    try {
        const res = await fetch('/convert', {method:'POST', body:formData});
        if (!res.ok) {
            const detail = await res.text();
            throw new Error(`Server returned ${res.status}: ${detail || res.statusText}`);
        }
        const payload = await res.json();
        if (!payload.job_id) throw new Error('Server did not return a conversion job ID.');
        const job_id = payload.job_id;

        const poll = setInterval(async () => {
            try {
                const statusRes = await fetch('/status/'+encodeURIComponent(job_id), {cache:'no-store'});
                if (!statusRes.ok) throw new Error(`Status request failed (${statusRes.status})`);
                const s = await statusRes.json();
            if (s.status==='processing'||s.status==='completed') {
                document.getElementById('progressBarInner').style.width = s.percent+'%';
                document.getElementById('loading-text').innerText = 'Converting: '+s.percent+'%';
            }
            if (s.status==='completed') {
                clearInterval(poll);
                const finalResults = s.results.map(r=>({...r, id:`${session_id}/${r.id.split('/').pop()}`}));
                showResults(finalResults);
                document.getElementById('loading').style.display='none';
            }
                if (s.status==='error') {
                    clearInterval(poll);
                    alert('Error: '+s.message);
                    document.getElementById('loading').style.display='none';
                }
                if (s.status==='not_found') {
                    throw new Error('Conversion job was not found on the server.');
                }
            } catch (pollError) {
                clearInterval(poll);
                console.error(pollError);
                alert('Lost contact with the converter: '+pollError.message);
                document.getElementById('loading').style.display='none';
            }
        }, 1000);
    } catch(err) {
        console.error(err);
        alert('Failed to start conversion: '+err.message);
        document.getElementById('loading').style.display='none';
    }
});

function showResults(data) {
    document.getElementById('convertForm').style.display='none';
    document.getElementById('results_container').style.display='block';
    currentResults = data; renderResultsList();
}

function renderResultsList() {
    const list = document.getElementById('results_list');
    list.innerHTML = '';
    if (!currentResults.length) {
        document.getElementById('downloadAllBtn').disabled=true;
        list.innerHTML='<p style="color:var(--text-muted)">All files removed.</p>'; return;
    }
    document.getElementById('downloadAllBtn').disabled=false;
    currentResults.forEach((item,idx)=>{
        const div=document.createElement('div');
        div.className='result-item';
        div.innerHTML=`
            <div class="name-container">
                <input type="text" class="edit-input" value="${item.original_name}"
                       onchange="currentResults[${idx}].original_name=this.value.trim()||'converted'">
                <span class="ext-span">.${item.ext}</span>
            </div>
            <div style="display:flex;gap:.5rem;">
                <button type="button" class="btn-small" onclick="downloadSingle(${idx})">Download</button>
                <button type="button" class="btn-small btn-danger" onclick="removeResult(${idx})">Remove</button>
            </div>`;
        list.appendChild(div);
    });
}

window.downloadSingle = function(idx) {
    const item=currentResults[idx];
    const a=document.createElement('a');
    a.href=`/download/${item.id}?name=${encodeURIComponent(item.original_name)}`;
    a.download=''; document.body.appendChild(a); a.click(); document.body.removeChild(a);
};
window.removeResult = function(idx) { currentResults.splice(idx,1); renderResultsList(); };

document.getElementById('downloadAllBtn').addEventListener('click', async () => {
    if (!currentResults.length) return;
    const btn=document.getElementById('downloadAllBtn');
    btn.innerText='Zipping...'; btn.disabled=true;
    try {
        const res=await fetch('/download_all',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(currentResults)});
        const blob=await res.blob();
        const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
        a.download='converted_files.zip'; document.body.appendChild(a); a.click(); a.remove();
    } catch(e){alert('Error creating ZIP.');}
    btn.innerText='Download All (ZIP)'; btn.disabled=false;
});

document.getElementById('convertMoreBtn').addEventListener('click', ()=>{
    fetch('/reset/'+session_id, {method:'POST'});
    document.getElementById('results_container').style.display='none';
    document.getElementById('convertForm').style.display='block';
    clearFilesBtn.click();
});

// =====================================================================
// PREVIEW MODAL — CROP & CLIP
// =====================================================================
const VIDEO_EXTS = new Set(['mp4','mov','avi','mkv','webm','wmv','flv','m4v','mpg','mpeg','ts','mts','m2ts','3gp']);

let modal = {
    fileIndex:-1, mediaType:null,
    naturalW:0, naturalH:0, videoDuration:0,
    objectUrl:null,
    cropState:{x:0,y:0,w:0,h:0},
    clipState:{start:0,end:0},
    isDragging:false, dragType:null, dragStart:{},
    isClipDrag:false, clipDragType:null,
    capturedImg:null,
    dpr:1, activeCropCanvas:null, _docCropHandlersAdded:false,
    activePointerId:null, clipPointerId:null, clipTimelineBound:false, documentTouchGuardBound:false, pageScrollLocked:false,
    savedPageScrollY:0, savedBodyStyles:null,
};
let cropPreviewActive = false;

function openPreviewModal(index) {
    const file = selectedFiles[index];
    if (!file) return;
    modal.fileIndex = index;
    if (modal.objectUrl) URL.revokeObjectURL(modal.objectUrl);
    modal.objectUrl = URL.createObjectURL(file);
    modal.capturedImg = null;
    const ext = file.name.split('.').pop().toLowerCase();
    modal.mediaType = VIDEO_EXTS.has(ext) ? 'video' : 'image';
    document.getElementById('modalFileName').textContent = file.name;
    lockPageBehindCropModal();
    document.getElementById('previewModal').style.display = 'flex';
    const existing = fileEdits[index] || {};
    if (modal.mediaType==='video') initVideoPreview(existing);
    else initImagePreview(existing);
}

function initImagePreview(existing) {
    document.getElementById('videoPreviewWrap').style.display = 'none';
    document.getElementById('imagePreviewWrap').style.display = 'block';
    const img = new Image();
    img.onload = () => {
        modal.naturalW=img.naturalWidth; modal.naturalH=img.naturalHeight;
        modal.cropState = existing.crop ? {...existing.crop} : {x:0,y:0,w:img.naturalWidth,h:img.naturalHeight};
        modal.capturedImg = img;
        const canvas = document.getElementById('imageCropCanvas');
        sizeCropCanvas(canvas, img.naturalWidth, img.naturalHeight);
        drawCrop(canvas); syncCropInputs();
        setupCropEvents(canvas);
    };
    img.src = modal.objectUrl;
}

function initVideoPreview(existing) {
    document.getElementById('imagePreviewWrap').style.display = 'none';
    document.getElementById('videoPreviewWrap').style.display = 'block';
    document.getElementById('videoCropShell').style.display = 'none';
    const video = document.getElementById('previewVideo');
    video.src = modal.objectUrl; video.load();
    video.onloadedmetadata = () => {
        modal.naturalW=video.videoWidth; modal.naturalH=video.videoHeight;
        modal.videoDuration=video.duration;
        modal.cropState = existing.crop ? {...existing.crop} : {x:0,y:0,w:video.videoWidth,h:video.videoHeight};
        modal.clipState = existing.clip ? {...existing.clip} : {start:0,end:video.duration};
        syncCropInputs(); syncClipTimeline(); syncClipInputs();
    };
    setupClipTimeline();
}

function captureVideoFrame() {
    const video = document.getElementById('previewVideo');
    if (!video.src || !video.videoWidth || !video.videoHeight) return;
    const canvas = document.getElementById('videoCropCanvas');
    const shell = document.getElementById('videoCropShell');
    sizeCropCanvas(canvas, video.videoWidth, video.videoHeight);
    shell.style.display = 'inline-block';
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    // Bake the current frame into an image so crop redraws are stable while the video plays.
    const frameImg = new Image();
    frameImg.src = canvas.toDataURL();
    frameImg.onload = () => {
        modal.capturedImg = frameImg;
        drawCrop(canvas); syncCropInputs();
        setupCropEvents(canvas);
    };
}

function sizeCropCanvas(canvas, nw, nh) {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const modalBox = document.querySelector('.modal-box');
    const maxW = Math.min(Math.max(160, modalBox.clientWidth - 72), 800);
    const maxH = Math.min(window.innerHeight * 0.5, 480);
    const scale = Math.min(maxW/nw, maxH/nh, 1);
    const cssW = Math.max(1, Math.round(nw * scale));
    const cssH = Math.max(1, Math.round(nh * scale));
    canvas.width  = Math.max(1, Math.round(cssW * dpr));
    canvas.height = Math.max(1, Math.round(cssH * dpr));
    canvas.style.width = '100%';
    canvas.style.height = 'auto';
    const shell = canvas.closest('.crop-canvas-shell');
    if (shell) {
        shell.style.width = cssW + 'px';
        shell.style.maxWidth = '100%';
        shell.style.aspectRatio = `${nw} / ${nh}`;
    }
    modal.dpr = dpr;
}

// ---- Crop drawing ----
function drawCrop(canvas) {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const cw=canvas.width, ch=canvas.height;
    const nw=modal.naturalW, nh=modal.naturalH;
    ctx.clearRect(0,0,cw,ch);
    if (modal.capturedImg) ctx.drawImage(modal.capturedImg,0,0,cw,ch);

    const {x,y,w,h} = modal.cropState;
    const sx=x/nw*cw, sy=y/nh*ch, sw=w/nw*cw, sh=h/nh*ch;

    // Dark mask
    ctx.fillStyle='rgba(0,0,0,.56)';
    ctx.fillRect(0,0,cw,sy);
    ctx.fillRect(0,sy+sh,cw,ch-sy-sh);
    ctx.fillRect(0,sy,sx,sh);
    ctx.fillRect(sx+sw,sy,cw-sx-sw,sh);

    const dpr = modal.dpr || 1;

    // Border
    ctx.strokeStyle='#fff'; ctx.lineWidth=1.5*dpr;
    ctx.strokeRect(sx,sy,sw,sh);

    // Rule of thirds
    ctx.strokeStyle='rgba(255,255,255,.22)'; ctx.lineWidth=0.7*dpr;
    for (let i=1;i<3;i++){
        ctx.beginPath();ctx.moveTo(sx+sw*i/3,sy);ctx.lineTo(sx+sw*i/3,sy+sh);ctx.stroke();
        ctx.beginPath();ctx.moveTo(sx,sy+sh*i/3);ctx.lineTo(sx+sw,sy+sh*i/3);ctx.stroke();
    }

    // Handles
    const hs = 5*dpr;
    handles(sx,sy,sw,sh).forEach(h=>{
        ctx.fillStyle='#fff'; ctx.strokeStyle='#444'; ctx.lineWidth=dpr;
        ctx.fillRect(h.cx-hs,h.cy-hs,hs*2,hs*2); ctx.strokeRect(h.cx-hs,h.cy-hs,hs*2,hs*2);
    });

    updateCropTouchOverlay(canvas);
}

function handles(sx,sy,sw,sh){
    return [{id:'nw',cx:sx,cy:sy},{id:'n',cx:sx+sw/2,cy:sy},{id:'ne',cx:sx+sw,cy:sy},
            {id:'e',cx:sx+sw,cy:sy+sh/2},{id:'se',cx:sx+sw,cy:sy+sh},
            {id:'s',cx:sx+sw/2,cy:sy+sh},{id:'sw',cx:sx,cy:sy+sh},{id:'w',cx:sx,cy:sy+sh/2}];
}

function hitHandle(canvas,mx,my){
    const cw=canvas.width,ch=canvas.height,nw=modal.naturalW,nh=modal.naturalH;
    const {x,y,w,h}=modal.cropState;
    const sx=x/nw*cw,sy=y/nh*ch,sw=w/nw*cw,sh=h/nh*ch;
    const HR = 8*(modal.dpr||1);
    for (const hd of handles(sx,sy,sw,sh))
        if (Math.abs(mx-hd.cx)<HR&&Math.abs(my-hd.cy)<HR) return hd.id;
    if(mx>sx&&mx<sx+sw&&my>sy&&my<sy+sh) return 'move';
    return null;
}

const CURSORS={nw:'nw-resize',n:'n-resize',ne:'ne-resize',e:'e-resize',se:'se-resize',s:'s-resize',sw:'sw-resize',w:'w-resize',move:'move'};

function canvasXY(canvas,e){
    const r=canvas.getBoundingClientRect();
    return {mx:(e.clientX-r.left)*(canvas.width/r.width),my:(e.clientY-r.top)*(canvas.height/r.height)};
}

function lockPageBehindCropModal(){
    if(modal.pageScrollLocked)return;
    modal.pageScrollLocked=true;
    modal.savedPageScrollY=window.scrollY||document.documentElement.scrollTop||0;
    const b=document.body;
    modal.savedBodyStyles={position:b.style.position,top:b.style.top,left:b.style.left,right:b.style.right,width:b.style.width,overflow:b.style.overflow};
    document.documentElement.classList.add('crop-modal-open');
    b.classList.add('crop-modal-open');
    b.style.position='fixed';
    b.style.top=`-${modal.savedPageScrollY}px`;
    b.style.left='0'; b.style.right='0'; b.style.width='100%'; b.style.overflow='hidden';
}

function unlockPageBehindCropModal(){
    if(!modal.pageScrollLocked)return;
    modal.pageScrollLocked=false;
    const b=document.body, old=modal.savedBodyStyles||{};
    document.documentElement.classList.remove('crop-modal-open');
    b.classList.remove('crop-modal-open');
    b.style.position=old.position||''; b.style.top=old.top||''; b.style.left=old.left||'';
    b.style.right=old.right||''; b.style.width=old.width||''; b.style.overflow=old.overflow||'';
    window.scrollTo(0,modal.savedPageScrollY||0);
    modal.savedBodyStyles=null;
}

function cropOverlayElements(canvas){
    const prefix=canvas.id==='videoCropCanvas'?'video':'image';
    return {
        layer:document.getElementById(prefix+'CropTouchLayer'),
        rect:document.getElementById(prefix+'CropTouchRect')
    };
}

function updateCropTouchOverlay(canvas){
    const {layer,rect:rectEl}=cropOverlayElements(canvas);
    if(!layer||!rectEl||!modal.naturalW||!modal.naturalH)return;
    const {x,y,w,h}=modal.cropState;
    const left=x/modal.naturalW*100, top=y/modal.naturalH*100;
    const width=w/modal.naturalW*100, height=h/modal.naturalH*100;
    rectEl.style.left=left+'%'; rectEl.style.top=top+'%'; rectEl.style.width=width+'%'; rectEl.style.height=height+'%';
    const positions={
        nw:[left,top], n:[left+width/2,top], ne:[left+width,top],
        e:[left+width,top+height/2], se:[left+width,top+height],
        s:[left+width/2,top+height], sw:[left,top+height], w:[left,top+height/2]
    };
    layer.querySelectorAll('.crop-touch-handle').forEach(el=>{
        const p=positions[el.dataset.handle];
        if(p){el.style.left=p[0]+'%';el.style.top=p[1]+'%';}
    });
}

function cropDragTypeAt(canvas,target,clientX,clientY){
    const handle=target&&target.closest?target.closest('.crop-touch-handle'):null;
    if(handle)return handle.dataset.handle;
    const r=canvas.getBoundingClientRect();
    if(!r.width||!r.height)return null;
    const nx=(clientX-r.left)/r.width*modal.naturalW;
    const ny=(clientY-r.top)/r.height*modal.naturalH;
    const {x,y,w,h}=modal.cropState;
    return nx>=x&&nx<=x+w&&ny>=y&&ny<=y+h?'move':null;
}

function beginCropDrag(canvas,target,clientX,clientY,pointerId=null){
    const dragType=cropDragTypeAt(canvas,target,clientX,clientY);
    if(!dragType)return false;
    modal.isDragging=true;
    modal.dragType=dragType;
    modal.activeCropCanvas=canvas;
    modal.activePointerId=pointerId;
    modal.dragStart={clientX,clientY,...modal.cropState};
    return true;
}

function moveCropDrag(clientX,clientY){
    if(!modal.isDragging||!modal.activeCropCanvas)return;
    const cv=modal.activeCropCanvas;
    const r=cv.getBoundingClientRect();
    if(!r.width||!r.height)return;
    const nw=modal.naturalW,nh=modal.naturalH;
    const dx=(clientX-modal.dragStart.clientX)/r.width*nw;
    const dy=(clientY-modal.dragStart.clientY)/r.height*nh;
    let {x,y,w,h}=modal.dragStart,dt=modal.dragType;
    if(dt==='move'){
        x=Math.max(0,Math.min(nw-w,x+dx));
        y=Math.max(0,Math.min(nh-h,y+dy));
    }else{
        if(dt.includes('e'))w=Math.max(8,Math.min(nw-x,w+dx));
        if(dt.includes('s'))h=Math.max(8,Math.min(nh-y,h+dy));
        if(dt.includes('w')){const nx=Math.max(0,Math.min(x+w-8,x+dx));w=x+w-nx;x=nx;}
        if(dt.includes('n')){const ny=Math.max(0,Math.min(y+h-8,y+dy));h=y+h-ny;y=ny;}
    }
    modal.cropState={x:Math.round(x),y:Math.round(y),w:Math.round(w),h:Math.round(h)};
    drawCrop(cv); syncCropInputs(); refreshVideoCropPreview();
}

function endCropDrag(){
    modal.isDragging=false; modal.activeCropCanvas=null; modal.activePointerId=null;
}

function setupCropEvents(canvas){
    const {layer}=cropOverlayElements(canvas);
    if(!layer)return;
    updateCropTouchOverlay(canvas);
    if(layer.dataset.cropBound==='1')return;
    layer.dataset.cropBound='1';

    layer.addEventListener('pointerdown',e=>{
        e.preventDefault();e.stopPropagation();
        if(e.isPrimary===false)return;
        if(beginCropDrag(canvas,e.target,e.clientX,e.clientY,e.pointerId)){
            try{layer.setPointerCapture(e.pointerId);}catch(_e){}
        }
    },{passive:false});
    layer.addEventListener('pointermove',e=>{
        if(!modal.isDragging||modal.activeCropCanvas!==canvas||modal.activePointerId!==e.pointerId)return;
        e.preventDefault();e.stopPropagation();moveCropDrag(e.clientX,e.clientY);
    },{passive:false});
    const finishPointer=e=>{
        if(modal.activeCropCanvas!==canvas)return;
        if(modal.activePointerId!==null&&e.pointerId!==modal.activePointerId)return;
        e.preventDefault();e.stopPropagation();endCropDrag();
    };
    layer.addEventListener('pointerup',finishPointer,{passive:false});
    layer.addEventListener('pointercancel',finishPointer,{passive:false});

    // Safari/older WebView fallback when Pointer Events are unavailable.
    layer.addEventListener('touchstart',e=>{
        if(window.PointerEvent)return;
        e.preventDefault();e.stopPropagation();
        const t=e.changedTouches[0];if(t)beginCropDrag(canvas,e.target,t.clientX,t.clientY,'touch');
    },{passive:false});
    layer.addEventListener('touchmove',e=>{
        if(window.PointerEvent||!modal.isDragging||modal.activeCropCanvas!==canvas)return;
        e.preventDefault();e.stopPropagation();
        const t=e.changedTouches[0];if(t)moveCropDrag(t.clientX,t.clientY);
    },{passive:false});
    const finishTouch=e=>{
        if(window.PointerEvent||modal.activeCropCanvas!==canvas)return;
        e.preventDefault();e.stopPropagation();endCropDrag();
    };
    layer.addEventListener('touchend',finishTouch,{passive:false});
    layer.addEventListener('touchcancel',finishTouch,{passive:false});

    // Mouse fallback for older desktop browsers without Pointer Events.
    layer.addEventListener('mousedown',e=>{
        if(window.PointerEvent)return;
        e.preventDefault();e.stopPropagation();beginCropDrag(canvas,e.target,e.clientX,e.clientY,'mouse');
    });
    document.addEventListener('mousemove',e=>{
        if(window.PointerEvent||!modal.isDragging||modal.activeCropCanvas!==canvas)return;
        e.preventDefault();moveCropDrag(e.clientX,e.clientY);
    });
    document.addEventListener('mouseup',()=>{
        if(!window.PointerEvent&&modal.activeCropCanvas===canvas)endCropDrag();
    });

    if(!modal.documentTouchGuardBound){
        modal.documentTouchGuardBound=true;
        document.addEventListener('touchmove',e=>{
            if(modal.isDragging||modal.isClipDrag){e.preventDefault();e.stopPropagation();}
        },{capture:true,passive:false});
    }
}

function syncCropInputs(){
    const{x,y,w,h}=modal.cropState;
    ['X','Y','W','H'].forEach((k,i)=>document.getElementById('crop'+k).value=[x,y,w,h][i]);
}

function onCropInputChange(){
    const x=clamp(parseInt(document.getElementById('cropX').value)||0,0,modal.naturalW-1);
    const y=clamp(parseInt(document.getElementById('cropY').value)||0,0,modal.naturalH-1);
    const w=clamp(parseInt(document.getElementById('cropW').value)||modal.naturalW,1,modal.naturalW-x);
    const h=clamp(parseInt(document.getElementById('cropH').value)||modal.naturalH,1,modal.naturalH-y);
    modal.cropState={x,y,w,h};
    const c=document.getElementById('imageCropCanvas');
    const vc=document.getElementById('videoCropCanvas');
    if(c.width)drawCrop(c); if(document.getElementById('videoCropShell').style.display!=='none')drawCrop(vc);
}
function clamp(v,lo,hi){return Math.max(lo,Math.min(hi,v));}

// ---- Clip Timeline ----
function setupClipTimeline(){
    if(modal.clipTimelineBound)return;
    modal.clipTimelineBound=true;
    const tl=document.getElementById('clipTimeline');
    const vid=document.getElementById('previewVideo');

    function fractionAt(clientX){
        const r=tl.getBoundingClientRect();
        return Math.max(0,Math.min(1,(clientX-r.left)/Math.max(r.width,1)));
    }
    function updateClip(clientX){
        if(!modal.videoDuration||!modal.clipDragType)return;
        const t=fractionAt(clientX)*modal.videoDuration;
        if(modal.clipDragType==='start'){
            modal.clipState.start=Math.max(0,Math.min(modal.clipState.end-.05,t));
            vid.currentTime=modal.clipState.start;
        }else{
            modal.clipState.end=Math.max(modal.clipState.start+.05,Math.min(modal.videoDuration,t));
            vid.currentTime=Math.min(modal.clipState.end,modal.videoDuration);
        }
        syncClipTimeline();syncClipInputs();
    }
    function beginClip(target,clientX,pointerId){
        const handle=target&&target.closest?target.closest('.clip-handle'):null;
        if(!handle){
            vid.currentTime=fractionAt(clientX)*modal.videoDuration;
            return false;
        }
        modal.isClipDrag=true;
        modal.clipDragType=handle.dataset.clipHandle;
        modal.clipPointerId=pointerId;
        updateClip(clientX);
        return true;
    }
    function finishClip(){
        modal.isClipDrag=false;modal.clipDragType=null;modal.clipPointerId=null;
    }

    tl.addEventListener('pointerdown',e=>{
        if(!modal.videoDuration)return;
        e.preventDefault();e.stopPropagation();
        if(e.isPrimary===false)return;
        if(beginClip(e.target,e.clientX,e.pointerId)){
            try{tl.setPointerCapture(e.pointerId);}catch(_e){}
        }
    },{passive:false});
    tl.addEventListener('pointermove',e=>{
        if(!modal.isClipDrag||modal.clipPointerId!==e.pointerId)return;
        e.preventDefault();e.stopPropagation();updateClip(e.clientX);
    },{passive:false});
    const finishPointer=e=>{
        if(!modal.isClipDrag)return;
        if(modal.clipPointerId!==null&&e.pointerId!==modal.clipPointerId)return;
        e.preventDefault();e.stopPropagation();finishClip();
    };
    tl.addEventListener('pointerup',finishPointer,{passive:false});
    tl.addEventListener('pointercancel',finishPointer,{passive:false});

    tl.addEventListener('touchstart',e=>{
        if(window.PointerEvent||!modal.videoDuration)return;
        e.preventDefault();e.stopPropagation();
        const t=e.changedTouches[0];if(t)beginClip(e.target,t.clientX,'touch');
    },{passive:false});
    tl.addEventListener('touchmove',e=>{
        if(window.PointerEvent||!modal.isClipDrag)return;
        e.preventDefault();e.stopPropagation();
        const t=e.changedTouches[0];if(t)updateClip(t.clientX);
    },{passive:false});
    tl.addEventListener('touchend',e=>{if(!window.PointerEvent&&modal.isClipDrag){e.preventDefault();finishClip();}},{passive:false});
    tl.addEventListener('touchcancel',e=>{if(!window.PointerEvent&&modal.isClipDrag){e.preventDefault();finishClip();}},{passive:false});

    tl.addEventListener('mousedown',e=>{
        if(window.PointerEvent||!modal.videoDuration)return;
        e.preventDefault();beginClip(e.target,e.clientX,'mouse');
    });
    document.addEventListener('mousemove',e=>{
        if(!window.PointerEvent&&modal.isClipDrag){e.preventDefault();updateClip(e.clientX);}
    });
    document.addEventListener('mouseup',()=>{if(!window.PointerEvent&&modal.isClipDrag)finishClip();});

    vid.addEventListener('timeupdate',()=>{
        const ph=document.getElementById('clipPlayhead');
        if(ph&&modal.videoDuration) ph.style.left=(vid.currentTime/modal.videoDuration*100).toFixed(2)+'%';
    });
}

function syncClipTimeline(){
    if(!modal.videoDuration)return;
    const sp=(modal.clipState.start/modal.videoDuration*100).toFixed(2);
    const ep=(modal.clipState.end  /modal.videoDuration*100).toFixed(2);
    document.getElementById('clipStartHandle').style.left=sp+'%';
    document.getElementById('clipEndHandle').style.left  =ep+'%';
    document.getElementById('clipRange').style.left =sp+'%';
    document.getElementById('clipRange').style.width=(ep-sp)+'%';
}

function syncClipInputs(){
    document.getElementById('clipStartInput').value=toTS(modal.clipState.start);
    document.getElementById('clipEndInput').value  =toTS(modal.clipState.end);
    document.getElementById('clipDuration').textContent=toTS(modal.clipState.end-modal.clipState.start);
}

function onClipInputChange(){
    if(!modal.videoDuration)return;
    let start=clamp(fromTS(document.getElementById('clipStartInput').value),0,modal.videoDuration);
    let end=clamp(fromTS(document.getElementById('clipEndInput').value),0,modal.videoDuration);
    if(end<=start){
        if(start>=modal.videoDuration)start=Math.max(0,modal.videoDuration-.05);
        end=Math.min(modal.videoDuration,start+.05);
    }
    modal.clipState={start,end};
    syncClipTimeline();syncClipInputs();
}

function toTS(s){
    if(!isFinite(s)||s<0)s=0;
    const h=Math.floor(s/3600),m=Math.floor(s%3600/60),sec=s%60;
    return `${pad(h)}:${pad(m)}:${sec.toFixed(2).padStart(5,'0')}`;
}
function fromTS(str){
    const p=str.split(':');
    if(p.length===3)return parseFloat(p[0])*3600+parseFloat(p[1])*60+parseFloat(p[2]);
    return parseFloat(str)||0;
}
function pad(n){return String(n).padStart(2,'0');}

// ---- Apply / Reset ----
function applyEdits(){
    const idx=modal.fileIndex;
    const c=modal.cropState;
    const cropFull=(c.x===0&&c.y===0&&c.w===modal.naturalW&&c.h===modal.naturalH);
    const cl=modal.clipState;
    const clipFull=(!cl||cl.start===0&&Math.abs(cl.end-modal.videoDuration)<.05);

    fileEdits[idx]={
        crop: cropFull ? null : {...c},
        clip: (modal.mediaType==='video'&&!clipFull) ? {...cl} : null,
    };
    const badge=document.getElementById('editBadge_'+idx);
    if(badge) badge.style.display=(fileEdits[idx].crop||fileEdits[idx].clip)?'inline-block':'none';
    closePreviewModal();
}

function resetEdits(){
    modal.cropState={x:0,y:0,w:modal.naturalW,h:modal.naturalH};
    if(modal.mediaType==='video') modal.clipState={start:0,end:modal.videoDuration};
    const c=document.getElementById('imageCropCanvas');
    const vc=document.getElementById('videoCropCanvas');
    if(c.width)drawCrop(c); if(document.getElementById('videoCropShell').style.display!=='none')drawCrop(vc);
    syncCropInputs();
    if(modal.mediaType==='video'){syncClipTimeline();syncClipInputs();}
}

function setClipToCurrentTime(type){
    const vid=document.getElementById('previewVideo');
    if(!vid||!modal.videoDuration)return;
    const t=vid.currentTime;
    if(type==='start') modal.clipState.start=Math.min(t, modal.clipState.end-.1);
    else modal.clipState.end=Math.max(t, modal.clipState.start+.1);
    syncClipTimeline(); syncClipInputs();
}

function refreshVideoCropPreview(){
    if(!cropPreviewActive)return;
    const video=document.getElementById('previewVideo');
    const{x,y,w,h}=modal.cropState;
    const nW=modal.naturalW,nH=modal.naturalH;
    if(!nW||!nH||!w||!h)return;
    const top   =(y/nH*100).toFixed(3);
    const right =((nW-x-w)/nW*100).toFixed(3);
    const bottom=((nH-y-h)/nH*100).toFixed(3);
    const left  =(x/nW*100).toFixed(3);
    video.style.clipPath=`inset(${top}% ${right}% ${bottom}% ${left}%)`;
}

function toggleVideoCropPreview(){
    cropPreviewActive=!cropPreviewActive;
    const btn=document.getElementById('cropPreviewBtn');
    if(cropPreviewActive){ refreshVideoCropPreview(); btn.textContent='👁 Show Full'; }
    else{ document.getElementById('previewVideo').style.clipPath=''; btn.textContent='👁 Preview Crop'; }
}

function toggleVideoCropCanvas(){
    const wrap=document.getElementById('videoCropWrap');
    const btn=document.getElementById('videoCropCollapseBtn');
    const open=wrap.style.display!=='none';
    wrap.style.display=open?'none':'';
    btn.textContent=open?'▼ Show':'▲ Collapse';
}

function closePreviewModal(){
    endCropDrag();
    unlockPageBehindCropModal();
    const vid=document.getElementById('previewVideo');
    vid.pause(); vid.src=''; vid.style.clipPath='';
    cropPreviewActive=false;
    const cpBtn=document.getElementById('cropPreviewBtn');
    if(cpBtn)cpBtn.textContent='👁 Preview Crop';
    if(modal.objectUrl){URL.revokeObjectURL(modal.objectUrl);modal.objectUrl=null;}
    modal.capturedImg=null;
    const vcShell=document.getElementById('videoCropShell');
    if(vcShell) vcShell.style.display='none';
    const vcBtn=document.getElementById('videoCropCollapseBtn');
    if(vcBtn) vcBtn.textContent='▲ Collapse';
    document.getElementById('previewModal').style.display='none';
}
</script>
</body>
</html>
"""


# ==========================================
# FLASK ROUTES
# ==========================================

@app.after_request
def disable_browser_cache(response):
    """Always deliver the current embedded UI/JavaScript during local development."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE,
        formats_json=json.dumps([f.to_dict() for f in FORMATS]),
        setting_help=json.dumps(SETTING_HELP),
        favicon=FAVICON_BASE64,
        probe_full_upload_limit_bytes=PROBE_FULL_UPLOAD_LIMIT_MB * 1024 * 1024)

@app.route('/reset', methods=['POST'])
def reset_all():
    """No-op — full wipe is only done on server startup/shutdown."""
    return "OK", 200

@app.route('/reset/<session_id>', methods=['POST'])
def reset_session(session_id):
    """Delete only this user's session folder."""
    wipe_session(session_id)
    return "Cleaned", 200

@app.route('/probe', methods=['POST'])
def probe():
    if 'file' not in request.files:
        return jsonify({})
    file = request.files['file']
    if not file.filename or '.' not in file.filename:
        return jsonify({})

    ext = "." + file.filename.rsplit('.', 1)[-1]
    tmp = os.path.join(BASE_TEMP_DIR, f"probe_{uuid.uuid4().hex}{ext}")
    file.save(tmp)
    meta = {}
    try:
        cmd = [
            FFPROBE_CMD, '-v', 'error',
            '-probesize', '50M', '-analyzeduration', '100M',
            '-print_format', 'json',
            '-show_entries',
            'stream=codec_type,width,height,r_frame_rate,avg_frame_rate,bit_rate,sample_rate:format=bit_rate',
            tmp
        ]
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            startupinfo=make_startupinfo(), timeout=45
        )
        if proc.returncode != 0:
            detail = proc.stderr.decode(errors='replace').strip().splitlines()
            if detail:
                print(f"Probe skipped for {file.filename}: {detail[-1]}")
            return jsonify({})

        data = json.loads(proc.stdout.decode(errors='replace') or '{}')
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video' and 'Resolution' not in meta:
                width, height = stream.get('width'), stream.get('height')
                if width and height:
                    meta['Resolution'] = f"{width}x{height}"
                rate = stream.get('avg_frame_rate') or stream.get('r_frame_rate')
                if rate and '/' in rate:
                    numerator, denominator = rate.split('/', 1)
                    try:
                        if float(denominator) != 0:
                            meta['FPS'] = str(round(float(numerator) / float(denominator), 2))
                    except ValueError:
                        pass
                if stream.get('bit_rate'):
                    meta['Video Bitrate'] = f"{int(stream['bit_rate']) // 1000}k"
            elif stream.get('codec_type') == 'audio' and 'Sample Rate' not in meta:
                if stream.get('sample_rate'):
                    meta['Sample Rate'] = stream['sample_rate']
                if stream.get('bit_rate'):
                    meta['Audio Bitrate'] = f"{int(stream['bit_rate']) // 1000}k"

        format_bitrate = data.get('format', {}).get('bit_rate')
        if 'Video Bitrate' not in meta and format_bitrate:
            meta['Video Bitrate'] = f"{int(format_bitrate) // 1000}k"
    except subprocess.TimeoutExpired:
        print(f"Probe timed out for {file.filename}; browser metadata will be used.")
    except Exception as exc:
        print(f"Probe skipped for {file.filename}: {exc}")
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
    return jsonify(meta)

@app.route('/convert', methods=['POST'])
def convert():
    session_id = request.form.get('session_id', str(uuid.uuid4()))
    session_dir = os.path.join(BASE_TEMP_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    files = request.files.getlist('file')
    output_format = request.form.get('output_format','')
    job_id = session_id
    progress_store[job_id] = {"percent":0,"status":"processing","results":[]}

    files_data = []
    for f in files:
        if not f or not f.filename or '.' not in f.filename:
            continue
        u_id   = os.urandom(4).hex()
        in_ext = "." + f.filename.rsplit('.',1)[-1]
        out_ext = output_format.lower()
        if out_ext=='avchd':       out_ext='m2ts'
        if out_ext=='mpeg-2':      out_ext='mpg'
        if out_ext=='animated gif': out_ext='gif'

        in_path     = os.path.join(session_dir, f"in_{u_id}{in_ext}")
        out_filename = f"out_{u_id}.{out_ext}"
        out_path    = os.path.join(session_dir, out_filename)
        f.save(in_path)
        files_data.append((f.filename.rsplit('.',1)[0], in_path, out_path, out_filename))

    if not files_data:
        progress_store[job_id].update({"status":"error","message":"No valid files received."})
        return jsonify({"job_id": job_id})

    t = threading.Thread(target=background_convert,
                         args=(job_id, session_dir, files_data, output_format, request.form),
                         daemon=True)
    t.start()
    return jsonify({"job_id": job_id})

@app.route('/status/<job_id>')
def status(job_id):
    return jsonify(progress_store.get(job_id, {"status":"not_found"}))

@app.route('/download/<session_id>/<file_id>')
def download(session_id, file_id):
    custom_name = request.args.get('name','converted')
    ext = file_id.split('.')[-1]
    filepath = os.path.join(BASE_TEMP_DIR, session_id, file_id)
    if not os.path.exists(filepath):
        return "File not found (may have been cleaned up).", 404

    @after_this_request
    def remove_file(response):
        try:
            if os.path.exists(filepath): os.remove(filepath)
        except: pass
        return response
    try:
        return send_file(filepath, as_attachment=True, download_name=f"{custom_name}.{ext}")
    except FileNotFoundError:
        return "File missing during download.", 404

@app.route('/download_all', methods=['POST'])
def download_all():
    data = request.json
    mem = io.BytesIO()
    to_delete = []
    with zipfile.ZipFile(mem,'w') as zf:
        for item in data:
            fp = os.path.join(BASE_TEMP_DIR, item['id'])
            if os.path.exists(fp):
                zf.write(fp, f"{item['original_name']}.{item['ext']}")
                to_delete.append(fp)
    mem.seek(0)

    @after_this_request
    def cleanup(response):
        for f in to_delete:
            try: os.remove(f)
            except: pass
        return response
    return send_file(mem, mimetype='application/zip', as_attachment=True,
                     download_name='converted_files.zip')

def resolve_network_mode(argv=None):
    """Return 'lan' or 'local' from command-line arguments or an interactive prompt."""
    import argparse

    args = sys.argv[1:] if argv is None else list(argv)
    parser = argparse.ArgumentParser(
        description="Run the local file converter in LAN or local-only mode."
    )
    parser.add_argument(
        "network_mode", nargs="?", choices=("lan", "local"), type=str.lower,
        help="Network mode: 'lan' exposes the server to your LAN; 'local' binds to this machine only."
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--mode", "--network-mode", dest="option_mode",
        choices=("lan", "local"), type=str.lower,
        help="Network mode (alternative to the positional argument)."
    )
    mode_group.add_argument(
        "--lan", dest="option_mode", action="store_const", const="lan",
        help="Shortcut for --mode lan."
    )
    mode_group.add_argument(
        "--local", dest="option_mode", action="store_const", const="local",
        help="Shortcut for --mode local."
    )
    parsed = parser.parse_args(args)

    if parsed.network_mode and parsed.option_mode and parsed.network_mode != parsed.option_mode:
        parser.error("conflicting network modes were supplied")

    selected_mode = parsed.option_mode or parsed.network_mode
    if selected_mode:
        return selected_mode

    while True:
        answer = input(
            "Enter LAN to allow other devices, or LOCAL for this machine only [LOCAL]: "
        ).strip().lower()
        if not answer:
            return "local"
        if answer in ("lan", "local"):
            return answer
        print("Please enter LAN or LOCAL.")


def get_lan_ips():
    """Return usable IPv4 LAN addresses, with the default-route address first."""
    found = []

    # A UDP connect does not send application data. It asks the OS which local
    # interface/address it would use, avoiding unreliable hostname resolution.
    for target in (("8.8.8.8", 80), ("1.1.1.1", 80)):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.settimeout(1.0)
            sock.connect(target)
            found.append(sock.getsockname()[0])
        except OSError:
            pass
        finally:
            sock.close()

    # Also include other active IPv4 adapters (useful with Ethernet + Wi-Fi,
    # VPNs, or when the machine has no internet route).
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(info[4][0])
    except OSError:
        pass

    usable = []
    for value in found:
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue
        if address.version != 4 or address.is_loopback or address.is_link_local or address.is_unspecified:
            continue
        if value not in usable:
            usable.append(value)

    # Prefer RFC1918/private LAN addresses over VPN/public adapter addresses.
    return sorted(usable, key=lambda value: (not ipaddress.ip_address(value).is_private, usable.index(value)))


def configure_windows_firewall(port):
    """Allow TCP access from the local subnet on Windows, when elevated."""
    if platform.system() != "Windows":
        return

    rule_name = f"LocalFileConverter_{port}"
    command = [
        "netsh", "advfirewall", "firewall", "add", "rule",
        f"name={rule_name}", "dir=in", "action=allow", "enable=yes",
        "protocol=TCP", f"localport={port}", "profile=any",
        "remoteip=localsubnet",
    ]

    try:
        import ctypes
        is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        is_admin = False

    if not is_admin:
        print("⚠️  Windows Firewall rule was not changed (Administrator rights required).")
        print("   Re-run this program as Administrator once, or allow this command in an")
        print("   elevated Command Prompt:")
        print("   " + " ".join(command))
        return

    try:
        subprocess.run(
            ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}"],
            capture_output=True, text=True, check=False,
        )
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            print(f"✅ Windows Firewall: LAN access allowed on TCP port {port}.")
        else:
            detail = (result.stderr or result.stdout).strip()
            print(f"⚠️  Windows Firewall rule could not be added (exit {result.returncode}).")
            if detail:
                print(f"   {detail}")
    except OSError as exc:
        print(f"⚠️  Could not run Windows Firewall command: {exc}")


if __name__ == '__main__':
    network_mode = resolve_network_mode()
    HOST = "0.0.0.0" if network_mode == "lan" else "127.0.0.1"

    wipe_temp_folder()
    print("=" * 55)
    print("  Fully Local File Converter")
    print("=" * 55)
    print(f"Network mode: {network_mode.upper()} ({HOST})")

    if not shutil.which("ffmpeg"):
        print("\n❌ CRITICAL: FFmpeg not found in PATH! Install FFmpeg.")
    else:
        print("✅ FFmpeg detected.")

    print(f"\nLocal access: http://127.0.0.1:{PORT}")

    if network_mode == "lan":
        lan_ips = get_lan_ips()
        if lan_ips:
            print(f"LAN access:   http://{lan_ips[0]}:{PORT}")
            for alternate_ip in lan_ips[1:]:
                print(f"Alternative:  http://{alternate_ip}:{PORT}")
        else:
            print("⚠️  No usable LAN IPv4 address was detected.")
            print("   Run 'ipconfig' (Windows) or 'ip addr' (Linux) and use the")
            print(f"   active adapter's IPv4 address with port {PORT}.")

        configure_windows_firewall(PORT)
        print("\nOn the other device, use the LAN URL shown above—not 0.0.0.0 or 127.0.0.1.")
        print("Both devices must be on the same LAN, and guest/AP isolation must be disabled.")

    print()

    # Explicitly listen on every IPv4 interface in LAN mode. Using Waitress's
    # listen form avoids accidentally falling back to localhost-only defaults.
    if network_mode == "lan":
        serve(app, listen=f"0.0.0.0:{PORT}", threads=8)
    else:
        serve(app, host="127.0.0.1", port=PORT, threads=8)
