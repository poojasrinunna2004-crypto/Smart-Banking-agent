# Smart Banking Support Agent

A Python project demonstrating a single tool-calling banking assistant with a responsive loan-planning interface, built with LangChain, LangGraph, FastAPI, and SQLite.

## Scenario

A customer requests a personal loan application. The agent must:


## Features

- Responsive loan planning screen with estimate, eligibility, account details, and explicit submission confirmation
- FastAPI endpoints for support and submission
- Mock customer account data
- Loan applications persisted in SQLite
- Example request matching the banking scenario
- http://127.0.0.1:8000/ for the loan planning interface
## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Set OPENAI_API_KEY in .env to enable model-driven tool selection.
uvicorn app.main:app --reload
```

Without an API key, the app uses the deterministic workflow so the mock API and tests can run offline. The sample uses a 12% annual EMI rate and a 40% salary cap; these are demonstration assumptions, not bank terms.

Then open:

- http://127.0.0.1:8000/
- http://127.0.0.1:8000/docs

## Example API call

│   ├── static/
│   │   ├── app.js
│   │   └── styles.css
│   ├── templates/
│   │   └── index.html
```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/banking/support `
  -ContentType 'application/json' `
  -Body '{"request":"I want to apply for a personal loan of ₹5,00,000 for three years. My monthly salary is 60,000, and I already pay 5,000 as an EMI. Calculate my EMI, check my eligibility, retrieve my account details, and help me submit the application if I qualify."}'
```

## Example confirmation call

First review the support response and obtain the customer's explicit confirmation. Only then make this second call:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/banking/applications `
  -ContentType 'application/json' `
  -Body '{"loan_amount":500000,"tenure_months":36,"monthly_salary":60000,"existing_emi":5000,"confirmed":true}'
```

The agent's submission tool receives confirmation and customer identity from server-side graph state, not from model-generated tool arguments. The applications endpoint also rejects requests where `confirmed` is false.

## Run tests

```powershell
python -m unittest discover -s tests -v
```

## Deploy to Railway

1. Push this repository to GitHub and create a Railway project from that repository.
2. Add `OPENAI_API_KEY` as a Railway service variable to enable model-driven tool selection. It can be omitted to use the offline deterministic workflow.
3. Deploy the service. Railway uses the root `Procfile` to bind Uvicorn to its assigned port.
4. Open the generated Railway domain and append `/docs` to try the API.

The SQLite database is local to the service by default. Railway's local filesystem is not durable across redeploys; attach a persistent volume and configure the database path before relying on stored applications beyond this demonstration.

## Project structure

```text
smart-banking-agent/
├── app/
│   ├── __init__.py
│   ├── agent.py
│   ├── db.py
│   ├── main.py
│   └── tools.py
├── tests/
│   └── test_agent.py
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
└── .venv/
```
