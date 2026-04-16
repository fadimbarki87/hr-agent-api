
# # Colab HR Agent, updated in one cell, with FAISS added for semantic search on employees.performance_review
from __future__ import annotations
import os
import re
import json
import sqlite3
import requests
import pandas as pd
import numpy as np
import unicodedata
import sys
import subprocess

# --- FAISS import/install for Colab ---
try:
    import faiss
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "faiss-cpu"])
    import faiss

DEBUG = False

UNSUPPORTED_MSG = "Unsupported or vague question."
EMPTY_MSG = "Empty result."

# -----------------------------------------------------------------------------
# 1) Azure OpenAI config
# -----------------------------------------------------------------------------
# Put your real values here, or set them in the environment before running.
os.environ["AZURE_OPENAI_ENDPOINT"] = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
os.environ["AZURE_OPENAI_DEPLOYMENT"] = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")
os.environ["AZURE_OPENAI_API_VERSION"] = os.environ.get("AZURE_OPENAI_API_VERSION", "")
os.environ["AZURE_OPENAI_API_KEY"] = os.environ.get("AZURE_OPENAI_API_KEY", "")

# Separate embedding deployment
os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"] = os.environ.get(
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
    ""
)

AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
AZURE_OPENAI_DEPLOYMENT = os.environ["AZURE_OPENAI_DEPLOYMENT"]
AZURE_OPENAI_API_VERSION = os.environ["AZURE_OPENAI_API_VERSION"]
AZURE_OPENAI_API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]

# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# 3) 
# -----------------------------------------------------------------------------
with open("hr_data_files.json", "r", encoding="utf-8") as f:
    file_config = json.load(f)

EMPLOYEES_FILE = file_config["EMPLOYEES_FILE"]
DEPARTMENTS_FILE = file_config["DEPARTMENTS_FILE"]
ABSENCES_FILE = file_config["ABSENCES_FILE"]

print("Detected files:")
print(" - employees:", EMPLOYEES_FILE)
print(" - departments:", DEPARTMENTS_FILE)
print(" - absences:", ABSENCES_FILE)
# -----------------------------------------------------------------------------
# 4) Build in-memory SQLite DB
# -----------------------------------------------------------------------------
def make_hr_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)

    employees_df = pd.read_csv(EMPLOYEES_FILE)
    departments_df = pd.read_csv(DEPARTMENTS_FILE)
    absences_df = pd.read_csv(ABSENCES_FILE)

    employees_df.to_sql("employees", conn, index=False, if_exists="replace")
    departments_df.to_sql("departments", conn, index=False, if_exists="replace")
    absences_df.to_sql("absences", conn, index=False, if_exists="replace")

    return conn


conn = make_hr_db()

# -----------------------------------------------------------------------------
# 4b) Small text helpers for semantic normalization
# -----------------------------------------------------------------------------
def fold_umlauts_and_ascii(text: str) -> str:
    replacements = {
        "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
        "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
    }
    out = text
    for src, dst in replacements.items():
        out = out.replace(src, dst)
    return out

def strip_accents_to_ascii(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )

def semantic_text_variants(text: str) -> str:
    """
    Build a richer semantic text with German spelling variants.
    """
    base = text.strip()
    umlaut_folded = fold_umlauts_and_ascii(base)
    ascii_folded = strip_accents_to_ascii(base)

    # Common semantic spelling variants
    variants = [
        base,
        umlaut_folded,
        ascii_folded,
        base.replace("potenzial", "potential"),
        umlaut_folded.replace("potenzial", "potential"),
        ascii_folded.replace("potenzial", "potential"),
        base.replace("führung", "fuehrung"),
        base.replace("führung", "fuhrung"),
        umlaut_folded.replace("fuehrung", "fuhrung"),
        ascii_folded,
    ]

    seen = []
    for v in variants:
        v = re.sub(r"\s+", " ", v).strip()
        if v and v not in seen:
            seen.append(v)

    return "\n".join(seen)

# -----------------------------------------------------------------------------
# 4c) Azure embedding helpers
# -----------------------------------------------------------------------------
def azure_embed_text(text: str) -> list[float] | None:
    url = f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_OPENAI_EMBEDDING_DEPLOYMENT}/embeddings?api-version={AZURE_OPENAI_API_VERSION}"
    headers = {"Content-Type": "application/json", "api-key": AZURE_OPENAI_API_KEY}
    payload = {"input": text}

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        if DEBUG:
            print("embedding status code:", r.status_code)
            print("embedding body preview:", r.text[:300] if hasattr(r, "text") else "")

        if not r.ok:
            return None

        data = r.json()
        return data["data"][0]["embedding"]
    except Exception as e:
        if DEBUG:
            print("embedding exception:", repr(e))
        return None


