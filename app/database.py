from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DB_DIR / "banking.db"


def _connect() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                account_number_masked TEXT NOT NULL,
                account_type TEXT NOT NULL,
                available_balance REAL NOT NULL,
                currency TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS loan_applications (
                application_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                principal INTEGER NOT NULL,
                tenure_months INTEGER NOT NULL,
                monthly_emi REAL NOT NULL,
                status TEXT NOT NULL,
                currency TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO customers (
                customer_id, name, account_number_masked, account_type, available_balance, currency
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "CUST-1001",
                "Aarav Sharma",
                "XXXXXX4821",
                "Savings",
                125000,
                "INR",
            ),
        )


def get_customer_by_id(customer_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def list_loan_applications() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM loan_applications ORDER BY application_id"
        ).fetchall()
    return [dict(row) for row in rows]


def save_loan_application(application: dict[str, Any]) -> dict[str, Any]:
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO loan_applications (
                application_id, customer_id, principal, tenure_months, monthly_emi, status, currency
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                application["application_id"],
                application["customer_id"],
                application["principal"],
                application["tenure_months"],
                application["monthly_emi"],
                application["status"],
                application["currency"],
            ),
        )
    return application


def clear_loan_applications() -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM loan_applications")


initialize_database()
