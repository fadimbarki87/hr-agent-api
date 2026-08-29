from __future__ import annotations

import hmac
import json
import logging
from pathlib import Path
import time
import uuid

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

import agent
from hr_agent.guidance import (
    UNSUPPORTED_GUIDANCE_PROMPT_SHA256,
    UNSUPPORTED_GUIDANCE_PROMPT_VERSION,
)
from hr_agent.planner import (
    PLAN_AUDIT_PROMPT_SHA256,
    PLAN_AUDIT_PROMPT_VERSION,
    PLAN_REPAIR_POLICY_SHA256,
    PLAN_REPAIR_POLICY_VERSION,
    PLANNER_PROMPT_SHA256,
    PLANNER_PROMPT_VERSION,
)
from hr_agent.retrieval import RERANK_PROMPT_SHA256, RERANK_PROMPT_VERSION
from hr_agent.settings import Settings


PROJECT_ROOT = Path(__file__).resolve().parent
RUNTIME_SETTINGS = Settings.from_environment()
LOGGER = logging.getLogger("hr_agent.api")

app = FastAPI(title="HR Agent API")
app.mount(
    "/static",
    StaticFiles(directory=str(PROJECT_ROOT / "static")),
    name="static",
)
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    use_ai_formulation: bool = True


with (PROJECT_ROOT / "hr_data_files.json").open(encoding="utf-8") as file:
    file_config = json.load(file)

TABLE_FILES = {
    "employees": PROJECT_ROOT / file_config["EMPLOYEES_FILE"],
    "departments": PROJECT_ROOT / file_config["DEPARTMENTS_FILE"],
    "absences": PROJECT_ROOT / file_config["ABSENCES_FILE"],
}


def _presented_api_key(request: Request) -> str:
    direct_key = request.headers.get("x-api-key", "")
    if direct_key:
        return direct_key
    authorization = request.headers.get("authorization", "")
    scheme, separator, credential = authorization.partition(" ")
    if separator and scheme.casefold() == "bearer":
        return credential.strip()
    return ""


def require_api_access(request: Request) -> None:
    """Require a caller key only when HR_AGENT_API_KEY is configured."""
    configured_key = RUNTIME_SETTINGS.api_access_key
    if not configured_key:
        return
    if not hmac.compare_digest(_presented_api_key(request), configured_key):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API credential",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_data_endpoints() -> None:
    if not RUNTIME_SETTINGS.enable_data_endpoints:
        raise HTTPException(status_code=404, detail="Not found")


@app.middleware("http")
async def add_response_safeguards(request: Request, call_next):
    request.state.request_id = uuid.uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith(("/ask", "/data/", "/download/")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def readiness():
    missing_files = sorted(
        table_name for table_name, path in TABLE_FILES.items() if not path.is_file()
    )
    missing_services = []
    if not RUNTIME_SETTINGS.chat_is_configured:
        missing_services.append("azure_chat")
    if not RUNTIME_SETTINGS.embeddings_are_configured:
        missing_services.append("azure_embeddings")
    if missing_files or missing_services:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "missing_files": missing_files,
                "missing_services": missing_services,
            },
        )
    return {
        "status": "ready",
        "planner_prompt_version": PLANNER_PROMPT_VERSION,
        "planner_prompt_sha256": PLANNER_PROMPT_SHA256,
        "plan_audit_prompt_version": PLAN_AUDIT_PROMPT_VERSION,
        "plan_audit_prompt_sha256": PLAN_AUDIT_PROMPT_SHA256,
        "plan_repair_policy_version": PLAN_REPAIR_POLICY_VERSION,
        "plan_repair_policy_sha256": PLAN_REPAIR_POLICY_SHA256,
        "rerank_prompt_version": RERANK_PROMPT_VERSION,
        "rerank_prompt_sha256": RERANK_PROMPT_SHA256,
        "unsupported_guidance_prompt_version": (
            UNSUPPORTED_GUIDANCE_PROMPT_VERSION
        ),
        "unsupported_guidance_prompt_sha256": (
            UNSUPPORTED_GUIDANCE_PROMPT_SHA256
        ),
    }


@app.post("/ask", dependencies=[Depends(require_api_access)])
def ask(req: AskRequest, request: Request):
    started = time.monotonic()
    traced = agent.hr_agent_with_trace(
        req.question,
        use_ai_formulation=req.use_ai_formulation,
    )
    evidence = traced["evidence"]
    LOGGER.info(
        "request_id=%s event=ask_completed route=%s status=%s duration_ms=%d",
        request.state.request_id,
        evidence.get("route_used", "unavailable"),
        evidence.get("status", "unavailable"),
        round((time.monotonic() - started) * 1000),
    )
    response = {
        "question": req.question,
        "answer": traced["answer"],
    }
    if RUNTIME_SETTINGS.expose_evidence:
        response["evidence"] = evidence
    return response


@app.get(
    "/data/{table_name}",
    dependencies=[Depends(require_api_access), Depends(require_data_endpoints)],
)
def get_table_data(table_name: str):
    if table_name not in TABLE_FILES:
        raise HTTPException(status_code=404, detail="Table not found")

    dataframe = pd.read_csv(TABLE_FILES[table_name])
    return {
        "table": table_name,
        "columns": list(dataframe.columns),
        "rows": dataframe.fillna("").to_dict(orient="records"),
    }


@app.get(
    "/download/{table_name}",
    dependencies=[Depends(require_api_access), Depends(require_data_endpoints)],
)
def download_table(table_name: str):
    if table_name not in TABLE_FILES:
        raise HTTPException(status_code=404, detail="Table not found")

    return FileResponse(
        str(TABLE_FILES[table_name]),
        media_type="text/csv",
        filename=f"{table_name}.csv",
    )