def l2_normalize_matrix(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return x / norms

# -----------------------------------------------------------------------------
# 4d) Build FAISS index once for employees.performance_review
# -----------------------------------------------------------------------------
FAISS_READY = False
review_index = None
review_metadata = []
review_vectors = None

REVIEW_ANCHOR_RULES = [
    ("leadership potential", ["leadership potential", "leadership", "führungspotenzial", "fuehrungspotenzial", "fuhrungspotenzial", "führungspotential", "fuehrungspotential", "fuhrungspotential"]),
    ("strong leadership", ["leadership", "leader", "führung", "fuehrung", "fuhrung"]),
    ("experienced leader", ["leadership", "leader", "führung", "fuehrung", "fuhrung"]),
    ("communication", ["communication", "kommunikation"]),
    ("mentors junior staff", ["mentoring", "mentor", "mentors", "coaching", "mentoring others", "mentor fuer junioren", "mentor für junioren"]),
    ("strategic thinking", ["strategic thinking", "strategic", "strategie", "strategisch"]),
    ("analytical skills", ["analytical", "analytics", "analytisch", "analytische fähigkeiten", "analytische fahigkeiten"]),
    ("attention to detail", ["detail-oriented", "attention to detail", "detailorientiert", "detailorientierung"]),
    ("organized", ["organized", "organizational", "organisiert", "organisatorisch"]),
    ("problem-solving", ["problem-solving", "problem solving", "problemlösung", "problemlosung", "problemlösen", "problemloesen"]),
    ("initiative", ["initiative", "eigeninitiative"]),
    ("curiosity", ["curiosity", "neugier"]),
    ("reliable", ["reliable", "zuverlässig", "zuverlaessig"]),
    ("stability", ["stability", "stabilität", "stabilitat"]),
    ("negotiation", ["negotiation", "verhandlung"]),
    ("team performance", ["team performance", "teamleistung"]),
    ("needs guidance", ["needs guidance", "guidance", "anleitung", "unterstützung", "unterstuetzung"]),
    ("needs confidence", ["needs confidence", "confidence", "selbstvertrauen"]),
    ("improve communication", ["improve communication", "communication improvement", "kommunikation verbessern"]),
]

def build_review_anchor_text(review: str) -> str:
    low = review.lower()
    anchors = []
    for trigger, terms in REVIEW_ANCHOR_RULES:
        if trigger in low:
            anchors.extend(terms)
    anchors = sorted(set(anchors))
    return ", ".join(anchors)


def build_review_faiss_index(conn: sqlite3.Connection):
    global FAISS_READY, review_index, review_metadata, review_vectors

    sql = """
    SELECT
        e.employee_id,
        e.first_name,
        e.last_name,
        e.job_title,
        d.department_name,
        e.performance_review
    FROM employees e
    LEFT JOIN departments d
        ON e.department_id = d.department_id
    WHERE e.performance_review IS NOT NULL
      AND TRIM(e.performance_review) <> ''
    ORDER BY e.employee_id
    """

    df = pd.read_sql_query(sql, conn)
    if df.empty:
        FAISS_READY = False
        review_index = None
        review_metadata = []
        review_vectors = None
        return

    texts = []
    metadata = []

    for _, row in df.iterrows():
        anchor_text = build_review_anchor_text(str(row["performance_review"]))
        review_text = (
            f"Employee: {row['first_name']} {row['last_name']}. "
            f"Job title: {row['job_title']}. "
            f"Department: {row['department_name']}. "
            f"Performance review: {row['performance_review']}. "
            f"Semantic tags: {anchor_text}."
        )
        semantic_doc = semantic_text_variants(review_text)
        texts.append(semantic_doc)

        metadata.append({
            "employee_id": int(row["employee_id"]),
            "first_name": str(row["first_name"]),
            "last_name": str(row["last_name"]),
            "job_title": str(row["job_title"]),
            "department_name": str(row["department_name"]),
            "performance_review": str(row["performance_review"]),
        })

    embeddings = []
    for text in texts:
        emb = azure_embed_text(text)
        if emb is None:
            FAISS_READY = False
            review_index = None
            review_metadata = []
            review_vectors = None
            return
        embeddings.append(emb)

    mat = np.array(embeddings, dtype=np.float32)
    mat = l2_normalize_matrix(mat)

    dim = mat.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(mat)

    review_index = index
    review_metadata = metadata
    review_vectors = mat
    FAISS_READY = True

build_review_faiss_index(conn)

# -----------------------------------------------------------------------------
# 5) Deterministic normalization / mapping layer
#    Bilingual: English + German
# -----------------------------------------------------------------------------
TEXT_MAPPINGS = [
    # common verbs / request style
    (r"\bzeige\b", "show"),
    (r"\bliste\b", "list"),
    (r"\balle\b", "all"),
    (r"\bwelche\b", "which"),
    (r"\bwer\b", "who"),
    (r"\bwie viele\b", "how many"),
    (r"\bgibt es\b", "are there"),
    (r"\bwurden\b", ""),
    (r"\bist\b", "is"),
    (r"\bsind\b", "are"),

    # core entities
    (r"\bemployees\b", "employees"),
    (r"\bemployee\b", "employee"),
    (r"\bmitarbeiter\b", "employees"),
    (r"\bangestellte\b", "employees"),
    (r"\bpersonal\b", "employees"),

    (r"\bdepartments\b", "departments"),
    (r"\bdepartment\b", "department"),
    (r"\babteilung\b", "department"),
    (r"\bbereich\b", "department"),
    (r"\bteam\b", "department"),

    (r"\babsences\b", "absences"),
    (r"\babsence\b", "absence"),
    (r"\babwesenheiten\b", "absences"),
    (r"\bfehlzeiten\b", "absences"),
    (r"\bleave\b", "absences"),
    (r"\btime off\b", "absences"),

    # hire date
    (r"\bhire date\b", "hire date"),
    (r"\bhired\b", "hired"),
    (r"\bjoined\b", "hired"),
    (r"\beinstellungsdatum\b", "hire date"),
    (r"\beingestellt\b", "hired"),
    (r"\beingetreten\b", "hired"),

    # salary
    (r"\bsalary\b", "salary"),
    (r"\bpay\b", "salary"),
    (r"\bcompensation\b", "salary"),
    (r"\bgehalt\b", "salary"),
    (r"\blohn\b", "salary"),
    (r"\bvergütung\b", "salary"),

    # manager
    (r"\bmanager\b", "manager"),
    (r"\bsupervisor\b", "manager"),
    (r"\breports to\b", "reports to"),
    (r"\bvorgesetzter\b", "manager"),
    (r"\bchef\b", "manager"),
    (r"\bberichtet an\b", "reports to"),

    # performance review
    (r"\bperformance review\b", "performance review"),
    (r"\breview\b", "performance review"),
    (r"\bfeedback\b", "performance review"),
    (r"\bevaluation\b", "performance review"),
    (r"\bleistungsbewertung\b", "performance review"),
    (r"\bbeurteilung\b", "performance review"),
    (r"\bbewertung\b", "performance review"),

    # names
    (r"\bfull name\b", "full name"),
    (r"\bname\b", "name"),
    (r"\bvoller name\b", "full name"),
    (r"\bvollständiger name\b", "full name"),
    (r"\bfirst name\b", "first name"),
    (r"\bvorname\b", "first name"),
    (r"\blast name\b", "last name"),
    (r"\bnachname\b", "last name"),

    # absences special phrases
    (r"\bsickness absences\b", "sick absences"),
    (r"\bkrankheitsausfälle\b", "sick absences"),
    (r"\bkrankheitsausfall\b", "sick absence"),
    (r"\bkrankmeldungen\b", "sick absences"),
    (r"\bkrankenstand\b", "sick"),
    (r"\bkrankheit\b", "sick"),
    (r"\bkrank\b", "sick"),

    # operator phrases
    (r"\bat least\b", " >= "),
    (r"\bmindestens\b", " >= "),
    (r"\bat most\b", " <= "),
    (r"\bhöchstens\b", " <= "),
    (r"\bmore than\b", " > "),
    (r"\bmehr als\b", " > "),
    (r"\bless than\b", " < "),
    (r"\bweniger als\b", " < "),
    (r"\bafter\b", " > "),
    (r"\bnach\b", " > "),
    (r"\bbefore\b", " < "),
    (r"\bvor\b", " < "),
    (r"\bgreater than\b", " > "),
    (r"\büber\b", " > "),
    (r"\bunter\b", " < "),

    # semantic German spellings
    (r"\bführungspotenzial\b", "leadership potential"),
    (r"\bführungspotential\b", "leadership potential"),
    (r"\bfuehrungspotenzial\b", "leadership potential"),
    (r"\bfuehrungspotential\b", "leadership potential"),
    (r"\bfuhrungspotenzial\b", "leadership potential"),
    (r"\bfuhrungspotential\b", "leadership potential"),
    (r"\bkommunikation verbessern\b", "improve communication"),
    (r"\banalytische fähigkeiten\b", "analytical skills"),
    (r"\banalytische fahigkeiten\b", "analytical skills"),
    (r"\borganisiert\b", "organized"),
    (r"\borganisatorisch\b", "organizational"),
    (r"\bdetailorientiert\b", "detail-oriented"),
    (r"\bstrategisch\b", "strategic"),
    (r"\bmentoring\b", "mentoring"),
    (r"\bmentor\b", "mentor"),
]

DEPARTMENT_VALUE_MAPPINGS = [
    (r"\bengineering\b", "Engineering"),
    (r"\beng\b", "Engineering"),
    (r"\btech\b", "Engineering"),
    (r"\bentwicklung\b", "Engineering"),
    (r"\btechnik\b", "Engineering"),

    (r"\bhr\b", "HR"),
    (r"\bhuman resources\b", "HR"),
    (r"\bpeople\b", "HR"),
    (r"\bpersonalabteilung\b", "HR"),

    (r"\bsales\b", "Sales"),
    (r"\bvertrieb\b", "Sales"),
    (r"\bcommercial\b", "Sales"),
]

ABSENCE_TYPE_VALUE_MAPPINGS = [
    (r"\bsick leave\b", "sick"),
    (r"\bsickness\b", "sick"),
    (r"\billness\b", "sick"),
    (r"\bmedical leave\b", "sick"),
    (r"\bsick\b", "sick"),
    (r"\bkrank\b", "sick"),
    (r"\bkrankheit\b", "sick"),
    (r"\bkrankmeldung\b", "sick"),
    (r"\bkrankenstand\b", "sick"),

    (r"\bpaid vacation\b", "paid_vacation"),
    (r"\bvaccation\b", "paid_vacation"),  # typo guard
    (r"\bvacation\b", "paid_vacation"),
    (r"\bannual leave\b", "paid_vacation"),
    (r"\bholiday\b", "paid_vacation"),
    (r"\bpto\b", "paid_vacation"),
    (r"\burlaub\b", "paid_vacation"),
    (r"\bferien\b", "paid_vacation"),
    (r"\bbezahlter urlaub\b", "paid_vacation"),

    (r"\bunpaid vacation\b", "unpaid_vacation"),
    (r"\bunpaid leave\b", "unpaid_vacation"),
    (r"\bunbezahlter urlaub\b", "unpaid_vacation"),
]

def normalize_date_formats(text: str) -> str:
    """
    Convert DD.MM.YYYY -> YYYY-MM-DD
    Example: 01.02.2024 -> 2024-02-01
    """
    def repl(match):
        dd, mm, yyyy = match.group(1), match.group(2), match.group(3)
        return f"{yyyy}-{mm}-{dd}"

    return re.sub(r"\b(\d{2})\.(\d{2})\.(\d{4})\b", repl, text)


def normalize_question(question: str) -> str:
    q = question.strip()
    q = normalize_date_formats(q)
    q = q.replace("“", '"').replace("”", '"').replace("’", "'").replace("–", "-")
    q = re.sub(r"\s+", " ", q)

    q_lower = q.lower()

    for pattern, replacement in TEXT_MAPPINGS:
        q_lower = re.sub(pattern, replacement, q_lower, flags=re.IGNORECASE)

    for pattern, replacement in DEPARTMENT_VALUE_MAPPINGS:
        q_lower = re.sub(pattern, replacement, q_lower, flags=re.IGNORECASE)

    for pattern, replacement in ABSENCE_TYPE_VALUE_MAPPINGS:
        q_lower = re.sub(pattern, replacement, q_lower, flags=re.IGNORECASE)

    q_lower = re.sub(r"\bfull name\b", "first name and last name", q_lower, flags=re.IGNORECASE)
    q_lower = re.sub(r"\s+", " ", q_lower).strip()

    return q_lower

# -----------------------------------------------------------------------------
# 5b) FAISS routing helpers
# -----------------------------------------------------------------------------
SEMANTIC_REVIEW_KEYWORDS = [
    "leadership potential", "leadership qualities", "leadership",
    "communication improvement", "improve communication", "communication skills",
    "mentoring", "mentor", "mentors", "coaching",
    "strategic thinking", "strategic", "analytical", "analytical skills",
    "organized", "organizational", "detail-oriented", "attention to detail",
    "problem-solving", "problem solving", "initiative", "curiosity",
    "reliable", "stability", "negotiation", "team performance",
    "high-quality work", "high quality work", "key contributor",
    "strengths", "weaknesses", "improvement", "potential",
]

STRUCTURED_FILTER_KEYWORDS = [
    "department", "departments", "engineering", "hr", "sales",
    "salary", "hire date", "hired", "joined", "manager", "reports to",
    "absence", "absences", "sick", "paid_vacation", "unpaid_vacation",
    "budget", "top", "how many", "count", "employee_id", "job title",
    "department_id", "manager_id", "employment_status",
    "department_name", "email", "first name", "last name"
]

EXACT_REVIEW_SQL_PATTERNS = [
    "performance review containing",
    "review containing",
    "feedback containing",
    "evaluation containing",
    "leistungsbewertung mit",
    "beurteilung mit",
    "bewertung mit"
]

def detect_question_route(normalized_question: str) -> str:
    """
    Returns one of:
    - sql_only
    - review_semantic
    - review_semantic_plus_sql
    """
    q = normalized_question.lower()

    if any(pat in q for pat in EXACT_REVIEW_SQL_PATTERNS):
        return "sql_only"

    has_semantic = any(term in q for term in SEMANTIC_REVIEW_KEYWORDS)
    has_structured = any(term in q for term in STRUCTURED_FILTER_KEYWORDS)

    if has_semantic and has_structured:
        return "review_semantic_plus_sql"
    if has_semantic:
        return "review_semantic"
    return "sql_only"

# -----------------------------------------------------------------------------
# 6) SQL safety checks
# -----------------------------------------------------------------------------
FORBIDDEN_SQL_PATTERNS = [
    r"\binsert\b",
    r"\bupdate\b",
    r"\bdelete\b",
    r"\bdrop\b",
    r"\balter\b",
    r"\bcreate\b",
    r"\breplace\b",
    r"\btruncate\b",
    r"\bpragma\b",
    r"\battach\b",
]

def is_safe_select_sql(sql: str) -> bool:
    if not sql or not isinstance(sql, str):
        return False

    s = sql.strip()
    s_no_comments = re.sub(r"--.*?$|/\*.*?\*/", "", s, flags=re.MULTILINE | re.DOTALL).strip()

    if not re.match(r"(?is)^\s*select\b", s_no_comments):
        return False

    for pat in FORBIDDEN_SQL_PATTERNS:
        if re.search(pat, s_no_comments, flags=re.IGNORECASE):
            return False

    if ";" in s_no_comments[:-1]:
        return False

    return True

# -----------------------------------------------------------------------------
# 7) Azure parser
# -----------------------------------------------------------------------------
def parse_question_to_intent(question: str, normalized_question: str, semantic_candidate_ids: list[int] | None = None) -> dict:
    url = f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions?api-version={AZURE_OPENAI_API_VERSION}"
    headers = {"Content-Type": "application/json", "api-key": AZURE_OPENAI_API_KEY}

    semantic_constraint_text = ""
    if semantic_candidate_ids:
        ids_text = ", ".join(str(x) for x in semantic_candidate_ids)
        semantic_constraint_text = f"""
ADDITIONAL SEMANTIC REVIEW CONSTRAINT
- Semantic review candidate employee_ids: [{ids_text}]
- If the question mixes review meaning with structured filters, restrict employee results to these candidate employee_ids.
- For employees table use a constraint like e.employee_id IN ({ids_text}) when appropriate.
- Zero rows after applying this constraint is still supported and must return a valid SELECT.
"""

    system_prompt = f"""
You are an HR database assistant that converts user questions into SQLite SQL.

SCHEMA
1) employees(
    employee_id,
    first_name,
    last_name,
    email,
    hire_date,
    job_title,
    department_id,
    manager_id,
    salary,
    employment_status,
    performance_review
)

2) departments(
    department_id,
    department_name,
    budget
)

3) absences(
    absence_id,
    employee_id,
    absence_type,
    start_date,
    end_date,
    days_absent,
    reason
)

KEY RELATIONS
- employees.department_id = departments.department_id
- absences.employee_id = employees.employee_id
- employees.manager_id = employees.employee_id   (manager self-join)

CANONICAL DEPARTMENT VALUES
- Engineering
- HR
- Sales

CANONICAL ABSENCE VALUES
- sick
- paid_vacation
- unpaid_vacation

{semantic_constraint_text}

STRICT RULES
- Output JSON only, no markdown, no explanations.
- JSON format must be exactly:
  {{"supported": true, "sql": "SELECT ..."}}
  or
  {{"supported": false, "sql": ""}}
- SQL must be SELECT only.
- Never generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, REPLACE, TRUNCATE, PRAGMA, ATTACH.
- Use only the schema above.
- Use proper joins when needed.
- Zero matching rows is still SUPPORTED. If the question is valid but no rows match, still return supported=true with a valid SELECT.
- Return supported=false only if the question is vague, ambiguous, unrelated to this HR database, or asks for something not represented in the schema.
- For name output, use first_name and last_name unless the user explicitly asks for another field.
- For "reports to X", join employees to employees as manager/self-join.
- For performance review text search, use LIKE with %term%.
- For top-k requests, use ORDER BY ... LIMIT k.
- For counts by department, use GROUP BY.

SQLITE EXAMPLES

English examples:
Q: Show first name and last name of all employees in Engineering department
A: {{"supported": true, "sql": "SELECT e.first_name, e.last_name FROM employees e JOIN departments d ON e.department_id = d.department_id WHERE d.department_name = 'Engineering' ORDER BY e.employee_id"}}

Q: Employees in Engineering hired after 2024-01-01
A: {{"supported": true, "sql": "SELECT e.* FROM employees e JOIN departments d ON e.department_id = d.department_id WHERE d.department_name = 'Engineering' AND e.hire_date > '2024-01-01' ORDER BY e.employee_id"}}

Q: List all sickness absences
A: {{"supported": true, "sql": "SELECT a.* FROM absences a WHERE a.absence_type = 'sick' ORDER BY a.absence_id"}}

Q: Who reports to Frank Neumann?
A: {{"supported": true, "sql": "SELECT e.first_name, e.last_name FROM employees e JOIN employees m ON e.manager_id = m.employee_id WHERE m.first_name = 'Frank' AND m.last_name = 'Neumann' ORDER BY e.employee_id"}}

Q: How many employees are in each department?
A: {{"supported": true, "sql": "SELECT d.department_name, COUNT(e.employee_id) AS employee_count FROM departments d LEFT JOIN employees e ON e.department_id = d.department_id GROUP BY d.department_id, d.department_name ORDER BY d.department_id"}}

Q: Employees in Engineering earning more than 70000 with performance review containing leadership
A: {{"supported": true, "sql": "SELECT e.* FROM employees e JOIN departments d ON e.department_id = d.department_id WHERE d.department_name = 'Engineering' AND e.salary > 70000 AND LOWER(e.performance_review) LIKE '%leadership%' ORDER BY e.employee_id"}}

Q: Top 3 highest paid employees
A: {{"supported": true, "sql": "SELECT first_name, last_name, salary FROM employees ORDER BY salary DESC, employee_id ASC LIMIT 3"}}

German examples:
Q: Zeige Vorname und Nachname aller Mitarbeiter in der Engineering Abteilung
A: {{"supported": true, "sql": "SELECT e.first_name, e.last_name FROM employees e JOIN departments d ON e.department_id = d.department_id WHERE d.department_name = 'Engineering' ORDER BY e.employee_id"}}

Q: Welche Mitarbeiter in Engineering wurden nach dem 2024-02-01 eingestellt?
A: {{"supported": true, "sql": "SELECT e.* FROM employees e JOIN departments d ON e.department_id = d.department_id WHERE d.department_name = 'Engineering' AND e.hire_date > '2024-02-01' ORDER BY e.employee_id"}}

Q: Zeige alle Krankheitsausfälle
A: {{"supported": true, "sql": "SELECT a.* FROM absences a WHERE a.absence_type = 'sick' ORDER BY a.absence_id"}}

Q: Wer berichtet an Frank Neumann?
A: {{"supported": true, "sql": "SELECT e.first_name, e.last_name FROM employees e JOIN employees m ON e.manager_id = m.employee_id WHERE m.first_name = 'Frank' AND m.last_name = 'Neumann' ORDER BY e.employee_id"}}

Q: Wie viele Mitarbeiter gibt es in jeder Abteilung?
A: {{"supported": true, "sql": "SELECT d.department_name, COUNT(e.employee_id) AS employee_count FROM departments d LEFT JOIN employees e ON e.department_id = d.department_id GROUP BY d.department_id, d.department_name ORDER BY d.department_id"}}

Unsupported examples:
Q: What is the weather today?
A: {{"supported": false, "sql": ""}}

Q: Wer ist der glücklichste Mitarbeiter?
A: {{"supported": false, "sql": ""}}

Use the normalized question as the main signal. Use the original question only if needed for names or phrasing.
"""

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Original question: {question}\nNormalized question: {normalized_question}"
            }
        ],
        "temperature": 0.0,
        "max_tokens": 500,
        "response_format": {"type": "json_object"}
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        body_preview = r.text[:500] if hasattr(r, "text") else ""

        if DEBUG:
            print("parser status code:", r.status_code)
            print("parser body preview:", body_preview)

        if not r.ok:
            return {"supported": False, "sql": ""}

        data = r.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)

        if not isinstance(parsed, dict):
            return {"supported": False, "sql": ""}

        return {
            "supported": bool(parsed.get("supported", False)),
            "sql": str(parsed.get("sql", "") or "")
        }

    except Exception as e:
        if DEBUG:
            print("parser exception:", repr(e))
        return {"supported": False, "sql": ""}

