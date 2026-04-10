let agentData = window.agentData ?? null;
window.agentData = agentData;

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
        const response = await fetch("/agent/api/change-password", {
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
                window.location.href = '/agent/profile/';
            }, 2000);
        } else {
            passwordError.classList.remove("hidden");
            passwordError.textContent = result.message;
        }
    } catch (error) {
        passwordError.classList.remove("hidden");
        passwordError.textContent = "Error updating password.";
        console.error("Error updating password:", error);
    }

    document.getElementById("changePasswordModal").classList.add("hidden");;
    document.body.classList.remove("overflow-hidden");
}

function showNotification(message, type = "info") {
    alert(`${type.toUpperCase()}: ${message}`);
}

function getCSRFToken() {
    const cookieValue = document.cookie
        .split("; ")
        .find((row) => row.startsWith("csrftoken="))
        ?.split("=")[1];
    return cookieValue || "";
}

// Password strength checker
function getPasswordStrength(password) {
    let strength = 0;

    if (password.length >= 6) strength++;
    if (/[A-Z]/.test(password)) strength++;
    if (/[0-9]/.test(password)) strength++;
    if (/[^A-Za-z0-9]/.test(password)) strength++;

    if (strength <= 1) return { label: "Weak", color: "text-red-600" };
    if (strength === 2) return { label: "Medium", color: "text-yellow-600" };
    if (strength >= 3) return { label: "Strong", color: "text-green-600" };
}

async function fetchAgentData() {
      try {
        const response = await fetch("/agent/api/agent-info/");
        const data = await response.json();

        if (data.success) {
          agentData = data.agent;
          populateProfileData();
        } else {
          console.error("Failed to fetch agent data");
        }
      } catch (error) {
        console.error("Error fetching agent data:", error);
      }
    }

    function populateProfileData() {
      if (!agentData) return;

      const fields = {
        fullName: document.querySelectorAll('[data-field="fullName"]'),
        email: document.querySelectorAll('[data-field="email"]'),
        phone: document.querySelectorAll('[data-field="phone"]'),
        agentId: document.querySelectorAll('[data-field="agentId"]'),
        role: document.querySelectorAll('[data-field="role"]'),
        photo: document.querySelectorAll('[data-field="photo"]'),
      };

      fields.fullName.forEach((el) => (el.textContent = agentData.full_name || "N/A"));
      fields.email.forEach((el) => (el.textContent = agentData.email || "N/A"));
      fields.phone.forEach((el) => (el.textContent = agentData.phone || "N/A"));
      fields.agentId.forEach((el) => (el.textContent = agentData.agent_id || "N/A"));
      fields.role.forEach((el) => (el.textContent = agentData.role || "N/A"));

      fields.photo.forEach((el) => {
        if (agentData.photo_url) {
          el.src = agentData.photo_url;
          el.alt = agentData.full_name || "Agent Photo";
        }
      });
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

function updatePhotoElements(src) {
    document.querySelectorAll('[data-field="photo"]').forEach((el) => {
        el.src = src;
    });
}

async function uploadProfilePhoto(file) {
    const formData = new FormData();
    formData.append("photo", file);

    const response = await fetch("/agent/api/image-update/", {
        method: "POST",
        headers: {
            "X-CSRFToken": getCSRFToken(),
        },
        body: formData,
    });

    const result = await response.json();
    if (!result.success) {
        throw new Error(result.message || "Unable to update profile photo.");
    }

    if (result.photo_url) {
        updatePhotoElements(result.photo_url);
    }

    if (typeof window.showToast === "function") {
        window.showToast(result.message || "Profile photo updated successfully!", "success");
    }
}

function setupProfilePhotoUploader() {
    const fileInput = document.getElementById("profilePhotoInput");
    if (!fileInput) {
        return;
    }

    fileInput.addEventListener("change", async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = function (e) {
            if (e.target?.result) {
                updatePhotoElements(e.target.result);
            }
        };
        reader.readAsDataURL(file);

        try {
            await uploadProfilePhoto(file);
        } catch (error) {
            console.error("Error updating profile photo:", error);
            if (typeof window.showToast === "function") {
                window.showToast(error.message || "Error updating profile photo.", "error");
            } else {
                alert(error.message || "Error updating profile photo.");
            }
            if (typeof agentData !== "undefined" && agentData?.photo_url) {
                updatePhotoElements(agentData.photo_url);
            }
        } finally {
            event.target.value = "";
        }
    });
}