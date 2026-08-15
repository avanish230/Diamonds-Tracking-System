const profileButton = document.getElementById("profileButton");
const profileDropdown = document.getElementById("profileDropdown");

profileButton.addEventListener("click", (event) => {
    event.stopPropagation();
    profileDropdown.classList.toggle("show");
});

document.addEventListener("click", (event) => {
    if (!event.target.closest(".profile-menu")) {
        profileDropdown.classList.remove("show");
    }
});