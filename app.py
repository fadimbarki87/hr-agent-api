from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.requests import Request
from pydantic import BaseModel
import pandas as pd
import json
import agent

app = FastAPI(title="HR Agent API")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


class AskRequest(BaseModel):
    question: str
    use_ai_formulation: bool = True


with open("hr_data_files.json", "r", encoding="utf-8") as f:
    file_config = json.load(f)

TABLE_FILES = {
    "employees": file_config["EMPLOYEES_FILE"],
    "departments": file_config["DEPARTMENTS_FILE"],
    "absences": file_config["ABSENCES_FILE"],
}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask(req: AskRequest):
    answer = agent.hr_agent(
        req.question,
        use_ai_formulation=req.use_ai_formulation
    )
    return {
        "question": req.question,
        "answer": answer
    }


@app.get("/data/{table_name}")
def get_table_data(table_name: str):
    if table_name not in TABLE_FILES:
        raise HTTPException(status_code=404, detail="Table not found")

    df = pd.read_csv(TABLE_FILES[table_name])

    return {
        "table": table_name,
        "columns": list(df.columns),
        "rows": df.fillna("").to_dict(orient="records")
    }


@app.get("/download/{table_name}")
def download_table(table_name: str):
    if table_name not in TABLE_FILES:
        raise HTTPException(status_code=404, detail="Table not found")

    return FileResponse(
        TABLE_FILES[table_name],
        media_type="text/csv",
        filename=f"{table_name}.csv"
    )
