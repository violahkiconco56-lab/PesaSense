const token = localStorage.getItem("access_token");

const budgetForm = document.getElementById("budgetForm");
const budgetMessage = document.getElementById("budgetMessage");
const budgetSummary = document.getElementById("budgetSummary");
const budgetAlerts = document.getElementById("budgetAlerts");


function formatUGX(amount) {
    return `UGX ${Number(amount).toLocaleString()}`;
}


async function loadBudgetPerformance() {

    if (!token) {
        window.location.href = "../index.html";
        return;
    }

    try {
        const response = await fetch(
            "http://127.0.0.1:8000/budgets/performance",
            {
                method: "GET",
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Failed to load budget performance"
            );
        }

        budgetSummary.innerHTML = `
            <p><strong>Total Budgeted:</strong> ${formatUGX(data.total_budgeted)}</p>
            <p><strong>Total Spent:</strong> ${formatUGX(data.total_spent)}</p>
            <p><strong>Total Remaining:</strong> ${formatUGX(data.total_remaining)}</p>
        `;

        if (data.budgets.length > 0) {

            data.budgets.forEach(budget => {

                const budgetElement = document.createElement("div");

                budgetElement.innerHTML = `
                    <hr>
                    <h3>${budget.category}</h3>
                    <p>Limit: ${formatUGX(budget.limit_amount)}</p>
                    <p>Spent: ${formatUGX(budget.spent)}</p>
                    <p>Remaining: ${formatUGX(budget.remaining)}</p>
                    <p>Used: ${budget.used_percentage}%</p>
                    <p>
                        Status:
                        ${
                            budget.over_budget
                                ? "Over budget"
                                : budget.approaching_limit
                                    ? "Approaching limit"
                                    : "Within budget"
                        }
                    </p>
                `;

                budgetSummary.appendChild(budgetElement);
            });
        }

    } catch (error) {

        console.error(error);

        budgetSummary.innerHTML =
            "<p>Unable to load budget information.</p>";
    }
}


async function loadBudgetAlerts() {

    if (!token) {
        return;
    }

    try {

        const response = await fetch(
            "http://127.0.0.1:8000/budgets/alerts",
            {
                method: "GET",
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Failed to load budget alerts"
            );
        }

        budgetAlerts.innerHTML = "";

        if (data.alerts.length === 0) {
            budgetAlerts.innerHTML =
                "<p>No budget alerts.</p>";
            return;
        }

        data.alerts.forEach(alert => {

            const alertElement = document.createElement("p");

            alertElement.textContent = alert.message;

            budgetAlerts.appendChild(alertElement);
        });

    } catch (error) {

        console.error(error);

        budgetAlerts.innerHTML =
            "<p>Unable to load budget alerts.</p>";
    }
}


budgetForm.addEventListener("submit", async function (event) {

    event.preventDefault();

    const budget = {
        category: document.getElementById("category").value,
        limit_amount: Number(
            document.getElementById("limitAmount").value
        ),
        month: Number(
            document.getElementById("month").value
        ),
        year: Number(
            document.getElementById("year").value
        )
    };

    try {

        const response = await fetch(
            "http://127.0.0.1:8000/budgets/",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },

                body: JSON.stringify(budget)
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Failed to create budget"
            );
        }

        budgetMessage.textContent =
            "Budget created successfully!";

        budgetForm.reset();

        await loadBudgetPerformance();
        await loadBudgetAlerts();

    } catch (error) {

        console.error(error);

        budgetMessage.textContent = error.message;
    }
});


loadBudgetPerformance();
loadBudgetAlerts();