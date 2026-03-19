
from fastapi import FastAPI
from pydantic import BaseModel
import agent

app = FastAPI(title="HR Agent API")


class AskRequest(BaseModel):
    question: str
    use_ai_formulation: bool = True


@app.get("/")
def root():
    return {"message": "HR Agent API is running"}


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
