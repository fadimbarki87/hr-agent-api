HR Data QA Agent

A bilingual HR question-answering system built on structured employee data and unstructured performance reviews. The system combines deterministic natural-language-to-SQL routing for factual HR queries with FAISS-based semantic retrieval for review-related questions.

It supports English and German input, validates SQL before execution, and optionally converts deterministic outputs into short natural-language answers. The focus is on building a controlled backend system, not a generic chatbot.

Why this project

HR questions mix structured and semantic information.

Examples:

Who reports to Frank Neumann?
Which employees in Engineering show leadership potential?
How many sick absences were recorded?
Which employees need communication improvement?

Pure SQL cannot handle review text. Pure LLMs are unreliable for facts.

This system combines:

deterministic SQL for structured queries
semantic retrieval for performance reviews

Result: reliable + flexible.

Architecture

User Question
→ Normalization (EN/DE mapping, spelling cleanup, date normalization)
→ Route Detection
→ SQL OR Semantic OR Hybrid
→ Deterministic Output
→ Optional Natural Language Answer

Key Features
Deterministic natural-language-to-SQL routing
FAISS semantic search over performance reviews
Hybrid retrieval
English and German support
Read-only SQL validation
Optional answer generation
Flask web interface
Project Structure
.
├── static/
├── templates/
├── absences.csv
├── agent.py
├── app.py
├── departments.csv
├── employees.csv
├── hr_data_files.json
├── requirements.txt
└── README.md
How It Works
1. Data Loading

CSV files → in-memory SQLite
Fast, simple, reproducible.

2. Question Normalization
EN/DE mapping
spelling normalization
umlauts (ä → ae, etc.)
accent removal
date normalization
3. Query Routing

Three modes:

SQL

departments
salaries
hire dates
absences

Semantic

performance reviews

Hybrid

both combined

Example:
Employees in Engineering with leadership potential

4. SQL Generation

Azure OpenAI → SQL

Constraints:

SELECT only
schema-safe
no modifications
5. Semantic Search

Steps:

embed query
FAISS retrieval
return similar employees

Handles:

leadership
mentoring
communication issues
strategy
6. Deterministic Output
employee_id | first_name | last_name | job_title | department_name
12 | Anna | Keller | Software Engineer | Engineering
7. Optional Answer

LLM rewrites result:

same language
no extra facts
based only on SQL
Design Decisions

Deterministic SQL
Prevents hallucination.

FAISS
Handles flexible language.

Hybrid routing
Combines structure + meaning.

Bilingual normalization
Improves robustness.

Example Questions

English

Show all employees in Engineering
Who reports to Frank Neumann?
Which employees show leadership potential?

German

Zeige alle Krankheitsausfälle
Wer berichtet an Frank Neumann?
Welche Mitarbeiter zeigen Führungspotenzial?
Evaluation

Works well

structured queries
hybrid queries
semantic matching

Limitations

ambiguous questions
weak review signals
schema gaps
Azure OpenAI Config
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_DEPLOYMENT
AZURE_OPENAI_API_VERSION
AZURE_OPENAI_API_KEY
AZURE_OPENAI_EMBEDDING_DEPLOYMENT
Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
Safety Model

Only SELECT allowed.

Blocked:

INSERT
UPDATE
DELETE
DROP
ALTER
CREATE

Responses:

Unsupported or vague question.
Empty result.
Use Cases
HR analytics
NL-to-SQL systems
semantic search demos
internal tools
Limitations
in-memory DB
limited semantic scope
no auth
depends on embeddings
Main Files
app.py → Flask app
agent.py → logic
templates → UI
static → styles
License

Add your preferred license.
