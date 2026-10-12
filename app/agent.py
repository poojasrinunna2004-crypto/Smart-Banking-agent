from __future__ import annotations

import re
import json
import os
from typing import Any, NotRequired, TypedDict

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph

from app.tools import (
    calculate_loan_emi,
    check_loan_eligibility,
    get_account_details,
    get_account_details_record,
    parse_banking_request,
    submit_loan_application,
    submit_loan_application_record,
)

load_dotenv()

AGENT_SYSTEM_PROMPT = """You are a single banking support assistant using the available tools.
Use the customer request to decide which tools are needed, and use tool results to
decide what to do next. For a loan request, ask for the loan amount, tenure, monthly
salary, and existing EMI if any are missing; do not invent values. Calculate the EMI
before checking eligibility. Retrieve account details only when requested. Explain
that eligibility uses a mock rule: total monthly EMIs must be at most 40% of salary.
The sample EMI rate is 12% annually, not a bank quote.

Never claim an application was submitted unless the submission tool returns submitted.
The server supplies customer identity and confirmation as hidden state. An initial
request to apply is not confirmation; if confirmation state is false, explain the
calculated terms and ask the customer to explicitly confirm before submission. Keep
the final response concise and summarize the EMI, eligibility, account lookup, and
application status relevant to the request."""


class BankingState(TypedDict, total=False):
    request_text: str
    customer_id: str
    confirmed: bool
    loan_amount: int | None
    tenure_months: int | None
    monthly_salary: int | None
    existing_emi: int | None
    response: dict[str, Any]


class BankingAgentState(MessagesState, total=False):
    customer_id: str
    confirmed: bool


def banking_agent_node(state: BankingState) -> dict[str, Any]:
    request_text = state.get("request_text", "")
    parsed = parse_banking_request(request_text)

    for key in parsed:
        if state.get(key) is not None:
            parsed[key] = state[key]

    response: dict[str, Any] = {"status": "complete", "tools_used": []}
    required = ["loan_amount", "tenure_months", "monthly_salary", "existing_emi"]
    missing = [key for key in required if parsed[key] is None]

    if missing:
        response.update({
            "status": "needs_information",
            "missing_fields": missing,
            "message": "Please provide the loan amount, tenure, monthly salary, and existing EMI.",
        })
        return {"response": response}

    asks_emi = bool(re.search(r"\b(?:emi|monthly payment|installment)\b", request_text, re.IGNORECASE))
    asks_eligibility = bool(re.search(r"\b(?:eligib|qualif)\w*", request_text, re.IGNORECASE))
    asks_account = bool(re.search(r"\baccount\b", request_text, re.IGNORECASE))
    asks_application = bool(re.search(r"\b(?:apply|application|submit)\w*", request_text, re.IGNORECASE))
    customer_id = state.get("customer_id", "CUST-1001")

    emi_result = calculate_loan_emi.invoke({
        "principal": parsed["loan_amount"],
        "tenure_months": parsed["tenure_months"],
    })
    response["emi"] = emi_result
    response["tools_used"].append("calculate_loan_emi")

    eligibility = check_loan_eligibility.invoke({
        "monthly_salary": parsed["monthly_salary"],
        "existing_emi": parsed["existing_emi"],
        "proposed_emi": emi_result["monthly_emi"],
    })
    response["eligibility"] = eligibility
    response["tools_used"].append("check_loan_eligibility")

    if asks_account:
        response["account"] = get_account_details_record(customer_id)
        response["tools_used"].append("get_account_details")

    if asks_application and eligibility["eligible"]:
        if not state.get("confirmed", False):
            response.update({
                "status": "confirmation_required",
                "message": "You qualify under the sample rule. Confirm explicitly to submit this application.",
            })
        else:
            response["application"] = submit_loan_application_record(
                customer_id=customer_id,
                principal=parsed["loan_amount"],
                tenure_months=parsed["tenure_months"],
                monthly_salary=parsed["monthly_salary"],
                existing_emi=parsed["existing_emi"],
                confirmed=True,
            )
            response["status"] = response["application"]["status"]
            response["tools_used"].append("submit_loan_application")
    elif asks_application:
        response.update({
            "status": "not_eligible",
            "message": "The application was not submitted because the sample eligibility check failed.",
        })

    if not asks_emi:
        response.pop("emi", None)
    if not asks_eligibility:
        response.pop("eligibility", None)

    summary: list[str] = []
    if asks_emi:
        summary.append(f"Estimated monthly EMI: INR {emi_result['monthly_emi']:,.2f}.")
    if asks_eligibility:
        eligibility_text = "eligible" if eligibility["eligible"] else "not eligible"
        summary.append(
            f"Loan eligibility: {eligibility_text} under the sample rule "
            f"(total monthly EMIs INR {eligibility['total_monthly_emi']:,.2f} of "
            f"INR {eligibility['monthly_emi_limit']:,.2f} allowed)."
        )
    if asks_account:
        account = response.get("account", {"found": False})
        summary.append(
            f"Account details retrieved for {account['name']} ({account['account_number_masked']})."
            if account.get("found") else "No mock account was found for that customer ID."
        )
    if asks_application:
        if response["status"] == "confirmation_required":
            application_status = "not submitted; customer confirmation is required"
        elif response["status"] == "not_eligible":
            application_status = "not submitted because eligibility criteria were not met"
        else:
            application_status = response.get("application", {}).get("status", "not submitted")
        summary.append(f"Application status: {application_status}.")

    response["summary"] = " ".join(summary)
    return {"response": response}


