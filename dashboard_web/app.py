# modelshift-lite/dashboard_web/app.py
from __future__ import annotations
import sys
import subprocess
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Response
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

# Optional heartbeat file written by producer/training pipeline
LIVE_HEARTBEAT = DATA_DIR / "live_heartbeat.touch"

# How long a result is considered "live" (in seconds)
# Keep this short so dashboard goes blank quickly when nothing is connected.
RESULTS_STALE_AFTER_SEC = 10

# run_id safety (avoid path traversal)
SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,80}$")
SELFTEST_JSON = DATA_DIR / "selftest.json"
# -------------------------------------------------------------------
# App
# -------------------------------------------------------------------
app = FastAPI(title="ModelShift-Lite Dashboard")

# static + templates
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# -------------------------------------------------------------------
# Startup
# -------------------------------------------------------------------
@app.on_event("startup")
def _startup() -> None:
    ensure_dirs()


# -------------------------------------------------------------------
# Freshness helpers
# -------------------------------------------------------------------
def _is_fresh_file(p: str | Path) -> bool:
    """
    Returns True if file exists and was modified recently.
    Works whether p is a str or Path.
    """
    try:
        path = Path(p)
        if not path.exists() or not path.is_file():
            return False
        age_sec = time.time() - path.stat().st_mtime
        return age_sec <= RESULTS_STALE_AFTER_SEC
    except Exception:
        return False


