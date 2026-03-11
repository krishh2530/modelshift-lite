# dashboard_web/selftest_app.py

from pathlib import Path
import time
from typing import Dict, Any

from fastapi import FastAPI, Query, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

# Correct import from package
from modelshift.selftest import run_selftest


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"


app = FastAPI(title="ModelShift-Lite SelfTest Harness")


# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def no_cache(resp: Response) -> None:
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("selftest.html", {"request": request})


@app.get("/api/selftest")
def api_selftest(
    response: Response,
    test: str = Query(default="suite"),
    seed: int = Query(default=7, ge=0, le=10_000_000),
):
    t0 = time.time()

    # run self test
    out: Dict[str, Any] = run_selftest(seed=seed, test=test)

    # add server timing
    out["server_elapsed_ms"] = int((time.time() - t0) * 1000)

    no_cache(response)

    return JSONResponse(content=out)