def build_banking_agent():
    graph = StateGraph(BankingState)
    graph.add_node("banking_agent", banking_agent_node)
    graph.add_edge(START, "banking_agent")
    graph.add_edge("banking_agent", END)
    return graph.compile()


def build_tool_calling_agent(model: Any):
    return create_agent(
        model=model,
        tools=[
            calculate_loan_emi,
            check_loan_eligibility,
            get_account_details,
            submit_loan_application,
        ],
        system_prompt=AGENT_SYSTEM_PROMPT,
        state_schema=BankingAgentState,
    )


def _configured_tool_calling_agent():
    if not os.getenv("OPENAI_API_KEY"):
        return None
    return build_tool_calling_agent(ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
    ))


banking_agent = build_banking_agent()
tool_calling_agent = _configured_tool_calling_agent()


def _parse_tool_result(content: Any) -> Any:
    if not isinstance(content, str):
        return content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return content


def _handle_with_tool_calling_agent(
    request_text: str,
    customer_id: str,
    confirmed: bool,
    supplied_values: dict[str, int | None],
) -> dict[str, Any]:
    prompt = request_text
    provided = {key: value for key, value in supplied_values.items() if value is not None}
    if provided:
        prompt += f"\nValidated values supplied with this request: {provided}"

    result = tool_calling_agent.invoke({
        "messages": [("user", prompt)],
        "customer_id": customer_id,
        "confirmed": confirmed,
    })
    messages = result["messages"]
    tool_results: dict[str, Any] = {}
    tools_used: list[str] = []
    for message in messages:
        if isinstance(message, ToolMessage) and message.name:
            tool_results[message.name] = _parse_tool_result(message.content)
            tools_used.append(message.name)

    final_message = messages[-1].content if messages else ""
    if not isinstance(final_message, str):
        final_message = json.dumps(final_message, ensure_ascii=False)
    response: dict[str, Any] = {
        "status": "complete",
        "tools_used": tools_used,
        "summary": final_message,
    }
    response_keys = {
        "calculate_loan_emi": "emi",
        "check_loan_eligibility": "eligibility",
        "get_account_details": "account",
        "submit_loan_application": "application",
    }
    for tool_name, response_key in response_keys.items():
        if tool_name in tool_results:
            response[response_key] = tool_results[tool_name]

    eligibility = response.get("eligibility", {})
    application = response.get("application", {})
    if application.get("status"):
        response["status"] = application["status"]
    elif re.search(r"\b(?:apply|application|submit)\w*", request_text, re.IGNORECASE):
        if eligibility.get("eligible") and not confirmed:
            response["status"] = "confirmation_required"
        elif eligibility and not eligibility.get("eligible"):
            response["status"] = "not_eligible"

    parsed = parse_banking_request(request_text)
    for key, value in supplied_values.items():
        if value is not None:
            parsed[key] = value
    asks_for_loan = bool(re.search(r"\b(?:loan|emi|eligib|qualif|apply|application)\w*", request_text, re.IGNORECASE))
    missing = [key for key, value in parsed.items() if value is None]
    if asks_for_loan and missing and not tools_used:
        response["status"] = "needs_information"
        response["missing_fields"] = missing

    return response


def handle_banking_request(
    request_text: str,
    customer_id: str = "CUST-1001",
    confirmed: bool = False,
    loan_amount: int | None = None,
    tenure_months: int | None = None,
    monthly_salary: int | None = None,
    existing_emi: int | None = None,
) -> dict[str, Any]:
    if tool_calling_agent is not None:
        return _handle_with_tool_calling_agent(
            request_text=request_text,
            customer_id=customer_id,
            confirmed=confirmed,
            supplied_values={
                "loan_amount": loan_amount,
                "tenure_months": tenure_months,
                "monthly_salary": monthly_salary,
                "existing_emi": existing_emi,
            },
        )

    result = banking_agent.invoke({
        "request_text": request_text,
        "customer_id": customer_id,
        "confirmed": confirmed,
        "loan_amount": loan_amount,
        "tenure_months": tenure_months,
        "monthly_salary": monthly_salary,
        "existing_emi": existing_emi,
    })
    return result["response"]
