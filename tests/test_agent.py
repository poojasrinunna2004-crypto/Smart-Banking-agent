import unittest

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage

from app.agent import build_tool_calling_agent, handle_banking_request
from app.database import clear_loan_applications, list_loan_applications
from app.db import LOAN_APPLICATIONS
from app.main import app


SAMPLE_REQUEST = (
    "I want to apply for a personal loan of ₹5,00,000 for three years. "
    "My monthly salary is 60,000, and I already pay 5,000 as an EMI for another loan. "
    "Calculate my monthly EMI, check my loan eligibility, retrieve my account details, "
    "and help me submit a loan application if I qualify."
)


class BindableFakeMessagesListChatModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


class SmartBankingAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_loan_applications()
        LOAN_APPLICATIONS.clear()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()

    def test_handle_banking_request_requires_confirmation(self) -> None:
        result = handle_banking_request(SAMPLE_REQUEST)

        self.assertEqual(result["status"], "confirmation_required")
        self.assertEqual(result["emi"]["monthly_emi"], 16607.15)
        self.assertTrue(result["eligibility"]["eligible"])
        self.assertTrue(result["account"]["found"])
        self.assertFalse(LOAN_APPLICATIONS)

    def test_handle_banking_request_submits_eligible_application_after_confirmed(self) -> None:
        result = handle_banking_request(SAMPLE_REQUEST, confirmed=True)

        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["application"]["status"], "submitted")
        self.assertEqual(len(LOAN_APPLICATIONS), 1)

    def test_missing_financial_information_is_requested(self) -> None:
        result = handle_banking_request("Calculate my EMI and check my eligibility for a loan.")

        self.assertEqual(result["status"], "needs_information")
        self.assertIn("loan_amount", result["missing_fields"])

    def test_model_cannot_self_confirm_loan_submission(self) -> None:
        model = BindableFakeMessagesListChatModel(responses=[
            AIMessage(content="", tool_calls=[{
                "name": "submit_loan_application",
                "args": {
                    "principal": 500000,
                    "tenure_months": 36,
                    "monthly_salary": 60000,
                    "existing_emi": 5000,
                    "confirmed": True,
                    "customer_id": "CUST-1001",
                },
                "id": "submit-with-forged-confirmation",
            }]),
            AIMessage(content="The application requires customer confirmation."),
        ])
        agent = build_tool_calling_agent(model)

        result = agent.invoke({
            "messages": [("user", "Submit my eligible personal loan application.")],
            "customer_id": "CUST-1001",
            "confirmed": False,
        })

        submission_result = next(
            message.content
            for message in result["messages"]
            if isinstance(message, ToolMessage) and message.name == "submit_loan_application"
        )
        self.assertIn("confirmation_required", submission_result)
        self.assertFalse(LOAN_APPLICATIONS)

    def test_api_requires_confirmation_before_submission(self) -> None:
        response = self.client.post(
            "/banking/applications",
            json={
                "loan_amount": 500000,
                "tenure_months": 36,
                "monthly_salary": 60000,
                "existing_emi": 5000,
                "confirmed": False,
            },
        )

        self.assertEqual(response.status_code, 409)

    def test_application_is_persisted_in_sqlite(self) -> None:
        response = self.client.post(
            "/banking/applications",
            json={
                "loan_amount": 500000,
                "tenure_months": 36,
                "monthly_salary": 60000,
                "existing_emi": 5000,
                "confirmed": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(item["customer_id"] == "CUST-1001" for item in list_loan_applications()))


if __name__ == "__main__":
    unittest.main()
