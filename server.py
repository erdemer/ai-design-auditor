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

def parse_figma_link(link: str):
    """
    Extracts file_key and node_id from a Figma URL.
    Example: https://www.figma.com/design/KEY/Title?node-id=1-2...
    """
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(link)
        path_parts = parsed.path.split('/')
        
        # File Key is usually the 3rd or 4th part depending on URL structure
        # /file/KEY/Title or /design/KEY/Title
        file_key = None
        for part in path_parts:
            if len(part) > 20: # Heuristic for ID
                file_key = part
                break
        
        if not file_key:
            return None, None
            
        query_params = parse_qs(parsed.query)
        node_id = query_params.get('node-id', [None])[0]
        
        if node_id:
            node_id = node_id.replace('-', ':')
            
        return file_key, node_id
    except:
        return None, None


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
    figma_files: Optional[List[UploadFile]] = File(None),
    app_files: Optional[List[UploadFile]] = File(None),
    figma_link: str = Form(None),
    use_adb: bool = Form(False),
    app_analysis_mode: str = Form("xml"), # "xml" or "ai"
    figma_crop_top: int = Form(-1),
    figma_crop_bottom: int = Form(-1),
    app_crop_top: int = Form(-1),
    app_crop_bottom: int = Form(-1),
):
    # 1. Save Uploaded Files (if any)
    saved_figma_paths = []
    saved_app_paths = []

    # Clean upload dir for this run (optional, or use unique subdirs)
    # For simplicity, we just append timestamp or use unique names
    
    if figma_files:
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
    
    # 3. Handle Figma Source (Link vs Files)
    figma_file_key = None
    figma_node_ids = None
    
    if figma_link:
        key, node = parse_figma_link(figma_link)
        if key and node:
            figma_file_key = key
            figma_node_ids = [node]
            print(f"[Server] Using Figma Link: Key={key}, Node={node}")
        else:
            return JSONResponse(content={"error": "Invalid Figma Link format."}, status_code=400)
    elif not saved_figma_paths:
         return JSONResponse(content={"error": "Please provide either Figma Files or a Figma Link."}, status_code=400)

    # 4. Run Audit
    try:
        report = run_audit.run_audit_process(
            figma_parts=saved_figma_paths if not figma_file_key else None,
            app_parts=final_app_parts,
            app_analysis_mode=app_analysis_mode,
            figma_crop_top=figma_crop_top,
            figma_crop_bottom=figma_crop_bottom,
            app_crop_top=app_crop_top,
            app_crop_bottom=app_crop_bottom,
            figma_file_key=figma_file_key,
            figma_node_ids=figma_node_ids
        )
        return JSONResponse(content=report)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