# -----------------------------------------------------------------------------
# 8) Deterministic SQL execution and formatting
# -----------------------------------------------------------------------------
def cell_to_text(v):
    if v is None:
        return "NULL"
    return str(v)


def rows_to_table_payload(columns, rows) -> dict:
    payload_rows = []

    for row in rows:
        payload_rows.append({
            col: cell_to_text(v)
            for col, v in zip(columns, row)
        })

    return {
        "columns": list(columns),
        "rows": payload_rows,
        "row_count": len(payload_rows)
    }


def format_rows_deterministically(cursor, rows) -> str:
    columns = [desc[0] for desc in cursor.description] if cursor.description else []

    header = " | ".join(columns)
    lines = [header]
    for row in rows:
        lines.append(" | ".join(cell_to_text(v) for v in row))
    return "\n".join(lines)


def execute_intent_with_trace(conn, intent: dict):
    trace = {
        "supported": bool(intent.get("supported", False)),
        "sql": str(intent.get("sql", "") or "").strip(),
        "status": "unsupported",
        "result": None,
        "reason": ""
    }

    if not trace["supported"]:
        trace["reason"] = (
            "The assistant could not safely map this question to the available HR tables and fields."
        )
        return UNSUPPORTED_MSG, trace

    sql = trace["sql"]
    if not sql:
        trace["reason"] = "The question was understood as supported, but no executable SQL was produced."
        return UNSUPPORTED_MSG, trace

    if not is_safe_select_sql(sql):
        if DEBUG:
            print("unsafe sql rejected:", sql)
        trace["reason"] = "The generated SQL did not pass the read-only safety checks."
        return UNSUPPORTED_MSG, trace

    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        trace["result"] = rows_to_table_payload(columns, rows)

        if not rows:
            trace["status"] = "empty"
            trace["reason"] = "The question is supported, but no rows matched the query."
            return EMPTY_MSG, trace

        trace["status"] = "supported"
        return format_rows_deterministically(cursor, rows), trace

    except Exception as e:
        if DEBUG:
            print("sql error:", repr(e))
            print("sql text:", sql)

        trace["reason"] = "The assistant could not execute the generated SQL successfully."
        return UNSUPPORTED_MSG, trace


