# modelshift-lite/dashboard_web/app.py
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

# -------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RUNS_DIR = DATA_DIR / "runs"

LATEST_JSON = DATA_DIR / "latest.json"
PREVIOUS_JSON = DATA_DIR / "previous.json"
HISTORY_INDEX_JSON = DATA_DIR / "history_index.json"
REPORT_LATEST_HTML = DATA_DIR / "report_latest.html"

# run_id safety (avoid path traversal)
SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,80}$")

# -------------------------------------------------------------------
# App
# -------------------------------------------------------------------
app = FastAPI(title="ModelShift-Lite Dashboard")

# static + templates
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def read_json(path: Path) -> Dict[str, Any]:
    """Safe JSON reader; returns {} on error/missing."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_text(path: Path) -> str:
    """Safe text reader; returns empty string on error/missing."""
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def no_cache_headers(resp: Response) -> None:
    """Force no-cache for live dashboard APIs."""
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"


def safe_run_path(run_id: str) -> Path:
    if not SAFE_RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=400, detail="Invalid run_id format")
    return RUNS_DIR / f"{run_id}.json"


def safe_report_path(run_id: str) -> Path:
    if not SAFE_RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=400, detail="Invalid run_id format")
    return RUNS_DIR / f"{run_id}.report.html"


def slim_run_payload(run: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return only what the UI needs for lists / history.
    Keeps payload lightweight while preserving metrics used by tabs.
    """
    summary = run.get("summary", {}) if isinstance(run.get("summary"), dict) else {}
    evaluation = run.get("evaluation") if isinstance(run.get("evaluation"), dict) else None

    return {
        "run_id": run.get("run_id"),
        "generated_at": run.get("generated_at"),
        "status": run.get("status", run.get("state")),
        "window_size": run.get("window_size"),

        "clean_health": summary.get("clean_health"),
        "drifted_health": summary.get("drifted_health"),
        "drifted_pred_ks": summary.get("drifted_pred_ks"),
        "drifted_entropy_change": summary.get("drifted_entropy_change"),
        "drifted_last_window_feature": summary.get("drifted_last_window_feature"),
        "drifted_last_window_ks": summary.get("drifted_last_window_ks"),

        # Optional but useful for evaluation tables
        "evaluation": evaluation,

        "series_hash": run.get("series_hash"),
        "payload_hash": run.get("payload_hash"),
    }


def normalize_history_item(it: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize one history_index entry to the UI shape expected by app.js.
    Safe for missing fields.
    """
    return {
        "run_id": it.get("run_id"),
        "generated_at": it.get("generated_at"),
        "status": it.get("status"),

        "clean_health": it.get("clean_health"),
        "drifted_health": it.get("drifted_health"),
        "drifted_pred_ks": it.get("drifted_pred_ks"),
        "drifted_entropy_change": it.get("drifted_entropy_change"),

        "drifted_last_window_feature": it.get("drifted_last_window_feature"),
        "drifted_last_window_ks": it.get("drifted_last_window_ks"),

        "payload_hash": it.get("payload_hash"),
        "series_hash": it.get("series_hash"),
    }


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/results")
def api_results(response: Response):
    """
    Returns the current latest + previous run payloads exactly as the UI expects.
    """
    latest = read_json(LATEST_JSON)
    previous = read_json(PREVIOUS_JSON)
    no_cache_headers(response)
    return {"latest": latest, "previous": previous}


@app.get("/api/run/{run_id}")
def api_run(run_id: str, response: Response):
    """
    Return full archived run payload from:
      dashboard_web/data/runs/{run_id}.json
    """
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    p = safe_run_path(run_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    no_cache_headers(response)
    return read_json(p)


@app.get("/api/history")
def api_history(
    response: Response,
    n: int = Query(default=20, ge=1, le=50),
):
    """
    History for the History tab.
    Prefer dashboard_web/data/history_index.json (fast).
    Falls back to scanning runs/*.json.
    """
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    # Fast path: history_index.json
    idx = read_json(HISTORY_INDEX_JSON)
    if isinstance(idx, dict) and isinstance(idx.get("items"), list):
        items = idx["items"][:n]
        out = [normalize_history_item(it) for it in items if isinstance(it, dict)]

        no_cache_headers(response)
        return {"runs": out, "source": "history_index"}

    # Fallback: scan runs directory
    files = sorted(
        RUNS_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:n]

    out: List[Dict[str, Any]] = []
    for p in files:
        run = read_json(p)
        if isinstance(run, dict) and run:
            out.append(slim_run_payload(run))

    no_cache_headers(response)
    return {"runs": out, "source": "scan_runs"}


@app.get("/api/report/latest", response_class=HTMLResponse)
def api_report_latest(download: int = Query(default=0, ge=0, le=1)):
    """
    Returns the latest generated report HTML if available.
    If download=1 => Content-Disposition attachment.
    """
    html = read_text(REPORT_LATEST_HTML)

    # fallback: try latest run report by run_id
    if not html:
        latest = read_json(LATEST_JSON)
        rid = latest.get("run_id")
        if isinstance(rid, str) and SAFE_RUN_ID_RE.match(rid):
            html = read_text(safe_report_path(rid))

    if not html:
        raise HTTPException(status_code=404, detail="No report available yet")

    resp = HTMLResponse(content=html)

    # IMPORTANT: set header on the response we're actually returning
    if download == 1:
        resp.headers["Content-Disposition"] = 'attachment; filename="ModelShift-Lite_Report_Latest.html"'

    no_cache_headers(resp)
    return resp