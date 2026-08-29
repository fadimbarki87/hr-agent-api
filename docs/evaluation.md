# Evaluation record

This file records the acceptance evidence for the 2026-08-29 architecture
change. Live scripts used the configured Azure deployment
`gpt-4.1-mini-2025-04-14` and embeddings deployment
`text-embedding-3-small`. Credentials were loaded only from ignored
`.env.test`; they are not stored in these results.

## Development and regression evidence

- Balanced structured planner corpus before the independent audit:
  **100/100 routes**, with **0 invalid structured queries**.
- Frozen full hybrid pipeline before the independent plan audit:
  **33/33**, including expected semantic employee IDs, final SQL-filtered IDs,
  counts, top-k behavior, and empty results.
- Material regressions derived from v1 holdout findings after the audited
  architecture was introduced: **5/5**.
- Risk-focused hybrid regression through the final audited architecture:
  **5/5**, covering semantic counts, empty evidence, initiative precision,
  current strength versus future potential, and readiness.
- Curated website examples under the current contract: **22/22** end-to-end.
  The contract checks route, language, status, unsupported category, semantic
  scope, row/scalar result, semantic employee IDs, and final SQL-filtered IDs.
  The final capped run used 70 successful calls, 133,472 chat prompt tokens,
  3,830 completion tokens, and 263 embedding tokens, with no exceptions.
- Local final gate: **68 tests passed**, with one API module skipped only in the
  local Python 3.14 interpreter because FastAPI is not installed there. CI uses
  Python 3.11, installs the locked runtime requirements, and executes that
  module. Python compilation, JavaScript syntax, and `git diff --check` passed.

## Current classified boundary-response evaluation

The current planner returns one closed boundary category for an unsupported
request: `vague`, `out_of_scope`, `unavailable_data`, or
`unsupported_operation`. A separate prompt receives the original question, the
audited category, and schema metadata only. Its exact JSON response is locally
validated; it receives no HR rows and cannot execute a route or query.

| Component | Version | SHA-256 |
| --- | --- | --- |
| Planner | `2026-08-29.6` | `2e2d9331e295455075d120ceb7ee89b345cfd9dfea40eddd774f53852f800026` |
| Plan auditor | `2026-08-29.5` | `647d17f1d24de3a3ca44c15b2afed37cc7f788c7aa05dbeab93c8a012bf8fda9` |
| Repair policy | `2026-08-29.3` | `62cc186f5b49954dd1f71923474603f6c824e05f7ebd17a8c98dc934a7538f6e` |
| Boundary guidance | `2026-08-29.2` | `ca3f49348ccaaa9e88438e5fa40d1aaa5fed992b1ff6591f50410e339e0bac1d` |
| Review reranker | `2026-08-29.1` | `54312380f103736f539d596f6310842c0627775d03fed5476d6d15e779a3cc49` |

The final boundary suite scored **8/8** across all four categories and English,
German, Spanish, Arabic, and French. It verified category, language, audited
classification source, grounded-guidance source, absence of SQL/results, and
presence of schema evidence. The final run used 24 successful chat calls,
43,944 prompt tokens, and 751 completion tokens, with no embeddings or
exceptions.

Development evaluation caught two material issues before acceptance. Optional
free-form suggested questions sometimes introduced arbitrary filters, so that
field was removed rather than trusted. The independent auditor also initially
rejected a correct translated reference to the stored `HR` department value;
the schema contract now explicitly defines `HR` as the stored abbreviation for
Human Resources in any language. The focused control then passed in one
planner/auditor cycle, and the complete 22-question final run passed.

## Frozen blind holdout v1

The first untouched planner holdout used 60 questions across English, German,
French, Spanish, and Arabic. It scored **45/60 under exact plan matching**.
Several strict mismatches were behaviorally equivalent projections or date
boundaries. Five material failure classes were retained as evidence:

- two multilingual count requests returned rows instead of a count;
- an unavailable policy request was treated as review evidence;
- a present-time behavior qualifier invented an active-employment filter;
- an unavailable named department was substituted with another department.

The v1 prompt hashes and cases remain unchanged in `tests/prompt_freeze.py` and
`tests/blind_holdout_cases.py`. After v1 was consumed, its material cases became
a regression set; they were not presented as a new blind score.

## Frozen blind holdout v2

The then-current planner, independent plan-audit, and reranker prompts were frozen
before creating v2:

| Component | Version | SHA-256 |
| --- | --- | --- |
| Planner | `2026-08-29.4` | `c51db4353336392f17e1f54310146e492d57cce98cb1491ff9f9777cd5a6ed6f` |
| Plan auditor | `2026-08-29.2` | `fe61830d36b0a48e64819f086f9d27371e7b6720ee2c99f56c8c550012868df4` |
| Repair policy | `2026-08-29.1` | `6ba0e94967040f09be979c04895bbb35f57dd89a7bf739ad49f8045080a9bf0e` |
| Review reranker | `2026-08-29.1` | `54312380f103736f539d596f6310842c0627775d03fed5476d6d15e779a3cc49` |

The fresh v2 holdout contained 30 questions with no exact overlap against v1,
the 100-case route corpus, product UI questions, or production prompts. It
checked route, support status, response language, semantic modality, base table,
selection, filters, grouping, ordering, limit, and trusted query compilation.

Result: **30/30 fully correct**.

- Routes: SQL-only **11/11**, semantic **10/10**, hybrid **9/9**
- Languages: English **6/6**, German **6/6**, French **6/6**, Spanish **6/6**,
  Arabic **6/6**
- Azure usage: 62 attempted calls, 60 successful responses, two transient
  `URLError` retries, 134,781 chat prompt tokens, 3,242 completion tokens

The evaluator refuses to run if a frozen prompt identity changes or if a v2
question duplicates an earlier corpus or production prompt. The v2 result was
not used for further prompt tuning.

## Cost boundary

All live work used hard per-script call ceilings and recorded token usage. Based
on the measured deployment/model usage, the total development evaluation stayed
below the user-approved €2 ceiling. The Azure invoice and regional contract
pricing remain the authoritative billing source.