def execute_intent(conn, intent: dict):
    result, _trace = execute_intent_with_trace(conn, intent)
    return result

# -----------------------------------------------------------------------------
# 8b) FAISS semantic review search helpers
# -----------------------------------------------------------------------------
def semantic_search_reviews(question: str, top_k: int = 5, score_threshold: float = 0.08) -> list[dict]:
    if not FAISS_READY or review_index is None or not review_metadata:
        return []

    semantic_query = semantic_text_variants(question)
    emb = azure_embed_text(semantic_query)
    if emb is None:
        return []

    q = np.array([emb], dtype=np.float32)
    q = l2_normalize_matrix(q)

    k = min(top_k, len(review_metadata))
    scores, indices = review_index.search(q, k)

    matches = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        if float(score) < score_threshold:
            continue

        item = dict(review_metadata[int(idx)])
        item["score"] = float(score)
        matches.append(item)

    if DEBUG:
        print("semantic query:", semantic_query)
        print("semantic matches:", [(m["employee_id"], round(m["score"], 4), m["first_name"], m["last_name"]) for m in matches])

    return matches


def format_semantic_matches_deterministically(matches: list[dict]) -> str:
    if not matches:
        return EMPTY_MSG

    columns = ["employee_id", "first_name", "last_name", "job_title", "department_name", "performance_review"]
    lines = [" | ".join(columns)]

    for m in matches:
        row = [
            str(m.get("employee_id", "")),
            str(m.get("first_name", "")),
            str(m.get("last_name", "")),
            str(m.get("job_title", "")),
            str(m.get("department_name", "")),
            str(m.get("performance_review", "")),
        ]
        lines.append(" | ".join(row))

    return "\n".join(lines)


