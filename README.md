# Colab HR Agent

A lightweight HR question-answering application that combines SQLite, Azure OpenAI, and FAISS-based semantic search. The project allows users to ask natural-language questions about HR data and receive answers generated from structured data and performance reviews.

The system supports both structured database queries and semantic search over employee performance reviews. It also supports English and German questions through normalization and vocabulary mapping.

---

# Overview

This project loads HR CSV files into an in-memory SQLite database and answers user questions against that data.

Two types of queries are supported:

**Structured queries**

Questions about fields such as:

- departments  
- salaries  
- hire dates  
- reporting structure  
- absences  

These are converted into safe SQL `SELECT` queries.

**Semantic queries**

Questions about employee performance reviews. These are handled through embeddings and FAISS similarity search, which allows matching by meaning instead of exact keywords.

---

# Key Features

- Natural-language HR queries
- English and German question support
- SQLite in-memory database
- Azure OpenAI intent parsing
- FAISS semantic search for performance reviews
- Safe SQL execution (SELECT only)
- Optional natural-language result summaries
- Simple web interface using Flask
- Clean frontend with HTML templates and CSS

---

# Project Structure

```
.
├── static/
│   └── styles.css
├── templates/
│   └── index.html
├── absences.csv
├── agent.py
├── app.py
├── departments.csv
├── employees.csv
├── hr_data_files.json
├── requirements.txt
└── README.md
```

---

# How It Works

## 1. Data Loading

When the application starts, the HR CSV files are loaded into an in-memory SQLite database.

Using an in-memory database keeps the system simple and fast for queries.

---

## 2. Question Normalization

Before processing a question, the system normalizes it to improve reliability.

Normalization includes:

- English and German vocabulary mapping  
- spelling normalization  
- umlaut handling (`ä → ae`, `ö → oe`, `ü → ue`)  
- accent removal  
- date format normalization (`01.02.2024 → 2024-02-01`)  

This helps ensure different phrasing of the same question produces consistent behavior.

---

## 3. Query Routing

The system determines which processing path should handle the question:

**SQL Only**

Used for structured queries involving:

- departments
- salaries
- hire dates
- managers
- absences

**Semantic Review Search**

Used when the question relates to employee performance reviews.

**Hybrid Search**

When the question includes both structured filters and review meaning.

Example:

```
Employees in Engineering with leadership potential
```

This first finds review matches semantically, then filters results using SQL.

---

## 4. SQL Generation

Azure OpenAI converts normalized questions into SQLite `SELECT` statements.

Strict rules ensure:

- Only valid schema fields are used
- Only `SELECT` queries are allowed
- No modification operations are generated

---

## 5. Semantic Review Search

Employee performance reviews are embedded using Azure OpenAI embeddings.

Those vectors are indexed using **FAISS**.

When a semantic query is detected:

1. The question is embedded
2. Similar review vectors are retrieved
3. Matching employees are returned

This allows queries like:

- employees with leadership potential  
- people strong at mentoring  
- employees needing communication improvement  
- strategic thinkers  

Even when wording differs in the reviews.

---

## 6. Deterministic Result Output

Query results are returned in a deterministic table-style format.

Example:

```
employee_id | first_name | last_name | job_title | department_name
12 | Anna | Keller | Software Engineer | Engineering
15 | Markus | Weber | Senior Developer | Engineering
```

---

## 7. Optional Natural Language Response

An optional step can rewrite deterministic results into a short natural-language answer.

This step is strictly constrained:

- It uses only the SQL result
- It cannot add new information
- It keeps the language of the original question

---

# Example Questions

English:

```
Show all employees in Engineering
Who reports to Frank Neumann?
List all sickness absences
How many employees are in each department?
Which employees were hired after 2024-02-01?
Which employees show leadership potential?
```

German:

```
Zeige alle Krankheitsausfälle
Wer berichtet an Frank Neumann?
Welche Mitarbeiter in Engineering wurden nach dem 2024-02-01 eingestellt?
Welche Mitarbeiter zeigen Führungspotenzial?
```

# Azure OpenAI Configuration

The project requires Azure OpenAI for two tasks:

- chat completions (intent parsing and answer formulation)
- embeddings (semantic review search)

Set the following environment variables before running the application:

```
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_DEPLOYMENT
AZURE_OPENAI_API_VERSION
AZURE_OPENAI_API_KEY
AZURE_OPENAI_EMBEDDING_DEPLOYMENT
```

These values should match your Azure OpenAI resource configuration.

---

# Safety Model

The SQL execution layer strictly limits queries.

Only **read-only SELECT queries** are allowed.

The following operations are blocked:

- INSERT  
- UPDATE  
- DELETE  
- DROP  
- ALTER  
- CREATE  
- REPLACE  
- TRUNCATE  
- PRAGMA  
- ATTACH  

If a question is unsupported or unrelated to the HR data, the system returns:

```
Unsupported or vague question.
```

If a valid query produces no matching rows, the response is:

```
Empty result.
```

---

# Why FAISS Is Used

SQL text search only matches exact phrases.

Performance reviews often use varied language, making keyword search unreliable.

FAISS enables semantic similarity search, which improves retrieval for concepts such as:

- leadership potential
- mentoring ability
- communication issues
- strategic thinking
- reliability
- initiative

This makes performance-review queries much more flexible.

---

# Typical Use Cases

- HR analytics demonstrations  
- natural-language-to-SQL prototypes  
- semantic employee evaluation search  
- bilingual HR data exploration  
- internal HR tooling experiments  

---

# Limitations

- The database runs in memory and resets each time the app starts
- Semantic search currently focuses on performance reviews
- Correct Azure OpenAI configuration is required
- The project does not include authentication or access control by default

---

# Main Files

Important files in the repository:

- **app.py** — Flask application entry point  
- **agent.py** — HR agent logic, SQL generation, semantic search  
- **templates/index.html** — user interface  
- **static/styles.css** — frontend styling  

---

# License

Add your preferred license if you plan to publish or distribute the project.
