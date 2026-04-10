// Shared validation logic for agent create/edit forms

function showError(input, message) {
    let container = input.parentElement;
    let errorDiv = null;
    while (container && !errorDiv) {
        errorDiv = container.querySelector('.error-message');
        if (!errorDiv) container = container.parentElement;
    }
    if (errorDiv) {
        errorDiv.textContent = message;
    }
    input.classList.add('border-danger');
}

function clearError(input) {
    let container = input.parentElement;
    let errorDiv = null;
    while (container && !errorDiv) {
        errorDiv = container.querySelector('.error-message');
        if (!errorDiv) container = container.parentElement;
    }
    if (errorDiv) {
        errorDiv.textContent = '';
    }
    input.classList.remove('border-danger');
}

function validateAgentForm(form, isEdit = false) {
    // Returns true if valid, false if not
    let valid = true;
    // Full Name
    const fullNameInput = form.querySelector('input[name="full_name"]');
    if (!fullNameInput.value.trim()) {
        valid = false;
        showError(fullNameInput, 'Full name is required.');
    }
    // Email
    const emailInput = form.querySelector('input[name="email"]');
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailInput.value.trim()) {
        valid = false;
        showError(emailInput, 'Email is required.');
    } else if (!emailPattern.test(emailInput.value)) {
        valid = false;
        showError(emailInput, 'Enter a valid email address (e.g., abc@gmail.com)');
    }
    // Phone
    const phoneInput = form.querySelector('input[name="phone"]');
    const phonePattern = /^[0-9]{10}$/;
    if (!phoneInput.value.trim()) {
        valid = false;
        showError(phoneInput, 'Phone number is required.');
    } else if (!phonePattern.test(phoneInput.value)) {
        valid = false;
        showError(phoneInput, 'Enter a valid 10-digit phone number.');
    }
    // Area
    const areaInput = form.querySelector('input[name="area"]');
    if (!areaInput.value.trim()) {
        valid = false;
        showError(areaInput, 'Area is required.');
    }
    // Password (only if not edit or if filled in edit)
    const passwordInput = form.querySelector('input[name="password"]');
    const confirmPasswordInput = form.querySelector('input[name="confirm_password"]');
    if (!isEdit || (passwordInput && passwordInput.value)) {
        if (!passwordInput.value) {
            valid = false;
            showError(passwordInput, 'Password is required.');
        } else if (passwordInput.value.length < 8) {
            valid = false;
            showError(passwordInput, 'Password must be at least 8 characters.');
        }
        if (!confirmPasswordInput.value) {
            valid = false;
            showError(confirmPasswordInput, 'Confirm password is required.');
        } else if (passwordInput.value !== confirmPasswordInput.value) {
            valid = false;
            showError(confirmPasswordInput, 'Passwords do not match.');
        }
    }
    // Status
    const statusInput = form.querySelector('select[name="status"]');
    if (!statusInput.value) {
        valid = false;
        showError(statusInput, 'Status is required.');
    }
    // ID Proof (required for create, optional for edit)
    const idProofInput = form.querySelector('input[name="id_proof"]');
    if (!isEdit && (!idProofInput.files || idProofInput.files.length === 0)) {
        valid = false;
        showError(idProofInput, 'ID Proof is required.');
    }
    // Photo (required for create, optional for edit)
    const photoInput = form.querySelector('input[name="photo"]');
    if (!isEdit && (!photoInput.files || photoInput.files.length === 0)) {
        valid = false;
        showError(photoInput, 'Photo is required.');
    }
    return valid;
}

function setupAgentFormRealtimeValidation(form, isEdit = false) {
    form.querySelectorAll('input, select').forEach(function(input) {
        // Restrict phone input to digits and max 10 characters
        if (input.name === 'phone') {
            input.setAttribute('maxlength', '10');
            input.addEventListener('input', function(e) {
                // Remove non-digit characters
                let cleaned = input.value.replace(/\D/g, '');
                if (cleaned.length > 10) cleaned = cleaned.slice(0, 10);
                if (input.value !== cleaned) input.value = cleaned;
            });
        }
        input.addEventListener('input', function() {
            // Full Name
            if (input.name === 'full_name') {
                if (!input.value.trim()) {
                    showError(input, 'Full name is required.');
                } else {
                    clearError(input);
                }
            }
            // Email
            if (input.name === 'email') {
                const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!input.value.trim()) {
                    showError(input, 'Email is required.');
                } else if (!emailPattern.test(input.value)) {
                    showError(input, 'Enter a valid email address (e.g., abc@gmail.com)');
                } else {
                    clearError(input);
                }
            }
            // Phone
            if (input.name === 'phone') {
                const phonePattern = /^[0-9]{10}$/;
                if (!input.value.trim()) {
                    showError(input, 'Phone number is required.');
                } else if (!phonePattern.test(input.value)) {
                    showError(input, 'Enter a valid 10-digit phone number.');
                } else {
                    clearError(input);
                }
            }
            // Area
            if (input.name === 'area') {
                if (!input.value.trim()) {
                    showError(input, 'Area is required.');
                } else {
                    clearError(input);
                }
            }
            // Password
            if (input.name === 'password') {
                if (!isEdit || input.value) {
                    if (!input.value) {
                        showError(input, 'Password is required.');
                    } else if (input.value.length < 8) {
                        showError(input, 'Password must be at least 8 characters.');
                    } else {
                        clearError(input);
                    }
                    // Also validate confirm password if present
                    const confirmPasswordInput = form.querySelector('input[name="confirm_password"]');
                    if (confirmPasswordInput && confirmPasswordInput.value) {
                        if (confirmPasswordInput.value !== input.value) {
                            showError(confirmPasswordInput, 'Passwords do not match.');
                        } else {
                            clearError(confirmPasswordInput);
                        }
                    }
                }
            }
            // Confirm Password
            if (input.name === 'confirm_password') {
                const passwordInput = form.querySelector('input[name="password"]');
                if (!isEdit || passwordInput.value) {
                    if (!input.value) {
                        showError(input, 'Confirm password is required.');
                    } else if (passwordInput && input.value !== passwordInput.value) {
                        showError(input, 'Passwords do not match.');
                    } else {
                        clearError(input);
                    }
                }
            }
            // ID Proof
            if (input.name === 'id_proof') {
                if (!isEdit && (!input.files || input.files.length === 0)) {
                    showError(input, 'ID Proof is required.');
                } else {
                    clearError(input);
                }
            }
            // Photo
            if (input.name === 'photo') {
                if (!isEdit && (!input.files || input.files.length === 0)) {
                    showError(input, 'Photo is required.');
                } else {
                    clearError(input);
                }
            }
        });
        if (input.tagName === 'SELECT') {
            input.addEventListener('change', function() {
                if (input.name === 'status') {
                    if (!input.value) {
                        showError(input, 'Status is required.');
                    } else {
                        clearError(input);
                    }
                }
            });
        }
    });
}

function setupPasswordVisibilityToggle(form) {
    if (!form) return;
    const toggles = form.querySelectorAll('.password-toggle');
    toggles.forEach(function(toggle) {
        const targetName = toggle.dataset.target;
        if (!targetName) return;
        const input = form.querySelector('[name="' + targetName + '"]');
        if (!input) return;

        toggle.addEventListener('click', function () {
            if (input.type === 'password') {
                input.type = 'text';
            } else {
                input.type = 'password';
            }
        });
    });
}

// Export for use in Django templates
window.agentFormValidation = {
    showError,
    clearError,
    validateAgentForm,
    setupAgentFormRealtimeValidation,
    setupPasswordVisibilityToggle
};