def semantic_matches_to_table_payload(matches: list[dict]) -> dict:
    columns = [
        "employee_id",
        "first_name",
        "last_name",
        "job_title",
        "department_name",
        "performance_review",
        "score",
    ]

    rows = []
    for m in matches:
        rows.append({
            "employee_id": cell_to_text(m.get("employee_id", "")),
            "first_name": cell_to_text(m.get("first_name", "")),
            "last_name": cell_to_text(m.get("last_name", "")),
            "job_title": cell_to_text(m.get("job_title", "")),
            "department_name": cell_to_text(m.get("department_name", "")),
            "performance_review": cell_to_text(m.get("performance_review", "")),
            "score": f"{float(m.get('score', 0.0)):.4f}",
        })

    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows)
    }


def get_semantic_candidate_ids(matches: list[dict], max_ids: int = 8) -> list[int]:
    ids = []
    for m in matches[:max_ids]:
        try:
            ids.append(int(m["employee_id"]))
        except Exception:
            pass
    return ids

# -----------------------------------------------------------------------------
# 9) Optional NLG answer, only for supported queries with matching rows
#    Must not add facts. Same language as the question.
# -----------------------------------------------------------------------------
def formulate_answer(question: str, deterministic_result: str) -> str:
    if deterministic_result in (UNSUPPORTED_MSG, EMPTY_MSG):
        return deterministic_result

    url = f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions?api-version={AZURE_OPENAI_API_VERSION}"
    headers = {"Content-Type": "application/json", "api-key": AZURE_OPENAI_API_KEY}

    system_prompt = """
You rewrite deterministic SQL results into a short natural-language answer.

Rules:
- Use the same language as the user's question.
- Use ONLY the provided SQL result.
- Do NOT add facts, interpretations, or assumptions not present in the rows.
- If the result is tabular, summarize briefly but accurately.
- If there are multiple rows, you may enumerate them.
- If the result is already one of these exact strings, return it unchanged:
  Unsupported or vague question.
  Empty result.
"""

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Question:\n{question}\n\nDeterministic SQL result:\n{deterministic_result}"
            }
        ],
        "temperature": 0.0,
        "max_tokens": 300
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if not r.ok:
            if DEBUG:
                print("formulation failed:", r.status_code, r.text[:300])
            return deterministic_result

        return r.json()["choices"][0]["message"]["content"].strip()

    except Exception as e:
        if DEBUG:
            print("formulation exception:", repr(e))
        return deterministic_result

