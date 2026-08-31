const token = localStorage.getItem("access_token");

const transactionsList = document.getElementById("transactionsList");
const transactionForm = document.getElementById("transactionForm");
const transactionMessage = document.getElementById("transactionMessage");


async function loadTransactions() {

    if (!token) {
        window.location.href = "../index.html";
        return;
    }

    try {
        const response = await fetch(
            "http://127.0.0.1:8000/transactions/?skip=0&limit=100",
            {
                method: "GET",
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to load transactions");
        }

        transactionsList.innerHTML = "";

        if (data.length === 0) {
            transactionsList.innerHTML = "<p>No transactions found.</p>";
            return;
        }

        data.forEach(transaction => {

            const transactionElement = document.createElement("div");

            transactionElement.innerHTML = `
                <p>
                    <strong>${transaction.transaction_type}</strong>
                    -
                    ${transaction.description}
                    -
                    ${transaction.category}
                    -
                    UGX ${transaction.amount.toLocaleString()}
                    -
                    ${new Date(transaction.date).toLocaleDateString()}
                </p>
            `;

            transactionsList.appendChild(transactionElement);
        });

    } catch (error) {

        console.error(error);

        transactionsList.innerHTML =
            "<p>Unable to load transactions.</p>";
    }
}


transactionForm.addEventListener("submit", async function (event) {

    event.preventDefault();

    const transaction = {
        transaction_type:
            document.getElementById("transactionType").value,

        amount:
            Number(document.getElementById("amount").value),

        category:
            document.getElementById("category").value,

        description:
            document.getElementById("description").value,

        date:
            document.getElementById("date").value
    };


    try {

        const response = await fetch(
            "http://127.0.0.1:8000/transactions/",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },

                body: JSON.stringify(transaction)
            }
        );


        const data = await response.json();


        if (!response.ok) {
            throw new Error(data.detail || "Failed to create transaction");
        }


        transactionMessage.textContent =
            "Transaction added successfully!";


        transactionForm.reset();

        loadTransactions();


    } catch (error) {

        console.error(error);

        transactionMessage.textContent =
            error.message;
    }

});


loadTransactions();