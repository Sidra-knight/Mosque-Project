# Mosque Sites — MVP


This repo contains an MVP allowing non-technical admins to create/manage free one-page mosque sites hosted on GitHub Pages.


## Contents
- `backend/` - FastAPI service (agent manager & worker, GitHub tools, auth)
- `admin/` - Static admin client (Bootstrap + vanilla JS)
- `template/` - Template repo contents to use as a GitHub Template repository


## Quick local run


1. Create a Python virtualenv and install dependencies:


```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy .env.example to .env, fill values (see the list of required env vars below). Make sure DB_PATH points to /data/storage.sqlite3 or a local path for dev.

Run the app locally:

uvicorn main:app --reload --host 0.0.0.0 --port 8000

Serve the Admin static files with any static server (or open admin/index.html in your browser). Edit admin/js/admin.js to set BACKEND_BASE_URL if needed.

## Deploying to Render (summary)

Create a new Web Service for the backend using backend/ with a disk mount to persist /data (for SQLite).

Set environment variables in Render (SECRET_KEY, OPENAI_API_KEY, GITHUB_TOKEN, GITHUB_ORG, GITHUB_TEMPLATE_OWNER, GITHUB_TEMPLATE_REPO, ADMIN_ORIGIN, etc.).

Create a Static Site on Render for admin/. Set BACKEND_BASE_URL inside admin/index.html or use MD5 build-step.

## GitHub Template setup

Create a new repository (e.g., mosque-template) under the owner GITHUB_TEMPLATE_OWNER and push the template/ contents there.

In the repo's Settings > Template repository -> mark as template.

The FastAPI backend uses GitHub's "Create from template" endpoint to generate each mosque repo inside the GITHUB_ORG organization.

## Required environment variables (backend)

SECRET_KEY — a random string used to sign JWTs

ACCESS_TOKEN_EXPIRE_MINUTES — integer

OPENAI_API_KEY — API key for OpenAI

MANAGER_MODEL — e.g., gpt-4o (used for manager planning)

WORKER_MODEL — e.g., gpt-4o-mini (unused in simplified worker, but present)

GITHUB_TOKEN — token with repo scope

GITHUB_ORG — where new mosque repos will be created

GITHUB_TEMPLATE_OWNER — owner of the template repo

GITHUB_TEMPLATE_REPO — template repo name

DEFAULT_BRANCH — typically main

ADMIN_ORIGIN — the Admin frontend origin (CORS)

DB_PATH — /data/storage.sqlite3 (on Render, mount /data persistent disk)

## How it works (short)

Admin -> types an instruction (one instruction only).

Backend Manager agent converts natural language into a single JSON action (from the allowed list).

Backend Worker maps that action to exactly one tool that performs Git operations (one commit per logical change).

Acceptances covered:

Register/login

Create site from the template (config + content files + optional images)

Add announcement, set jumuah, toggle/set Eid, upload image, edit homepage copy — each via one Manager->Worker call and resulting in one commit.

## Notes & limitations

Prayer times are fetched client-side from Aladhan using lat/lon in config.json.

The Manager is intentionally conservative — if the instruction is compound, it will pick the first atomic step only.
