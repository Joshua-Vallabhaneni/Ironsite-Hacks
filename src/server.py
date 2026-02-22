"""
server.py — FastAPI server wrapping the Ironsite analysis pipeline.
Run with:  uvicorn src.server:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import uuid
import shutil
import logging
import threading
from pathlib import Path
from argparse import Namespace

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from . import pipeline

log = logging.getLogger(__name__)

BASE_OUTPUT_DIR = Path(os.environ.get("IRONSITE_OUTPUT_DIR", "outputs"))

app = FastAPI(title="Ironsite API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory run state
# ---------------------------------------------------------------------------
_runs: dict[str, dict] = {}


class PipelineProgressHandler(logging.Handler):
    """Intercept pipeline log messages to update run progress."""

    PHASE_MAP = {
        "PHASE 1": ("processing", "Scene selection"),
        "PHASE 2:": ("processing", "Sidecar construction"),
        "PHASE 2.5": ("processing", "Activity labeling"),
        "PHASE 3": ("processing", "Event extraction"),
        "PHASE 4": ("processing", "Spatial query"),
        "PHASE 5": ("processing", "Metrics computation"),
        "PHASE 6": ("processing", "Report generation"),
        "PIPELINE COMPLETE": ("complete", "Done"),
        "BASELINE: Uniform": ("processing", "Baseline frame sampling"),
        "BASELINE: Gemini": ("processing", "Baseline Gemini summaries"),
    }

    def __init__(self, run_id: str):
        super().__init__()
        self.run_id = run_id

    def emit(self, record: logging.LogRecord):
        msg = record.getMessage()
        for key, (status, step) in self.PHASE_MAP.items():
            if key in msg:
                if self.run_id in _runs:
                    _runs[self.run_id]["step"] = step
                break


def _run_pipeline_thread(run_id: str, input_dir: str, output_dir: str):
    """Execute the pipeline in a background thread."""
    handler = PipelineProgressHandler(run_id)
    logging.getLogger().addHandler(handler)
    try:
        args = Namespace(
            input_dir=input_dir,
            out_dir=str(BASE_OUTPUT_DIR),
            mode="augmented",
            baseline=False,
            no_llm=False,
            use_llm=True,
            video_file=None,
            max_videos=None,
            max_minutes_per_video=None,
            sample_every_sec=None,
            spatial_query_k=None,
            gemini_budget=None,
            gemini_budget_baseline=None,
            _output_dir_override=output_dir,
        )
        pipeline.run_pipeline(args)
        _runs[run_id]["status"] = "complete"
        _runs[run_id]["step"] = "Done"
    except SystemExit:
        _runs[run_id]["status"] = "error"
        _runs[run_id]["error"] = "Pipeline exited with an error"
    except Exception as e:
        log.exception("Pipeline failed for run %s", run_id)
        _runs[run_id]["status"] = "error"
        _runs[run_id]["error"] = str(e)
    finally:
        logging.getLogger().removeHandler(handler)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/upload")
async def upload_videos(files: list[UploadFile] = File(...)):
    run_id = uuid.uuid4().hex[:12]
    run_dir = BASE_OUTPUT_DIR / run_id
    input_dir = run_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        dest = input_dir / f.filename
        with open(dest, "wb") as out:
            shutil.copyfileobj(f.file, out)

    _runs[run_id] = {
        "status": "uploaded",
        "step": "Uploaded",
        "error": None,
        "output_dir": str(run_dir),
        "input_dir": str(input_dir),
    }
    return {"run_id": run_id}


@app.post("/api/analyze/{run_id}")
async def start_analysis(run_id: str):
    if run_id not in _runs:
        raise HTTPException(404, "Run not found")
    run = _runs[run_id]
    if run["status"] not in ("uploaded",):
        raise HTTPException(400, f"Run is already {run['status']}")

    run["status"] = "processing"
    run["step"] = "Starting pipeline"

    t = threading.Thread(
        target=_run_pipeline_thread,
        args=(run_id, run["input_dir"], run["output_dir"]),
        daemon=True,
    )
    t.start()
    return {"status": "processing"}


@app.get("/api/status/{run_id}")
async def get_status(run_id: str):
    if run_id not in _runs:
        raise HTTPException(404, "Run not found")
    run = _runs[run_id]
    return {
        "status": run["status"],
        "step": run["step"],
        "error": run["error"],
    }


@app.get("/api/report/{run_id}")
async def get_report(run_id: str):
    if run_id not in _runs:
        raise HTTPException(404, "Run not found")
    report_path = Path(_runs[run_id]["output_dir"]) / "report.md"
    if not report_path.exists():
        raise HTTPException(404, "Report not ready")
    return {"markdown": report_path.read_text()}


@app.get("/api/sidecar/{run_id}")
async def get_sidecar(run_id: str):
    if run_id not in _runs:
        raise HTTPException(404, "Run not found")
    import json
    sidecar_path = Path(_runs[run_id]["output_dir"]) / "sidecar.json"
    if not sidecar_path.exists():
        raise HTTPException(404, "Sidecar not ready")
    return json.loads(sidecar_path.read_text())


@app.get("/api/clips/{run_id}/{path:path}")
async def get_clip(run_id: str, path: str):
    if run_id not in _runs:
        raise HTTPException(404, "Run not found")
    clip_path = Path(_runs[run_id]["output_dir"]) / path
    if not clip_path.exists():
        raise HTTPException(404, "Clip not found")
    return FileResponse(clip_path, media_type="video/mp4")


@app.get("/api/runs")
async def list_runs():
    return [
        {"run_id": rid, "status": r["status"], "step": r["step"]}
        for rid, r in _runs.items()
    ]


@app.get("/api/runs/latest")
async def latest_run():
    if not _runs:
        raise HTTPException(404, "No runs yet")
    rid = list(_runs.keys())[-1]
    run = _runs[rid]
    return {"run_id": rid, "status": run["status"], "step": run["step"]}
