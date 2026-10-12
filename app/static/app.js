const form = document.querySelector("#loan-form");
const calculateButton = document.querySelector("#calculate-button");
const confirmButton = document.querySelector("#confirm-button");
const consentCheck = document.querySelector("#consent-check");
const confirmationBlock = document.querySelector("#confirmation-block");
const resultPanel = document.querySelector("#result-panel");
const resultState = document.querySelector("#result-state");
const responseMessage = document.querySelector("#response-message");
let reviewedApplication = null;

const currency = new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
});

function fieldValue(name) {
    return form.elements.namedItem(name).value;
}

function applicationDetails() {
    return {
        customer_id: fieldValue("customer_id").trim(),
        loan_amount: Number(fieldValue("loan_amount")),
        tenure_months: Number(fieldValue("tenure_months")),
        monthly_salary: Number(fieldValue("monthly_salary")),
        existing_emi: Number(fieldValue("existing_emi")),
    };
}

function requestText(details) {
    return `I want to apply for a personal loan of ${details.loan_amount} for ${details.tenure_months} months. ` +
        `My monthly salary is ${details.monthly_salary}, and I already pay ${details.existing_emi} as an EMI. ` +
        "Calculate my monthly EMI, check my loan eligibility, retrieve my account details, " +
        "and help me submit a loan application if I qualify.";
}

async function postJson(path, body) {
    const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "The request could not be completed.");
    }
    return data;
}

function setBusy(busy) {
    resultPanel.setAttribute("aria-busy", String(busy));
    calculateButton.disabled = busy;
    calculateButton.querySelector("span:first-child").textContent = busy ? "Checking details…" : "Calculate my estimate";
}

function setState(label, kind = "") {
    resultState.dataset.kind = kind;
    resultState.lastChild.textContent = ` ${label.toUpperCase()}`;
}

function resetConfirmation() {
    reviewedApplication = null;
    consentCheck.checked = false;
    confirmButton.disabled = true;
    confirmationBlock.hidden = true;
}

function renderAccount(account) {
    const strip = document.querySelector("#account-strip");
    if (!account?.found) {
        strip.hidden = true;
        return;
    }
    document.querySelector("#account-name").textContent = account.name;
    document.querySelector("#account-meta").textContent = `${account.account_type} · ${account.account_number_masked}`;
    document.querySelector("#account-balance").textContent = currency.format(account.available_balance);
    strip.hidden = false;
}

function renderEstimate(data, details) {
    const emi = data.emi;
    const eligibility = data.eligibility;
    document.querySelector("#monthly-emi").textContent = emi ? currency.format(emi.monthly_emi) : "—";
    document.querySelector("#term-caption").textContent = emi
        ? `${emi.tenure_months} months · ${currency.format(emi.total_repayment)} total repayment`
        : "Enter your details to see an estimate";

    const eligibilityValue = document.querySelector("#eligibility-value");
    eligibilityValue.textContent = eligibility
        ? eligibility.eligible ? "Eligible under sample rule" : "Not eligible under sample rule"
        : data.message || "Eligibility not calculated";
    eligibilityValue.dataset.kind = eligibility ? eligibility.eligible ? "success" : "error" : "";
    document.querySelector("#total-emi-value").textContent = eligibility
        ? currency.format(eligibility.total_monthly_emi)
        : "—";
    document.querySelector("#limit-value").textContent = eligibility
        ? currency.format(eligibility.monthly_emi_limit)
        : "—";

    renderAccount(data.account);
    responseMessage.textContent = data.summary || data.message || "Your estimate is ready.";

    if (data.status === "confirmation_required" && eligibility?.eligible) {
        reviewedApplication = details;
        confirmationBlock.hidden = false;
        setState("Review required", "success");
    } else if (data.status === "not_eligible" || (eligibility && !eligibility.eligible)) {
        setState("Not eligible", "error");
    } else if (data.status === "needs_information") {
        setState("More details needed", "error");
    } else {
        setState("Estimate ready", "success");
    }
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;

    resetConfirmation();
    setBusy(true);
    setState("Calculating");
    responseMessage.textContent = "Checking your estimate and account details…";
    const details = applicationDetails();

    try {
        const result = await postJson("/banking/support", {
            request: requestText(details),
            customer_id: details.customer_id,
            confirmed: false,
            loan_amount: details.loan_amount,
            tenure_months: details.tenure_months,
            monthly_salary: details.monthly_salary,
            existing_emi: details.existing_emi,
        });
        renderEstimate(result, details);
    } catch (error) {
        responseMessage.textContent = error.message;
        setState("Request failed", "error");
    } finally {
        setBusy(false);
    }
});

consentCheck.addEventListener("change", () => {
    confirmButton.disabled = !consentCheck.checked || !reviewedApplication;
});

confirmButton.addEventListener("click", async () => {
    if (!consentCheck.checked || !reviewedApplication) return;

    confirmButton.disabled = true;
    confirmButton.querySelector("span:first-child").textContent = "Submitting…";
    try {
        const application = await postJson("/banking/applications", {
            ...reviewedApplication,
            confirmed: true,
        });
        responseMessage.textContent = `Application ${application.application_id} submitted. Your estimated EMI is ${currency.format(application.monthly_emi)} per month.`;
        confirmationBlock.hidden = true;
        setState("Submitted", "success");
    } catch (error) {
        responseMessage.textContent = error.message;
        confirmButton.disabled = false;
        setState("Submission failed", "error");
    } finally {
        confirmButton.querySelector("span:first-child").textContent = "Confirm and submit";
    }
});