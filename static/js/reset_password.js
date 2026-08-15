function togglePassword(id, button) {
    const input = document.getElementById(id);
    const isHidden = input.type === "password";

    input.type = isHidden ? "text" : "password";
    button.textContent = isHidden ? "🙈" : "👁";
    button.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
}