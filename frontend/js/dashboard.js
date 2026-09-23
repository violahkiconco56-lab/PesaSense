const token = localStorage.getItem("access_token");

const totalIncome = document.getElementById("totalIncome");
const totalExpenses = document.getElementById("totalExpenses");
const balance = document.getElementById("balance");
const highestCategory = document.getElementById("highestCategory");
const recentTransactions = document.getElementById("recentTransactions");

async function loadDashboard() {

    if (!token) {
        window.location.href = "../index.html";
        return;
    }

    try {
        const response = await fetch(
            "http://127.0.0.1:8000/transactions/dashboard/summary",
            {
                method: "GET",
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to load dashboard");
        }

        totalIncome.textContent = `UGX ${data.total_income.toLocaleString()}`;
        totalExpenses.textContent = `UGX ${data.total_expenses.toLocaleString()}`;
        balance.textContent = `UGX ${data.balance.toLocaleString()}`;
        highestCategory.textContent = data.highest_expense_category || "None";

        recentTransactions.innerHTML = "";

        data.recent_transactions.forEach(transaction => {

            const transactionElement = document.createElement("p");

            transactionElement.textContent =
                `${transaction.description} - UGX ${transaction.amount.toLocaleString()}`;

            recentTransactions.appendChild(transactionElement);
        });

    } catch (error) {

        console.error(error);

        recentTransactions.innerHTML =
            "<p>Unable to load dashboard data.</p>";
    }
}

loadDashboard();