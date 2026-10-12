# Smart Banking Support Agent

A single-agent banking support demo built with Python, LangChain, LangGraph, FastAPI, and SQLite. The app includes a responsive loan-planning interface and mock banking tools.

## Features

- EMI calculation and sample eligibility check
- Mock customer account lookup
- Loan application submission protected by explicit confirmation
- Responsive browser interface and JSON API
- SQLite storage for sample accounts and applications
- LLM-based tool selection when `OPENAI_API_KEY` is configured; offline deterministic mode otherwise

The demo uses a representative 12% annual interest rate and a 40% salary-to-EMI limit. These are sample assumptions, not real bank terms or a credit decision.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Set OPENAI_API_KEY in .env only if you want model-driven tool selection.
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/` for the interface or `http://127.0.0.1:8000/docs` for the API.

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Deploy to Render

The repository includes a root-level `render.yaml` Blueprint. In Render, choose **New + → Blueprint**, connect `poojasrinunna2004-crypto/Smart-Banking-agent`, and deploy the `main` branch. Keep the root directory blank so Render can find `requirements.txt` and `render.yaml`.

The Blueprint sets the Python version, installs `requirements.txt`, starts Uvicorn on Render's assigned `$PORT`, and checks `/health`. Add `OPENAI_API_KEY` in the Render service's Environment settings only if you want LLM-based tool selection; do not put the key in GitHub or `render.yaml`.

After deployment, open the service URL for the interface, `/docs` for API testing, or `/health` to check service status.

## Deploy to Railway

The root `Procfile` also provides the Uvicorn start command for Railway. Connect the GitHub repository and deploy its `main` branch.

SQLite files are stored on the service's local filesystem. Platform redeploys may not preserve them; use persistent storage or a managed database before relying on application records.

## Project structure

```text
smart-banking-agent/
├── app/
│   ├── agent.py
│   ├── database.py
│   ├── db.py
│   ├── main.py
│   ├── models.py
│   ├── static/
│   │   ├── app.js
│   │   └── styles.css
│   └── templates/
│       └── index.html
├── tests/
│   └── test_agent.py
├── .env.example
├── Procfile
├── render.yaml
└── requirements.txt
```
