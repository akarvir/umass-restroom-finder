# In-Memory Restroom Store Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load the static `restrooms` dataset once at backend startup and serve search results from in-memory data instead of querying Supabase on each request.

**Architecture:** Refactor the FastAPI backend into an app factory that owns startup state, move restroom loading and search logic into a focused backend module, and pin the frontend-facing response contract with backend tests. Use the direct Postgres connection string to load rows once because the current environment exposes `SUPABASE_DB_URL`.

**Tech Stack:** FastAPI, psycopg, pytest, Python 3.11

---

## Chunk 1: Lock The Contract

### Task 1: Add backend contract tests

**Files:**
- Create: `tests/test_restroom_store.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

- [ ] **Step 1: Write the failing tests**

Add tests that:
- create the app with preloaded restroom rows
- call `/search-restrooms`
- assert the grouped response shape the frontend expects
- assert the 404 response for no matches

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_restroom_store.py -q`
Expected: FAIL because `backend.main` still initializes external clients at import time and does not support a preloaded in-memory store.

- [ ] **Step 3: Install minimal test/runtime dependencies**

Run:
- `uv add fastapi uvicorn openai pytest`
- `uv add 'psycopg[binary]'`

- [ ] **Step 4: Re-run the targeted test**

Run: `./.venv/bin/python -m pytest tests/test_restroom_store.py -q`
Expected: Still FAIL, but now with an application-structure failure rather than missing modules.

## Chunk 2: Move Search To Memory

### Task 2: Add the in-memory store module

**Files:**
- Create: `backend/restroom_store.py`

- [ ] **Step 1: Add one-time DB loading**

Create a focused module that:
- loads rows from Postgres using `SUPABASE_DB_URL`
- exposes distance and ETA helpers
- builds frontend-ready grouped results from in-memory rows

- [ ] **Step 2: Keep the result contract stable**

Ensure each restroom payload includes:
- identity and location fields
- restroom metadata used by the frontend
- computed `distance_miles`, `eta_minutes`, and `natural_summary`

### Task 3: Refactor the FastAPI app to own startup state

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Replace import-time side effects with an app factory**

Implement `create_app(...)` so tests can inject a preloaded dataset and runtime startup can load rows once.

- [ ] **Step 2: Load the dataset at startup**

Store rows on `app.state.restroom_rows` during lifespan startup.

- [ ] **Step 3: Route handlers read from memory**

Update `/search-restrooms` and `/search-restrooms-ai` to read from `app.state.restroom_rows` instead of querying Supabase inside the request path.

- [ ] **Step 4: Fix grouping**

Group multiple restrooms under the same building/address so the response matches the `LocationGroup` structure the frontend renders.

## Chunk 3: Verify And Commit

### Task 4: Verify the refactor end to end

**Files:**
- Verify: `tests/test_restroom_store.py`

- [ ] **Step 1: Run the targeted tests**

Run: `./.venv/bin/python -m pytest tests/test_restroom_store.py -q`
Expected: PASS

- [ ] **Step 2: Run the full repo Python test suite**

Run: `./.venv/bin/python -m pytest -q`
Expected: PASS

- [ ] **Step 3: Commit the plan and implementation in small steps**

Example:
```bash
git add docs/superpowers/plans/2026-03-15-in-memory-restroom-store.md
git commit -m "docs: add in-memory restroom store plan"

git add pyproject.toml uv.lock backend/main.py backend/restroom_store.py tests/test_restroom_store.py
git commit -m "feat: load restroom search data into memory"
```
