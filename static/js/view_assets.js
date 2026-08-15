const modal = document.getElementById("deactivateModal");
const modalText = document.getElementById("modalText");
const confirmDeactivate = document.getElementById("confirmDeactivate");
const modalClose = document.getElementById("modalClose");
const cancelButton = document.getElementById("cancelButton");

document.querySelectorAll(".deactivate-btn").forEach((button) => {
    button.addEventListener("click", () => {
        const kapanNumber = button.dataset.kapan;
        confirmDeactivate.href = button.dataset.url;
        modalText.textContent = `Kapan ${kapanNumber} will be marked as inactive.`;
        modal.classList.add("show");
    });
});

function closeModal() {
    modal.classList.remove("show");
}

modalClose.addEventListener("click", closeModal);
cancelButton.addEventListener("click", closeModal);

modal.addEventListener("click", (event) => {
    if (event.target === modal) {
        closeModal();
    }
});

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        closeModal();
    }
});