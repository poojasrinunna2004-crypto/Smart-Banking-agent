from __future__ import annotations

from typing import Any

from app.database import (
    clear_loan_applications,
    get_customer_by_id,
    initialize_database,
    list_loan_applications,
    save_loan_application,
)

initialize_database()

SAMPLE_ACCOUNTS: dict[str, dict[str, Any]] = {
    "CUST-1001": {
        "customer_id": "CUST-1001",
        "name": "Aarav Sharma",
        "account_number_masked": "XXXXXX4821",
        "account_type": "Savings",
        "available_balance": 125000,
        "currency": "INR",
    }
}

LOAN_APPLICATIONS: dict[str, dict[str, Any]] = {item["application_id"]: item for item in list_loan_applications()}


def sync_loan_applications() -> None:
    global LOAN_APPLICATIONS
    LOAN_APPLICATIONS = {item["application_id"]: item for item in list_loan_applications()}


def save_application(application: dict[str, Any]) -> dict[str, Any]:
    saved = save_loan_application(application)
    sync_loan_applications()
    return saved


def clear_applications() -> None:
    clear_loan_applications()
    LOAN_APPLICATIONS.clear()


def get_account_record(customer_id: str) -> dict[str, Any] | None:
    result = get_customer_by_id(customer_id)
    return result
