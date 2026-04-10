function setupProfilePhotoUploader(e) {
    const fileInput = e;
    if (!fileInput) {
        return;
    }
    const form = document.getElementById('profilePhotoForm');
    form.submit();    
}


// Form submission handlers
function handleProfileInfoSubmit(e) {
    e.preventDefault();

    let isValid = true;
    const inputs = this.querySelectorAll("input");

    inputs.forEach((input) => {
        if (!input.value) {
            input.classList.add("border-red-500");
            input.classList.remove("border-gray-300");

            // Ensure there is an error <p> after the 
            let errorEl = input.nextElementSibling;
            if (!errorEl || errorEl.tagName !== "P") {
                errorEl = document.createElement("p");
                errorEl.className = "mt-1 text-sm text-red-500";
                input.parentNode.insertBefore(errorEl, input.nextSibling);
            }
            errorEl.classList.remove("hidden");
            errorEl.textContent = getErrorMessage(input);
            isValid = false;
        } else {
            input.classList.remove("border-red-500");
            let errorEl = input.nextElementSibling;
            if (errorEl && errorEl.tagName == "P") {
                errorEl.classList.add("hidden");
            }
        }
    });

    if (!isValid) return;

    // submit the form
    profileInfoForm.submit();
}