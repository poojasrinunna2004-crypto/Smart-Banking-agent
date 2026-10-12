from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Customer:
    customer_id: str
    name: str
    account_number_masked: str
    account_type: str
    available_balance: float
    currency: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LoanApplication:
    application_id: str
    customer_id: str
    principal: int
    tenure_months: int
    monthly_emi: float
    status: str = "submitted"
    currency: str = "INR"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
