from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agent import handle_banking_request
from app.database import list_loan_applications
from app.tools import submit_loan_application_record


class BankingSupportRequest(BaseModel):
    request: str = Field(min_length=3, description="Customer's natural-language banking request")
    customer_id: str = "CUST-1001"
    confirmed: bool = False
    loan_amount: int | None = Field(default=None, gt=0)
    tenure_months: int | None = Field(default=None, gt=0)
    monthly_salary: int | None = Field(default=None, gt=0)
    existing_emi: int | None = Field(default=None, ge=0)


class LoanApplicationSubmission(BaseModel):
    customer_id: str = "CUST-1001"
    loan_amount: int = Field(gt=0)
    tenure_months: int = Field(gt=0)
    monthly_salary: int = Field(gt=0)
    existing_emi: int = Field(ge=0)
    confirmed: bool = False


app = FastAPI(
    title="Smart Banking Support Agent",
    description="Single-agent banking assistant using LangChain tools and FastAPI.",
    version="1.0.0",
)
APP_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")


@app.get("/")
def root() -> FileResponse:
    return FileResponse(APP_DIR / "templates" / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/banking/support")
def banking_support(request: BankingSupportRequest) -> dict:
    return handle_banking_request(
        request_text=request.request,
        customer_id=request.customer_id,
        confirmed=request.confirmed,
        loan_amount=request.loan_amount,
        tenure_months=request.tenure_months,
        monthly_salary=request.monthly_salary,
        existing_emi=request.existing_emi,
    )


@app.post("/banking/applications")
def create_loan_application(request: LoanApplicationSubmission) -> dict:
    if not request.confirmed:
        raise HTTPException(
            status_code=409,
            detail="Customer confirmation is required before submitting a loan application.",
        )

    result = submit_loan_application_record(
        customer_id=request.customer_id,
        principal=request.loan_amount,
        tenure_months=request.tenure_months,
        monthly_salary=request.monthly_salary,
        existing_emi=request.existing_emi,
        confirmed=True,
    )

    if result["status"] == "account_not_found":
        raise HTTPException(status_code=404, detail="Customer account not found in mock data.")
    if result["status"] == "not_eligible":
        raise HTTPException(status_code=409, detail="Customer does not meet the sample eligibility rule.")
    return result


@app.get("/banking/applications")
def list_applications() -> dict[str, list[dict]]:
    return {"applications": list_loan_applications()}
