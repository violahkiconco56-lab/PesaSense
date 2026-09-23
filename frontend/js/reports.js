const token = localStorage.getItem("access_token");

const reportType = document.getElementById("reportType");
const reportDate = document.getElementById("reportDate");
const loadReportButton = document.getElementById("loadReportButton");

const reportSummary = document.getElementById("reportSummary");
const categoryBreakdown = document.getElementById("categoryBreakdown");
const reportTransactions = document.getElementById("reportTransactions");


function formatUGX(amount) {
    return `UGX ${Number(amount).toLocaleString()}`;
}


function setDefaultDate() {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, "0");
    const day = String(today.getDate()).padStart(2, "0");

    reportDate.value = `${year}-${month}-${day}`;
}


async function loadReport() {

    if (!token) {
        window.location.href = "../index.html";
        return;
    }

    const selectedType = reportType.value;
    const selectedDate = reportDate.value;

    if (!selectedDate) {
        reportSummary.innerHTML =
            "<p>Please select a report date.</p>";
        return;
    }

    const dateObject = new Date(`${selectedDate}T00:00:00`);

    const day = String(dateObject.getDate()).padStart(2, "0");
    const month = dateObject.getMonth() + 1;
    const year = dateObject.getFullYear();

    let url = "";

    if (selectedType === "daily") {

        url = `http://127.0.0.1:8000/reports/daily?report_date=${selectedDate}`;

    } else if (selectedType === "weekly") {

        url = `http://127.0.0.1:8000/reports/weekly?report_date=${selectedDate}`;

    } else if (selectedType === "monthly") {

        url = `http://127.0.0.1:8000/reports/monthly?month=${month}&year=${year}`;

    } else if (selectedType === "yearly") {

        url = `http://127.0.0.1:8000/reports/yearly?year=${year}`;
    }


    try {

        const response = await fetch(url, {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Failed to load report"
            );
        }


        // Summary
        reportSummary.innerHTML = `
            <p><strong>Start Date:</strong> ${data.start_date}</p>
            <p><strong>End Date:</strong> ${data.end_date}</p>
            <p><strong>Transactions:</strong> ${data.transaction_count}</p>
            <p><strong>Total Income:</strong> ${formatUGX(data.total_income)}</p>
            <p><strong>Total Expenses:</strong> ${formatUGX(data.total_expenses)}</p>
            <p><strong>Balance:</strong> ${formatUGX(data.balance)}</p>
        `;


        // Category Breakdown
        categoryBreakdown.innerHTML = "";

        const categories = data.category_breakdown || {};

        if (Object.keys(categories).length === 0) {

            categoryBreakdown.innerHTML =
                "<p>No category spending found.</p>";

        } else {

            Object.entries(categories).forEach(
                ([category, amount]) => {

                    const categoryElement =
                        document.createElement("p");

                    categoryElement.textContent =
                        `${category}: ${formatUGX(amount)}`;

                    categoryBreakdown.appendChild(
                        categoryElement
                    );
                }
            );
        }


        // Transactions
        reportTransactions.innerHTML = "";

        if (
            !data.transactions ||
            data.transactions.length === 0
        ) {

            reportTransactions.innerHTML =
                "<p>No transactions found for this period.</p>";

        } else {

            data.transactions.forEach(transaction => {

                const transactionElement =
                    document.createElement("p");

                transactionElement.textContent =
                    `${transaction.transaction_type} - ` +
                    `${transaction.description} - ` +
                    `${transaction.category} - ` +
                    `${formatUGX(transaction.amount)}`;

                reportTransactions.appendChild(
                    transactionElement
                );
            });
        }

    } catch (error) {

        console.error(error);

        reportSummary.innerHTML =
            `<p>${error.message}</p>`;

        categoryBreakdown.innerHTML = "";
        reportTransactions.innerHTML = "";
    }
}


loadReportButton.addEventListener(
    "click",
    loadReport
);


setDefaultDate();
loadReport();