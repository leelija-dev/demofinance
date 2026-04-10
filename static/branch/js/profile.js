const API_URL = "/branch/api/manager-info/";

// Fetch manager data from API
async function fetchManagerData() {
    try {
        // Show loading state
        document.querySelectorAll('[data-field]').forEach(el => {
            if (el.textContent === 'Loading...') return;
            el.textContent = 'Loading...';
        });

        const response = await fetch(API_URL);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();

        if (data.success && data.manager) {
            updateUIWithManagerData(data.manager);
        } else {
            console.error("API response indicates failure:", data);
        }
    } catch (error) {
        console.error("Error fetching manager data:", error);
    }
}

// Update UI with manager data
function updateUIWithManagerData(manager) {
    const fields = {
        fullName: manager.full_name,
        firstName: manager.first_name,
        lastName: manager.last_name,
        profile_img: manager.profile_img ? `${window.location.origin}${manager.profile_img}` : '',
        email: manager.email,
        phone: manager.phone_number,
        managerName: manager.manager.name,
        managerEmail: manager.manager.email,
        managerPhone: manager.manager.phone,
        dateOfBirth: manager.date_of_birth,
        govId: `${manager.gov_id_type ? manager.gov_id_type.toUpperCase() : 'ID'}: ${manager.gov_id_number}`,
        address: manager.address,
        jobTitle: manager.role.role_name,
        branch_name: manager.branch.branch_name,
        branch_id: manager.branch.branch_id,
        branch_address: manager.branch.address,
        branch_contact_number: manager.branch.contact_number,
        branch_email: manager.branch.email,
        branch_address_line_1: manager.branch.address_line_1,
        branch_address_line_2: manager.branch.address_line_2 ? `, ${manager.branch.address_line_2}` : '',
        branch_city: manager.branch.city,
        branch_state: manager.branch.state,
        branch_postal_code: manager.branch.postal_code ? `, ${manager.branch.postal_code}` : '',
        branch_district: manager.branch.district,
        branch_country: manager.branch.country ? `, ${manager.branch.country}` : '',
    };

    // Update each field in the UI
    Object.entries(fields).forEach(([key, value]) => {
        const elements = document.querySelectorAll(`[data-field="${key}"]`);
        elements.forEach(el => {
            if (key === 'profile_img') {
                el.src = value;
            } else {
                el.textContent = value;
            }
        });
    });
}

// Update profile info in UI
function updateProfileInfo(formData) {
    const fields = {
        firstName: document.querySelector('[data-field="firstName"]'),
        lastName: document.querySelector('[data-field="lastName"]'),
        fullName: document.querySelector('[data-field="fullName"]'),
        email: document.querySelector('[data-field="email"]'),
        phone: document.querySelector('[data-field="phone"]'),
    };

    // Only update fields that exist
    if (fields.firstName)
        fields.firstName.textContent = formData.get("firstName");
    if (fields.lastName)
        fields.lastName.textContent = formData.get("lastName");
    if (fields.fullName)
        fields.fullName.textContent = `${formData.get("firstName")} ${formData.get("lastName")}`;
    if (fields.email) fields.email.textContent = formData.get("email");
    if (fields.phone) fields.phone.textContent = formData.get("phone");
}

async function chnagepassword(e) {
    e.preventDefault();

    const formData = new FormData(this);

    const newPassword = formData.get("new-password");
    const confirmPassword = formData.get("confirm-password");
    const passwordError = document.getElementById("passwordError");

    if (newPassword.length < 6 || confirmPassword.length < 6) {
        passwordError.classList.remove("hidden");
        passwordError.textContent = "Password can't be less than 6 characters!";
        return;
    }

    if (newPassword !== confirmPassword) {
        passwordError.classList.remove("hidden");
        passwordError.textContent = "Confirm Password does not match!";
        return;
    }

    try {
        const response = await fetch("/branch/api/change-password/", {
            method: "POST",
            headers: {
                "X-CSRFToken": getCSRFToken(),
            },
            body: formData,
        });

        const result = await response.json();
        if (result.success) {
            window.showToast(result.message || 'Password updated successfully!', 'success');
            setTimeout(() => {
                window.location.href = '/branch/profile/';
            }, 2000);
        } else {
            passwordError.classList.remove("hidden");
            passwordError.textContent = result.message;
            window.showToast(result.message || 'Something went wrong!', 'error');
        }
    } catch (error) {
        passwordError.classList.remove("hidden");
        passwordError.textContent = "Error updating password.";
        window.showToast(error.message || "Error updating password.", 'error');
        console.error("Error updating password:", error);
    }

    document.getElementById("changePasswordModal").classList.add("hidden");;
    document.body.classList.remove("overflow-hidden");
}

function getCSRFToken() {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    return csrfToken;
}

function setupModal(modal) {
    if (!modal) return;
    const closeButtons = modal.querySelectorAll("[data-close]");
    closeButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
            modal.classList.add("hidden");
            document.body.classList.remove("overflow-hidden");
        });
    });

    modal.addEventListener("click", (e) => {
        if (e.target === modal) {
            modal.classList.add("hidden");
            document.body.classList.remove("overflow-hidden");
        }
    });
}