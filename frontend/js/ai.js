const API_BASE_URL = "http://127.0.0.1:8000";

const aiSummary = document.getElementById("aiSummary");
const totalIncome = document.getElementById("totalIncome");
const totalExpenses = document.getElementById("totalExpenses");
const balance = document.getElementById("balance");
const categoryBreakdown = document.getElementById("categoryBreakdown");
const recommendations = document.getElementById("recommendations");
const errorMessage = document.getElementById("errorMessage");
const logoutBtn = document.getElementById("logoutBtn");


function formatCurrency(amount) {
    const numericValue = Number(amount ?? 0);
    return `UGX ${Number.isFinite(numericValue) ? numericValue.toLocaleString() : 0}`;
}


function getAuthToken() {
    return localStorage.getItem("access_token");
}


async function loadAIInsights() {
    if (!aiSummary || !totalIncome || !totalExpenses || !balance || !categoryBreakdown || !recommendations) {
        return;
    }

    try {
        const token = getAuthToken();

        if (!token) {
            window.location.href = "../index.html";
            return;
        }

        const response = await fetch(
            `${API_BASE_URL}/transactions/insights/summary`,
            {
                method: "GET",
                headers: {
                    "Authorization": `Bearer ${token}`,
                    "Content-Type": "application/json"
                }
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to load AI insights.");
        }

        let dashboardData = null;

        if (
            data &&
            (data.total_income === undefined ||
                data.total_expenses === undefined ||
                data.balance === undefined)
        ) {
            const dashboardResponse = await fetch(
                `${API_BASE_URL}/transactions/dashboard/summary`,
                {
                    method: "GET",
                    headers: {
                        "Authorization": `Bearer ${token}`,
                        "Content-Type": "application/json"
                    }
                }
            );

            if (dashboardResponse.ok) {
                dashboardData = await dashboardResponse.json();
            }
        }

        displayInsights({
            ...dashboardData,
            ...data,
            total_income: data?.total_income ?? dashboardData?.total_income ?? 0,
            total_expenses: data?.total_expenses ?? dashboardData?.total_expenses ?? 0,
            balance: data?.balance ?? dashboardData?.balance ?? 0,
            category_breakdown: data?.category_breakdown ?? dashboardData?.category_breakdown ?? {},
        });

    } catch (error) {
        console.error("AI Insights Error:", error);

        if (errorMessage) {
            errorMessage.style.display = "block";
            errorMessage.textContent =
                error.message || "Unable to load your AI insights. Please try again.";
        }

        if (aiSummary) {
            aiSummary.innerHTML = "<p>Unable to load your financial summary right now.</p>";
        }

        if (categoryBreakdown) {
            categoryBreakdown.innerHTML = "<p>No spending breakdown available yet.</p>";
        }

        if (recommendations) {
            recommendations.innerHTML = "<p>💡 Add more transactions to unlock personalized recommendations.</p>";
        }
    }
}


function displayInsights(data) {
    const summaryText = data?.summary || data?.ai_summary || "Your financial summary is ready.";
    const categories = data?.category_breakdown || {};
    const recommendationData = data?.ai_recommendations ?? [];

    totalIncome.textContent = formatCurrency(data?.total_income ?? 0);
    totalExpenses.textContent = formatCurrency(data?.total_expenses ?? 0);
    balance.textContent = formatCurrency(data?.balance ?? 0);

    aiSummary.innerHTML = "";
    const summaryParagraph = document.createElement("p");
    summaryParagraph.textContent = summaryText;
    aiSummary.appendChild(summaryParagraph);

    categoryBreakdown.innerHTML = "";

    if (Object.keys(categories).length === 0) {
        categoryBreakdown.innerHTML = "<p>No spending data available yet.</p>";
    } else {
        Object.entries(categories).forEach(([category, amount]) => {
            const item = document.createElement("div");
            item.className = "category-item";

            const label = document.createElement("strong");
            label.textContent = category;

            const value = document.createElement("span");
            value.textContent = formatCurrency(amount);

            item.appendChild(label);
            item.appendChild(value);
            categoryBreakdown.appendChild(item);
        });
    }

    recommendations.innerHTML = "";

    if (Array.isArray(recommendationData) && recommendationData.length > 0) {
        recommendationData.forEach((recommendation) => {
            const item = document.createElement("p");
            item.textContent = `💡 ${recommendation}`;
            recommendations.appendChild(item);
        });
    } else if (data?.ai_recommendations) {
        const item = document.createElement("p");
        item.textContent = `💡 ${data.ai_recommendations}`;
        recommendations.appendChild(item);
    } else {
        const item = document.createElement("p");
        item.textContent = "💡 Keep tracking your expenses to receive personalized recommendations.";
        recommendations.appendChild(item);
    }
}


if (logoutBtn) {
    logoutBtn.addEventListener("click", function (event) {
        event.preventDefault();
        localStorage.removeItem("access_token");
        window.location.href = "../index.html";
    });
}


loadAIInsights();