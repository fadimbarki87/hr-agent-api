# HR Data QA Agent

A bilingual HR question-answering system that combines deterministic SQL querying with semantic search over employee performance reviews.

The system answers structured HR questions, such as reporting lines, salaries, hire dates, department counts, and absences, by converting natural language into SQLite queries. For review-based queries like leadership potential or communication issues, it uses FAISS with Azure OpenAI embeddings to retrieve relevant employees.

It supports English and German input and routes questions through three modes:
- SQL only
- semantic review search
- hybrid (semantic + SQL filtering)

## Tech Stack

- Python
- Flask
- SQLite
- pandas
- FAISS
- Azure OpenAI

## Highlights

- Built a natural-language-to-SQL pipeline with strict read-only SQL validation
- Implemented semantic search over unstructured performance reviews using FAISS
- Designed a hybrid retrieval system combining vector search with structured SQL filtering
- Developed a bilingual normalization layer for English and German queries
- Ensured deterministic outputs to avoid hallucinations in factual queries

## Example Questions

- Who reports to Frank Neumann?
- How many employees are in each department?
- Which employees show leadership potential?
- Which employees in Engineering need communication improvement?

## Run Locally

```bash
pip install -r requirements.txt
python app.py

Set environment variables:

AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_DEPLOYMENT
AZURE_OPENAI_API_VERSION
AZURE_OPENAI_API_KEY
AZURE_OPENAI_EMBEDDING_DEPLOYMENT
