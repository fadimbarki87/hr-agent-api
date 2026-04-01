# HR Data QA Agent

A bilingual HR question-answering app that combines deterministic SQL querying with semantic search over employee performance reviews.

The project answers structured HR questions, such as reporting lines, salaries, hire dates, department counts, and absences, by converting natural language into SQLite queries. For review-based questions like leadership potential or communication issues, it uses FAISS and Azure OpenAI embeddings to retrieve relevant employees semantically.

It supports English and German input and routes questions through three modes:
- SQL only
- semantic review search
- hybrid semantic + SQL filtering

## Tech Stack

- Python
- Flask
- SQLite
- pandas
- FAISS
- Azure OpenAI

## Highlights

- Natural-language-to-SQL with read-only SQL guardrails
- FAISS-based semantic retrieval over `performance_review`
- Hybrid routing for mixed structured and semantic HR questions
- English/German normalization layer
- Deterministic tabular output with optional answer rewriting

## Example Questions

- Who reports to Frank Neumann?
- How many employees are in each department?
- Which employees show leadership potential?
- Which employees in Engineering need communication improvement?

## Run Locally

```bash
pip install -r requirements.txt
python app.py

Set these environment variables before running:

AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_DEPLOYMENT
AZURE_OPENAI_API_VERSION
AZURE_OPENAI_API_KEY
AZURE_OPENAI_EMBEDDING_DEPLOYMENT
Notes