# -----------------------------------------------------------------------------
# 10) Full HR agent
# -----------------------------------------------------------------------------
def hr_agent_with_trace(question: str, use_ai_formulation: bool = False) -> dict:
    normalized_question = normalize_question(question)

    if DEBUG:
        print("normalized question:", normalized_question)

    route_requested = detect_question_route(normalized_question)
    route_used = route_requested
    evidence = {
        "status": "unsupported",
        "supported": False,
        "normalized_question": normalized_question,
        "route_requested": route_requested,
        "route_used": route_requested,
        "sql": "",
        "semantic_candidate_ids": [],
        "semantic_matches": None,
        "result": None,
        "reason": "",
        "notes": []
    }

    if route_requested == "sql_only" or not FAISS_READY:
        if route_requested != "sql_only" and not FAISS_READY:
            route_used = "sql_only"
            evidence["notes"].append(
                "Semantic review search was unavailable, so the assistant used the SQL-only path."
            )

        evidence["route_used"] = route_used
        intent = parse_question_to_intent(question, normalized_question)
        result, exec_trace = execute_intent_with_trace(conn, intent)

        evidence["supported"] = exec_trace["supported"]
        evidence["status"] = exec_trace["status"]
        evidence["sql"] = exec_trace["sql"]
        evidence["result"] = exec_trace["result"]
        evidence["reason"] = exec_trace["reason"]

    elif route_requested == "review_semantic":
        evidence["route_used"] = "review_semantic"
        matches = semantic_search_reviews(question, top_k=5, score_threshold=0.08)
        evidence["supported"] = True
        evidence["semantic_matches"] = semantic_matches_to_table_payload(matches)

        if matches:
            evidence["status"] = "supported"
        else:
            evidence["status"] = "empty"
            evidence["reason"] = "No relevant performance review matches were found for this question."

        result = format_semantic_matches_deterministically(matches)

    else:  # review_semantic_plus_sql
        evidence["route_used"] = "review_semantic_plus_sql"
        matches = semantic_search_reviews(question, top_k=8, score_threshold=0.06)
        evidence["semantic_matches"] = semantic_matches_to_table_payload(matches)
        candidate_ids = get_semantic_candidate_ids(matches, max_ids=8)
        evidence["semantic_candidate_ids"] = candidate_ids

        if not candidate_ids:
            evidence["supported"] = True
            evidence["status"] = "empty"
            evidence["reason"] = (
                "No relevant performance review matches were found before applying the structured filters."
            )
            result = EMPTY_MSG
        else:
            intent = parse_question_to_intent(question, normalized_question, semantic_candidate_ids=candidate_ids)
            result, exec_trace = execute_intent_with_trace(conn, intent)

            evidence["supported"] = exec_trace["supported"]
            evidence["status"] = exec_trace["status"]
            evidence["sql"] = exec_trace["sql"]
            evidence["result"] = exec_trace["result"]

            if exec_trace["status"] == "empty":
                evidence["reason"] = (
                    "The question is supported, but no rows matched after applying the review candidates and structured filters."
                )
            elif exec_trace["status"] == "unsupported":
                evidence["reason"] = (
                    "The assistant found relevant review candidates, but could not safely translate the full request into a supported SQL query."
                )
            else:
                evidence["reason"] = exec_trace["reason"]

    if not use_ai_formulation:
        answer = result
    else:
        answer = formulate_answer(question, result)

    return {
        "answer": answer,
        "evidence": evidence
    }


def hr_agent(question: str, use_ai_formulation: bool = False) -> str:
    traced = hr_agent_with_trace(question, use_ai_formulation=use_ai_formulation)
    return traced["answer"]

# -----------------------------------------------------------------------------
# 11) Example usage
# -----------------------------------------------------------------------------