def _is_live_connected() -> bool:
    """
    LIVE mode (heartbeat) OR sticky export mode (latest.json exists).
    - If heartbeat is fresh -> LIVE
    - Else if latest.json has valid payload -> still LIVE (sticky mode for your project)
    - Else -> DISCONNECTED
    """
    try:
        # 1) True live stream mode (if heartbeat exists and is fresh)
        if LIVE_HEARTBEAT.exists() and _is_fresh_file(LIVE_HEARTBEAT):
            return True

        # 2) Sticky mode for your project:
        #    if exported dashboard files exist, keep UI as LIVE
        latest = read_json(LATEST_JSON)
        if isinstance(latest, dict) and latest:
            return True

        return False
    except Exception:
        return False


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> Dict[str, Any]:
    """
    Safe JSON reader; returns {} on error/missing/non-dict.
    """
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def read_text(path: Path) -> str:
    """
    Safe text reader; returns empty string on error/missing.
    """
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    """
    Atomic JSON write to avoid partial/corrupt files if interrupted.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp_path, path)


def no_cache_headers(resp: Response) -> None:
    """
    Force no-cache for live dashboard APIs.
    """
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


def _safe_number(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_str(value: Any) -> Optional[str]:
    if isinstance(value, str):
        v = value.strip()
        return v if v else None
    return None


def _parse_iso_dt(value: Any) -> Optional[datetime]:
    """
    Accepts common ISO strings, including trailing 'Z'.
    Returns None if invalid.
    """
    if not isinstance(value, str) or not value.strip():
        return None

    s = value.strip()
    try:
        # Python fromisoformat doesn't accept trailing Z directly
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _sort_dt_key(dt: Optional[datetime]) -> datetime:
    """
    Normalize datetime for sorting (naive/aware safe).
    """
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _best_status(run: Dict[str, Any]) -> str:
    """
    Status extraction compatible with older and newer schemas.
    """
    if not isinstance(run, dict):
        return "UNKNOWN"

    # Top-level
    top = _safe_str(run.get("status")) or _safe_str(run.get("state"))
    if top:
        return top

    # Nested decision blocks (newer schema)
    decision = run.get("decision")
    if isinstance(decision, dict):
        d_status = _safe_str(decision.get("status"))
        if d_status:
            return d_status

    monitor_decision = run.get("monitor_decision")
    if isinstance(monitor_decision, dict):
        md_status = _safe_str(monitor_decision.get("status"))
        if md_status:
            return md_status

    return "UNKNOWN"


def _summary_obj(run: Dict[str, Any]) -> Dict[str, Any]:
    raw = run.get("summary")
    return raw if isinstance(raw, dict) else {}


def _pick_metric(
    run: Dict[str, Any],
    summary_key: str,
    top_level_fallbacks: List[str],
) -> Optional[float]:
    summary = _summary_obj(run)
    v = _safe_number(summary.get(summary_key))
    if v is not None:
        return v

    for key in top_level_fallbacks:
        v = _safe_number(run.get(key))
        if v is not None:
            return v

    metrics = run.get("metrics")
    if isinstance(metrics, dict):
        for key in top_level_fallbacks:
            v = _safe_number(metrics.get(key))
            if v is not None:
                return v

    # decision.signals fallbacks for newer payloads
    for blk_name in ("decision", "monitor_decision"):
        blk = run.get(blk_name)
        if isinstance(blk, dict):
            signals = blk.get("signals")
            if isinstance(signals, dict):
                sig_key_map = {
                    "drifted_pred_ks": ["prediction_ks", "pred_ks"],
                    "drifted_entropy_change": ["entropy_change", "delta_entropy"],
                    "clean_health": ["clean_health"],
                    "drifted_health": ["drifted_health"],
                }
                for sig_key in sig_key_map.get(summary_key, []):
                    v = _safe_number(signals.get(sig_key))
                    if v is not None:
                        return v

    return None


def _pick_last_window_feature(run: Dict[str, Any]) -> Optional[str]:
    summary = _summary_obj(run)
    name = _safe_str(summary.get("drifted_last_window_feature"))
    if name:
        return name

    # Legacy fallback
    mdf = run.get("most_drifted_feature")
    if isinstance(mdf, dict):
        return _safe_str(mdf.get("feature")) or _safe_str(mdf.get("name"))

    metrics = run.get("metrics")
    if isinstance(metrics, dict):
        mdf = metrics.get("most_drifted_feature")
        if isinstance(mdf, dict):
            return _safe_str(mdf.get("feature")) or _safe_str(mdf.get("name"))

    return None


def _pick_last_window_ks(run: Dict[str, Any]) -> Optional[float]:
    summary = _summary_obj(run)
    ks = _safe_number(summary.get("drifted_last_window_ks"))
    if ks is not None:
        return ks

    # Legacy fallback
    mdf = run.get("most_drifted_feature")
    if isinstance(mdf, dict):
        ks = _safe_number(mdf.get("ks"))
        if ks is not None:
            return ks
        ks = _safe_number(mdf.get("ks_statistic"))
        if ks is not None:
            return ks

    metrics = run.get("metrics")
    if isinstance(metrics, dict):
        mdf = metrics.get("most_drifted_feature")
        if isinstance(mdf, dict):
            ks = _safe_number(mdf.get("ks"))
            if ks is not None:
                return ks
            ks = _safe_number(mdf.get("ks_statistic"))
            if ks is not None:
                return ks

    return None


def slim_run_payload(run: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return only what the UI needs for lists/history.
    Safe for older and newer run schemas.
    """
    evaluation = run.get("evaluation") if isinstance(run.get("evaluation"), dict) else None

    return {
        "saved_at": run.get("saved_at"),
        "run_id": run.get("run_id"),
        "generated_at": run.get("generated_at"),
        "status": _best_status(run),
        "window_size": run.get("window_size"),
        "clean_health": _pick_metric(run, "clean_health", ["clean_health"]),
        "drifted_health": _pick_metric(run, "drifted_health", ["drifted_health"]),
        "drifted_pred_ks": _pick_metric(run, "drifted_pred_ks", ["pred_ks", "drifted_pred_ks"]),
        "drifted_entropy_change": _pick_metric(run, "drifted_entropy_change", ["delta_entropy", "drifted_entropy_change"]),
        "drifted_last_window_feature": _pick_last_window_feature(run),
        "drifted_last_window_ks": _pick_last_window_ks(run),
        "evaluation": evaluation,
        "series_hash": run.get("series_hash"),
        "payload_hash": run.get("payload_hash"),
    }


