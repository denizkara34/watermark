import os, uuid, subprocess, shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI()
WORK = Path("/tmp/wm")
WORK.mkdir(exist_ok=True)

# Frontend
@app.get("/", response_class=HTMLResponse)
def index():
    return (Path("static/index.html")).read_text()

@app.post("/process")
async def process(
    video: UploadFile = File(...),
    watermark: UploadFile = File(...),
):
    job = WORK / str(uuid.uuid4())
    job.mkdir()
    try:
        # Dosyaları kaydet
        vid_ext = Path(video.filename).suffix or ".mp4"
        vid_path = job / f"input{vid_ext}"
        wm_path  = job / "wm.png"
        out_path = job / "output.mp4"

        vid_path.write_bytes(await video.read())
        wm_path.write_bytes(await watermark.read())

        # Video boyutunu al
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "csv=p=0", str(vid_path)],
            capture_output=True, text=True
        )
        dims = probe.stdout.strip().split(",")
        if len(dims) < 2:
            raise HTTPException(400, "Video boyutu alınamadı")
        w, h = dims[0].strip(), dims[1].strip()

        # FFmpeg
        cmd = [
            "ffmpeg", "-y",
            "-i", str(vid_path),
            "-i", str(wm_path),
            "-filter_complex", f"[1:v]scale={w}:{h}[wm];[0:v][wm]overlay=0:0",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-c:a", "copy", "-movflags", "+faststart",
            str(out_path)
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            raise HTTPException(500, f"FFmpeg hata: {result.stderr.decode()[-200:]}")

        out_name = "wm_" + Path(video.filename).stem + ".mp4"
        return FileResponse(str(out_path), media_type="video/mp4",
                            filename=out_name,
                            background=None)
    finally:
        # Yanıt gönderildikten sonra temizle — FileResponse bitince çalışmaz
        # O yüzden ayrı endpoint ile temizlik yapıyoruz, burada pass
        pass
