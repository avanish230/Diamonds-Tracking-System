function togglePassword(id, button) {
    const input = document.getElementById(id);
    const isPassword = input.type === "password";

    input.type = isPassword ? "text" : "password";
    button.textContent = isPassword ? "🙈" : "👁";
    button.setAttribute("aria-label", isPassword ? "Hide password" : "Show password");
}

document.addEventListener("DOMContentLoaded", () => {
    const roleRadios = document.querySelectorAll('input[name="role"]');
    const managerDiv = document.getElementById("managerDiv");
    const managerSelect = document.getElementById("manager_id");

    function toggleManagerField() {
        const selectedRole = document.querySelector('input[name="role"]:checked');
        const isEmployee = selectedRole && selectedRole.value === "employee";

        managerDiv.classList.toggle("show", isEmployee);
        managerSelect.required = isEmployee;

        if (!isEmployee) {
            managerSelect.value = "";
        }
    }

    roleRadios.forEach((radio) => {
        radio.addEventListener("change", toggleManagerField);
    });

    toggleManagerField();
});