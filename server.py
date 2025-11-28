import os
import shutil
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import run_audit
import adb_client
import config

app = FastAPI()

# Create directories for uploads if they don't exist
UPLOAD_DIR = "web_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/files", StaticFiles(directory="."), name="files")

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/adb/check")
async def check_adb():
    """Check if ADB is connected and a device is found."""
    try:
        # Simple check: list devices
        import subprocess
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        if "device" in result.stdout and len(result.stdout.strip().split('\n')) > 1:
             return JSONResponse(content={"status": "connected", "details": result.stdout})
        return JSONResponse(content={"status": "disconnected", "details": result.stdout})
    except Exception as e:
        return JSONResponse(content={"status": "error", "details": str(e)})

@app.post("/analyze")
async def analyze(
    figma_files: List[UploadFile] = File(...),
    app_files: Optional[List[UploadFile]] = File(None),
    use_adb: bool = Form(False),
    app_analysis_mode: str = Form("xml"), # "xml" or "ai"
    figma_crop_top: int = Form(0),
    figma_crop_bottom: int = Form(0),
    app_crop_top: int = Form(0),
    app_crop_bottom: int = Form(0),
):
    # 1. Save Uploaded Files
    saved_figma_paths = []
    saved_app_paths = []

    # Clean upload dir for this run (optional, or use unique subdirs)
    # For simplicity, we just append timestamp or use unique names
    
    for file in figma_files:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        saved_figma_paths.append(file_path)

    if app_files:
        for file in app_files:
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_app_paths.append(file_path)

    # 2. Prepare Arguments
    # If use_adb is True, we ignore app_files (or use them as fallback? Logic in run_audit handles this)
    # run_audit_process expects app_parts to be None if we want Auto/ADB mode.
    
    final_app_parts = None
    if not use_adb and saved_app_paths:
        final_app_parts = saved_app_paths
    
    # 3. Run Audit
    try:
        report = run_audit.run_audit_process(
            figma_parts=saved_figma_paths,
            app_parts=final_app_parts,
            app_analysis_mode=app_analysis_mode,
            figma_crop_top=figma_crop_top,
            figma_crop_bottom=figma_crop_bottom,
            app_crop_top=app_crop_top,
            app_crop_bottom=app_crop_bottom
        )
        return JSONResponse(content=report)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
