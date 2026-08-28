const loginForm = document.getElementById("loginForm");
const message = document.getElementById("message");

loginForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;

    const formData = new URLSearchParams();

    formData.append("username", username);
    formData.append("password", password);

    try {
        const response = await fetch("http://127.0.0.1:8000/users/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            localStorage.setItem("access_token", data.access_token);

            message.textContent = "Login successful!";

            console.log("Login successful:", data);
        } else {
            message.textContent = data.detail || "Login failed.";
        }

    } catch (error) {
        message.textContent = "Could not connect to the server.";
        console.error(error);
    }
});