import os
import subprocess
import tempfile

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="AI Beast Speech API", version="v1")
FILE_UPLOAD = File(...)

BACKEND = os.getenv("SPEECH_BACKEND", "auto")  # auto|faster_whisper|whisper_cpp
FW_MODEL = os.getenv("FASTER_WHISPER_MODEL", "small")  # tiny|base|small|medium|large-v3 etc
FW_DEVICE = os.getenv("FASTER_WHISPER_DEVICE", "cpu")  # cpu|cuda (cuda not typical on mac)
FW_COMPUTE = os.getenv("FASTER_WHISPER_COMPUTE", "int8")  # int8|int8_float16|float16|float32
WHISPER_CPP_BIN = os.getenv("WHISPER_CPP_BIN", "")
WHISPER_CPP_MODEL = os.getenv("WHISPER_CPP_MODEL", "")

_fw = None

def have_cmd(cmd: str) -> bool:
    from shutil import which
    return which(cmd) is not None

def init_faster_whisper():
    global _fw
    if _fw is not None:
        return _fw
    from faster_whisper import WhisperModel
    _fw = WhisperModel(FW_MODEL, device=FW_DEVICE, compute_type=FW_COMPUTE)
    return _fw

def transcribe_faster_whisper(path: str):
    model = init_faster_whisper()
    segments, info = model.transcribe(path, beam_size=5, vad_filter=True)
    segs=[]
    full=[]
    for s in segments:
        segs.append({"start": s.start, "end": s.end, "text": s.text})
        full.append(s.text)
    return {"backend":"faster-whisper", "language": getattr(info, "language", None), "text":"".join(full).strip(), "segments":segs}

def transcribe_whisper_cpp(path: str):
    if not WHISPER_CPP_BIN or not os.path.exists(WHISPER_CPP_BIN):
        return {"error":"WHISPER_CPP_BIN not set or missing"}
    if not WHISPER_CPP_MODEL or not os.path.exists(WHISPER_CPP_MODEL):
        return {"error":"WHISPER_CPP_MODEL not set or missing"}
    # whisper.cpp main usage can vary; we keep it conservative.
    # Typical: ./main -m model.bin -f audio.wav -otxt
    outdir = tempfile.mkdtemp(prefix="whispercpp_")
    cmd = [WHISPER_CPP_BIN, "-m", WHISPER_CPP_MODEL, "-f", path, "-otxt", "-of", os.path.join(outdir, "out")]
    p = subprocess.run(cmd, capture_output=True, text=True)
    txt_path = os.path.join(outdir, "out.txt")
    text_out = ""
    if os.path.exists(txt_path):
        with open(txt_path, encoding="utf-8", errors="ignore") as f:
            text_out = f.read().strip()
    return {"backend":"whisper.cpp", "returncode":p.returncode, "text":text_out, "stderr":p.stderr[-2000:], "stdout":p.stdout[-2000:]}

@app.get("/health")
def health():
    return {
        "ok": True,
        "backend": BACKEND,
        "faster_whisper_model": FW_MODEL,
        "whisper_cpp_configured": bool(WHISPER_CPP_BIN and WHISPER_CPP_MODEL),
    }

@app.post("/transcribe")
async def transcribe(file: UploadFile = FILE_UPLOAD, backend: str = Form("auto")):
    # Save upload
    suffix = os.path.splitext(file.filename or "")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    chosen = backend if backend != "auto" else BACKEND
    if chosen == "auto":
        chosen = "faster_whisper"

    try:
        if chosen in ("faster_whisper","faster-whisper"):
            data = transcribe_faster_whisper(tmp_path)
        elif chosen in ("whisper_cpp","whisper.cpp"):
            data = transcribe_whisper_cpp(tmp_path)
        else:
            data = {"error": f"Unknown backend: {chosen}"}
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return JSONResponse(data)

@app.post("/tts")
async def tts(text: str = Form(...), voice: str = Form(""), fmt: str = Form("wav")):
    # macOS: use `say` if available
    if not have_cmd("say"):
        return JSONResponse({"error":"No system TTS available (missing 'say')."}, status_code=400)

    outdir = tempfile.mkdtemp(prefix="tts_")
    aiff_path = os.path.join(outdir, "out.aiff")
    out_path = os.path.join(outdir, f"out.{fmt}")

    cmd = ["say", "-o", aiff_path]
    if voice:
        cmd += ["-v", voice]
    cmd += [text]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        return JSONResponse({"error":"say failed", "stderr":p.stderr[-2000:]}, status_code=500)

    # Convert to requested format
    if fmt.lower() == "aiff":
        return FileResponse(aiff_path, media_type="audio/aiff", filename="tts.aiff")

    if have_cmd("afconvert"):
        # Use macOS audio converter
        subprocess.run(["afconvert", aiff_path, out_path], capture_output=True, text=True)
        return FileResponse(out_path, media_type="audio/wav" if fmt.lower()=="wav" else "application/octet-stream", filename=f"tts.{fmt}")
    else:
        return FileResponse(aiff_path, media_type="audio/aiff", filename="tts.aiff")
