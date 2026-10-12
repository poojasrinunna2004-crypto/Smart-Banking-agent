from __future__ import annotations

import re
from typing import Annotated, Any

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from app.db import LOAN_APPLICATIONS, SAMPLE_ACCOUNTS, get_account_record, save_application


def calculate_emi_amount(principal: int, annual_interest_rate: float, tenure_months: int) -> float:
    if principal <= 0 or annual_interest_rate < 0 or tenure_months <= 0:
        raise ValueError("Principal and tenure must be positive; interest rate cannot be negative.")
    monthly_rate = annual_interest_rate / 12 / 100
    if monthly_rate == 0:
        return round(principal / tenure_months, 2)
    factor = (1 + monthly_rate) ** tenure_months
    return round(principal * monthly_rate * factor / (factor - 1), 2)


@tool
def calculate_loan_emi(
    principal: int,
    tenure_months: int,
    annual_interest_rate: float = 12.0,
) -> dict[str, Any]:
    """Calculate a personal-loan EMI using the representative annual interest rate of 12%."""
    emi = calculate_emi_amount(principal, annual_interest_rate, tenure_months)
    return {
        "principal": principal,
        "tenure_months": tenure_months,
        "annual_interest_rate": annual_interest_rate,
        "monthly_emi": emi,
        "total_repayment": round(emi * tenure_months, 2),
        "currency": "INR",
    }


@tool
def check_loan_eligibility(monthly_salary: int, existing_emi: int, proposed_emi: float) -> dict[str, Any]:
    """Check sample eligibility with a 40% salary cap for total monthly EMIs."""
    if monthly_salary <= 0 or existing_emi < 0 or proposed_emi < 0:
        raise ValueError("Salary must be positive and EMI values cannot be negative.")
    monthly_emi_limit = round(monthly_salary * 0.40, 2)
    total_monthly_emi = round(existing_emi + proposed_emi, 2)
    return {
        "eligible": total_monthly_emi <= monthly_emi_limit,
        "monthly_salary": monthly_salary,
        "existing_emi": existing_emi,
        "proposed_emi": proposed_emi,
        "total_monthly_emi": total_monthly_emi,
        "monthly_emi_limit": monthly_emi_limit,
        "rule": "Existing and proposed EMIs must not exceed 40% of monthly salary.",
    }


@tool
def get_account_details(customer_id: Annotated[str, InjectedState("customer_id")]) -> dict[str, Any]:
    """Retrieve masked account information from the mock customer account store."""
    return get_account_details_record(customer_id)


def get_account_details_record(customer_id: str) -> dict[str, Any]:
    account = get_account_record(customer_id) or SAMPLE_ACCOUNTS.get(customer_id)
    if account is None:
        return {"found": False, "customer_id": customer_id}
    return {"found": True, **account}


@tool
def submit_loan_application(
    customer_id: Annotated[str, InjectedState("customer_id")],
    principal: int,
    tenure_months: int,
    monthly_salary: int,
    existing_emi: int,
    confirmed: Annotated[bool, InjectedState("confirmed")],
    annual_interest_rate: float = 12.0,
) -> dict[str, Any]:
    """Submit an eligible sample loan only after explicit customer confirmation."""
    return submit_loan_application_record(
        customer_id=customer_id,
        principal=principal,
        tenure_months=tenure_months,
        monthly_salary=monthly_salary,
        existing_emi=existing_emi,
        confirmed=confirmed,
        annual_interest_rate=annual_interest_rate,
    )


def submit_loan_application_record(
    customer_id: str,
    principal: int,
    tenure_months: int,
    monthly_salary: int,
    existing_emi: int,
    confirmed: bool,
    annual_interest_rate: float = 12.0,
) -> dict[str, Any]:
    if not confirmed:
        return {"status": "confirmation_required", "submitted": False}

    account = SAMPLE_ACCOUNTS.get(customer_id)
    if account is None:
        return {"status": "account_not_found", "submitted": False}

    emi = calculate_emi_amount(principal, annual_interest_rate, tenure_months)
    eligibility = check_loan_eligibility.invoke({
        "monthly_salary": monthly_salary,
        "existing_emi": existing_emi,
        "proposed_emi": emi,
    })
    if not eligibility["eligible"]:
        return {"status": "not_eligible", "submitted": False}

    application_id = f"LN-{len(LOAN_APPLICATIONS) + 1:05d}"
    application = {
        "application_id": application_id,
        "customer_id": customer_id,
        "principal": principal,
        "tenure_months": tenure_months,
        "monthly_emi": emi,
        "status": "submitted",
        "currency": "INR",
    }
    saved = save_application(application)
    LOAN_APPLICATIONS[application["application_id"]] = saved
    return saved


def parse_banking_request(text: str) -> dict[str, int | None]:
    def amount(pattern: str) -> int | None:
        match = re.search(pattern, text, re.IGNORECASE)
        return int(match.group(1).replace(",", "")) if match else None

    loan_amount = amount(r"loan(?:\s+of)?\s*(?:₹|rs\.?\s*|inr\s*)?([\d,]+)")
    salary = amount(r"(?:monthly\s+salary|salary)\s*(?:is|of)?\s*(?:₹|rs\.?\s*|inr\s*)?([\d,]+)")
    existing_emi = amount(
        r"(?:already\s+pay|existing\s+emi\s*(?:of)?|current\s+emi\s*(?:of)?)\s*"
        r"(?:₹|rs\.?\s*|inr\s*)?([\d,]+)"
    )
    tenure_match = re.search(
        r"for\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(years?|yrs?|months?)",
        text,
        re.IGNORECASE,
    )
    tenure_months = None
    if tenure_match:
        count_text = tenure_match.group(1).lower()
        count = int(count_text) if count_text.isdigit() else {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        }[count_text]
        tenure_months = count * 12 if tenure_match.group(2).lower().startswith(("year", "yr")) else count
    return {
        "loan_amount": loan_amount,
        "tenure_months": tenure_months,
        "monthly_salary": salary,
        "existing_emi": existing_emi,
    }