def normalize_history_item(it: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize one history_index entry to the UI shape expected by app.js.
    Safe for missing fields and mixed versions of history_index schema.
    """
    status = _safe_str(it.get("status")) or _safe_str(it.get("state")) or "UNKNOWN"

    pred_ks = _safe_number(it.get("drifted_pred_ks"))
    if pred_ks is None:
        pred_ks = _safe_number(it.get("pred_ks"))

    delta_entropy = _safe_number(it.get("drifted_entropy_change"))
    if delta_entropy is None:
        delta_entropy = _safe_number(it.get("delta_entropy"))

    saved_at = it.get("saved_at") or it.get("generated_at")

    return {
        "saved_at": saved_at,
        "run_id": it.get("run_id"),
        "generated_at": it.get("generated_at"),
        "status": status,
        "clean_health": _safe_number(it.get("clean_health")),
        "drifted_health": _safe_number(it.get("drifted_health")),
        "drifted_pred_ks": pred_ks,
        "drifted_entropy_change": delta_entropy,
        "drifted_last_window_feature": it.get("drifted_last_window_feature"),
        "drifted_last_window_ks": _safe_number(it.get("drifted_last_window_ks")),
        "payload_hash": it.get("payload_hash"),
        "series_hash": it.get("series_hash"),
    }


def sort_history_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort by generated_at desc, fallback to saved_at desc, fallback to run_id desc.
    """
    def _key(it: Dict[str, Any]):
        dt_gen = _parse_iso_dt(it.get("generated_at"))
        dt_saved = _parse_iso_dt(it.get("saved_at"))
        rid = str(it.get("run_id") or "")
        # bool flags let valid dates sort ahead of missing values
        return (
            dt_gen is not None,
            _sort_dt_key(dt_gen) if dt_gen is not None else datetime.min.replace(tzinfo=timezone.utc),
            dt_saved is not None,
            _sort_dt_key(dt_saved) if dt_saved is not None else datetime.min.replace(tzinfo=timezone.utc),
            rid,
        )

    return sorted(items, key=_key, reverse=True)


def _history_from_index(n: int) -> Optional[List[Dict[str, Any]]]:
    """
    Reads history from history_index.json if present.
    Supports:
      {"items": [...]}  (preferred)
      {"runs": [...]}   (legacy alternate key)
    Returns None if file/schema unavailable.
    """
    idx = read_json(HISTORY_INDEX_JSON)
    items = None

    if isinstance(idx.get("items"), list):
        items = idx.get("items")
    elif isinstance(idx.get("runs"), list):
        items = idx.get("runs")

    if not isinstance(items, list):
        return None

    normalized = [normalize_history_item(it) for it in items if isinstance(it, dict)]
    normalized = sort_history_items(normalized)
    return normalized[:n]


def _history_from_runs_scan(n: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    if not RUNS_DIR.exists():
        return out

    for p in RUNS_DIR.glob("*.json"):
        run = read_json(p)
        if isinstance(run, dict) and run:
            item = slim_run_payload(run)

            # Fill saved_at from file mtime if not present in payload
            if not item.get("saved_at"):
                try:
                    item["saved_at"] = datetime.fromtimestamp(
                        p.stat().st_mtime
                    ).isoformat(timespec="seconds")
                except Exception:
                    item["saved_at"] = item.get("generated_at")

            out.append(item)

    out = sort_history_items(out)
    return out[:n]


def _clear_history_files() -> Dict[str, Any]:
    """
    Clears archived history artifacts while keeping latest.json and report_latest.html intact.
    Also resets previous.json and history_index.json.

    Deletes:
    - dashboard_web/data/runs/*.json
    - dashboard_web/data/runs/*.report.html

    Resets:
    - dashboard_web/data/history_index.json -> empty items
    - dashboard_web/data/previous.json -> {}
    """
    ensure_dirs()

    deleted_run_json = 0
    deleted_run_reports = 0
    errors: List[str] = []

    for p in RUNS_DIR.iterdir():
        if not p.is_file():
            continue

        try:
            # exact suffix handling to avoid accidental deletions
            if p.name.endswith(".report.html"):
                p.unlink(missing_ok=True)
                deleted_run_reports += 1
            elif p.suffix == ".json":
                p.unlink(missing_ok=True)
                deleted_run_json += 1
        except Exception as exc:
            errors.append(f"{p.name}: {exc}")

    try:
        write_json_atomic(HISTORY_INDEX_JSON, {
            "schema_version": 1,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "count": 0,
            "items": [],
        })
    except Exception as exc:
        errors.append(f"history_index.json: {exc}")

    try:
        write_json_atomic(PREVIOUS_JSON, {})
    except Exception as exc:
        errors.append(f"previous.json: {exc}")

    return {
        "deleted_run_json": deleted_run_json,
        "deleted_run_reports": deleted_run_reports,
        "errors": errors,
    }


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/health")
def api_health(response: Response):
    """
    Lightweight backend health endpoint.
    """
    ensure_dirs()
    payload = {
        "ok": True,
        "service": "modelshift-lite-dashboard",
        "paths": {
            "data_dir": str(DATA_DIR),
            "runs_dir": str(RUNS_DIR),
        },
        "files": {
            "latest_exists": LATEST_JSON.exists(),
            "previous_exists": PREVIOUS_JSON.exists(),
            "history_index_exists": HISTORY_INDEX_JSON.exists(),
            "report_latest_exists": REPORT_LATEST_HTML.exists(),
            "heartbeat_exists": LIVE_HEARTBEAT.exists(),
        },
        "live_connected": _is_live_connected(),
        "results_stale_after_sec": RESULTS_STALE_AFTER_SEC,
        "server_time": datetime.now().isoformat(timespec="seconds"),
    }
    no_cache_headers(response)
    return payload


@app.get("/api/results")
def api_results(response: Response):
    """
    Returns latest + previous payloads only if a fresh live signal exists.
    If nothing is actively updating the dashboard, return empty objects
    so the UI shows '-' instead of stale values.
    Also returns live_connected flag for frontend messaging.
    """
    ensure_dirs()

    live_connected = _is_live_connected()

    if not live_connected:
        no_cache_headers(response)
        return {"latest": {}, "previous": {}, "live_connected": False}

    latest = read_json(LATEST_JSON)
    if not latest:
        no_cache_headers(response)
        return {"latest": {}, "previous": {}, "live_connected": False}

    previous = read_json(PREVIOUS_JSON)

    no_cache_headers(response)
    return {"latest": latest, "previous": previous, "live_connected": True}


@app.get("/api/run/{run_id}")
def api_run(run_id: str, response: Response):
    """
    Return full archived run payload from:
      dashboard_web/data/runs/{run_id}.json
    """
    ensure_dirs()

    p = safe_run_path(run_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    payload = read_json(p)
    if not payload:
        raise HTTPException(status_code=500, detail="Run file is empty or invalid JSON")

    no_cache_headers(response)
    return payload


@app.get("/api/history")
def api_history(
    response: Response,
    n: int = Query(default=20, ge=1, le=200),
):
    """
    History for the History tab.

    Prefer dashboard_web/data/history_index.json (fast).
    Falls back to scanning runs/*.json.
    """
    ensure_dirs()

    items = _history_from_index(n)
    source = "history_index"

    if items is None:
        items = _history_from_runs_scan(n)
        source = "scan_runs"

    no_cache_headers(response)
    return {"runs": items, "source": source}


@app.post("/api/history/clear")
def api_history_clear(response: Response):
    """
    Clears archived history and resets previous pointer.
    """
    result = _clear_history_files()
    ok = len(result.get("errors", [])) == 0

    no_cache_headers(response)
    return {
        "ok": ok,
        "message": "History cleared" if ok else "History cleared with some errors",
        **result,
    }


@app.get("/api/report/latest", response_class=HTMLResponse)
def api_report_latest(download: int = Query(default=0, ge=0, le=1)):
    """
    Returns the latest generated report HTML if available.
    If download=1 => Content-Disposition attachment.
    """
    ensure_dirs()

    html = read_text(REPORT_LATEST_HTML)
    filename = "ModelShift-Lite_Report_Latest.html"

    # fallback: try latest run report by run_id
    if not html:
        latest = read_json(LATEST_JSON)
        rid = latest.get("run_id")
        if isinstance(rid, str) and SAFE_RUN_ID_RE.match(rid):
            html = read_text(safe_report_path(rid))
            filename = f"{rid}.report.html"

    if not html:
        raise HTTPException(status_code=404, detail="No report available yet")

    resp = HTMLResponse(content=html)
    if download == 1:
        resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    no_cache_headers(resp)
    return resp


@app.get("/api/report/{run_id}", response_class=HTMLResponse)
def api_report_run(
    run_id: str,
    download: int = Query(default=0, ge=0, le=1),
):
    """
    Returns archived report HTML for a given run_id if available.
    If download=1 => attachment.
    """
    ensure_dirs()

    p = safe_report_path(run_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Report not found for this run_id")

    html = read_text(p)
    if not html:
        raise HTTPException(status_code=500, detail="Report file is empty/unreadable")

    resp = HTMLResponse(content=html)
    if download == 1:
        resp.headers["Content-Disposition"] = f'attachment; filename="{run_id}.report.html"'

    no_cache_headers(resp)
    return resp
@app.get("/api/selftest")
def api_selftest(response: Response):
    ensure_dirs()
    data = read_json(SELFTEST_JSON)
    no_cache_headers(response)
    return data if data else {"ok": False, "message": "No self-test run yet."}


@app.post("/api/selftest/run")
def api_selftest_run(response: Response):
    ensure_dirs()

    # run from modelshift-lite/ so "modelshift" imports work
    cwd = str(BASE_DIR.parent)  # .../modelshift-lite
    cmd = [sys.executable, "-m", "modelshift.selftest", "--out", str(SELFTEST_JSON)]

    try:
        subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        no_cache_headers(response)
        return {
            "ok": False,
            "message": "Self-test failed to run",
            "stderr": (e.stderr or "")[:2000],
            "stdout": (e.stdout or "")[:2000],
        }

    data = read_json(SELFTEST_JSON)
    no_cache_headers(response)
    return data if data else {"ok": False, "message": "Self-test ran, but output file missing/invalid."}