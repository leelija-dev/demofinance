// static/branch/js/employeeFormValidation.js
document.addEventListener('DOMContentLoaded', function() {
    // Target the employee form specifically to avoid binding to other forms in the layout
    const form = document.getElementById('employee-form') || document.querySelector('form');
    if (!form) return;

    // Determine whether we are editing an existing employee
    const isEditMode = (form.dataset.editMode || '').toLowerCase() === 'true';

    // Password toggle functionality (scoped to this employee form)
    form.querySelectorAll('.password-toggle').forEach(button => {
        button.addEventListener('click', function(event) {
            // Prevent any parent handlers (or form behaviors) from interfering
            if (event) {
                event.preventDefault();
                event.stopPropagation();
                // If another script also binds to this button, avoid double-toggling.
                event.stopImmediatePropagation();
            }

            // Always target the input in the same container (independent of field ids)
            const container = this.parentElement || this.closest('.relative') || this.closest('div');
            if (!container) return;

            // Prefer explicit mapping via data-target => Django input id: id_<field_name>
            const targetName = (this.dataset.target || '').trim();
            let input = null;
            if (targetName) {
                input = form.querySelector(`#id_${targetName}`);
            }
            if (!input) {
                input = this.previousElementSibling;
            }
            if (!input || input.tagName.toLowerCase() !== 'input') {
                input = container.querySelector('input');
            }
            if (!input) return;
            const icon = this.querySelector('svg');
            if (!icon) return;
            const isCurrentlyHidden = input.type === 'password';
            if (isCurrentlyHidden) {
                // Show password
                input.type = 'text';
                icon.innerHTML = `
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                    <path d="M1 1l22 22"/>
                `;
            } else {
                // Hide password
                input.type = 'password';
                icon.innerHTML = `
                    <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z"></path>
                    <circle cx="12" cy="12" r="3"></circle>
                `;
            }
        });
    });

    // Initialize Flatpickr for Date of Birth field (if available)
    const dobInput = form.querySelector('#id_date_of_birth');
    if (dobInput && window.flatpickr) {
        const dobPicker = window.flatpickr(dobInput, {
            // Value sent to the server (kept in Django-friendly format)
            dateFormat: 'Y-m-d',
            // Format shown to the user
            altInput: true,
            altFormat: 'd-m-Y',
            allowInput: true,
            maxDate: 'today',
        });

        // Auto-insert hyphens in the visible DOB field while typing (dd-, dd-mm-, dd-mm-yyyy)
        if (dobPicker && dobPicker.altInput) {
            dobPicker.altInput.addEventListener('input', function(e) {
                const raw = e.target.value.replace(/\D/g, '').slice(0, 8); // keep only up to ddmmyyyy
                let formatted = '';

                if (raw.length <= 2) {
                    // d, dd
                    formatted = raw;
                } else if (raw.length <= 4) {
                    // ddmm -> dd-mm
                    formatted = `${raw.slice(0, 2)}-${raw.slice(2)}`;
                } else {
                    // ddmmyyyy -> dd-mm-yyyy
                    formatted = `${raw.slice(0, 2)}-${raw.slice(2, 4)}-${raw.slice(4)}`;
                }

                e.target.value = formatted;
            });
        }
    }

    // Form validation
    form.addEventListener('submit', function(e) {
        // Prevent the default form submission
        e.preventDefault();
        
        let isValid = true;

        // Clear previous errors
        document.querySelectorAll('.error-message').forEach(el => el.remove());
        document.querySelectorAll('.is-invalid').forEach(el => {
            el.classList.remove('is-invalid', 'border-red-500', 'focus:border-red-500', 'focus:ring-red-500');
        });

        const firstName = form.querySelector('#id_first_name');
        const lastName = form.querySelector('#id_last_name');
        const email = form.querySelector('#id_email');
        const phoneNumber = form.querySelector('#id_phone_number');
        const gender = form.querySelector('#id_gender');
        const role = form.querySelector('#id_role');
        const govIdType = form.querySelector('#id_gov_id_type');
        const govIdNumber = form.querySelector('#id_gov_id_number');
        const password = form.querySelector('#id_password');
        const confirmPassword = form.querySelector('#id_confirm_password');

        // Required field checks (empty values)
        const requiredFields = [
            firstName,
            lastName,
            email,
            phoneNumber,
            gender,
            role,
            govIdType,
            govIdNumber,
        ];

        requiredFields.forEach(fieldEl => {
            if (fieldEl && !fieldEl.value.trim()) {
                showError(fieldEl, 'This field is required');
                isValid = false;
            }
        });

        // Email validation (only if not empty)
        if (email && email.value.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim())) {
            showError(email, 'Please enter a valid email address.');
            isValid = false;
        }

        // Phone number validation (10 digits, only if not empty)
        if (phoneNumber && phoneNumber.value.trim() && !/^\d{10}$/.test(phoneNumber.value.trim())) {
            showError(phoneNumber, 'Contact number must be exactly 10 digits.');
            isValid = false;
        }

        // Password validation (if not in edit mode or if password is provided)
        if (password) {
            if (!isEditMode && (!password.value || password.value.length < 8)) {
                showError(password, 'Password must be at least 8 characters long');
                isValid = false;
            } else if (password.value && password.value.length < 8) {
                showError(password, 'Password must be at least 8 characters long');
                isValid = false;
            }
        }

        // Confirm password validation
        if (confirmPassword && password && confirmPassword.value !== password.value) {
            showError(confirmPassword, 'Passwords do not match');
            isValid = false;
        }

        // Government ID validation
        if (govIdType && govIdNumber && govIdNumber.value.trim()) {
            const validGov = validateGovId(govIdType.value, govIdNumber);
            if (!validGov) {
                isValid = false;
            }
        }

        if (!isValid) {
            e.preventDefault();
            // Scroll to first error
            const firstError = document.querySelector('.is-invalid');
            if (firstError) {
                firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
        
        if (isValid) {
            form.submit();
        }
        
    });

    // Real-time clearing of errors when the user fixes input
    const realtimeFields = [
        form.querySelector('#id_first_name'),
        form.querySelector('#id_last_name'),
        form.querySelector('#id_email'),
        form.querySelector('#id_phone_number'),
        form.querySelector('#id_gender'),
        form.querySelector('#id_role'),
        form.querySelector('#id_gov_id_type'),
        form.querySelector('#id_gov_id_number'),
        form.querySelector('#id_password'),
        form.querySelector('#id_confirm_password'),
    ];

    realtimeFields.forEach(field => {
        if (!field) return;
        const isSelect = field.tagName.toLowerCase() === 'select';
        const inputEvent = isSelect ? 'change' : 'input';

        // Live validation while typing/changing
        field.addEventListener(inputEvent, function() {
            const value = this.value.trim();

            // For email, show/hide validation messages live
            if (this.id === 'id_email') {
                if (!value) {
                    // Empty email: leave it to required check on submit
                    clearFieldError(this);
                } else if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
                    clearFieldError(this);
                } else {
                    showError(this, 'Please enter a valid email address.');
                }
                return;
            }

            // For phone, enforce digits/length and show message live
            if (this.id === 'id_phone_number') {
                // Force-only digits and max length 10
                const digitsOnly = value.replace(/\D/g, '').substring(0, 10);
                if (this.value !== digitsOnly) {
                    this.value = digitsOnly;
                }

                if (!digitsOnly) {
                    // Empty phone: leave it to required check on submit
                    clearFieldError(this);
                } else if (/^\d{10}$/.test(digitsOnly)) {
                    clearFieldError(this);
                } else {
                    showError(this, 'Contact number must be exactly 10 digits.');
                }
                return;
            }

            // Password live validation: length >= 8 when not empty
            if (this.id === 'id_password') {
                if (!value) {
                    clearFieldError(this);
                } else if (value.length < 8) {
                    showError(this, 'Password must be at least 8 characters long');
                } else {
                    clearFieldError(this);
                }
                return;
            }

            // Confirm password live validation: must match password when both entered
            if (this.id === 'id_confirm_password') {
                const pwdInput = form.querySelector('#id_password');
                const pwdVal = pwdInput ? pwdInput.value.trim() : '';

                if (!value) {
                    clearFieldError(this);
                } else if (pwdVal && value !== pwdVal) {
                    showError(this, 'Passwords do not match');
                } else {
                    clearFieldError(this);
                }
                return;
            }

            // For other fields: clear error as soon as there is some value
            if (value) {
                clearFieldError(this);
            }
        });

        // On blur/focus-out: if required and still empty, show required error
        field.addEventListener('blur', function() {
            const value = this.value.trim();

            // In edit mode, password fields are optional: don't force "required" on blur
            if (isEditMode && (this.id === 'id_password' || this.id === 'id_confirm_password')) {
                return;
            }

            // Skip if there is already a more specific error (email/phone/gov id etc.)
            if (!value) {
                showError(this, 'This field is required');
            }
        });
    });

    // Real-time validation for government ID based on type
    const govIdType = form.querySelector('#id_gov_id_type');
    const govIdNumber = form.querySelector('#id_gov_id_number');

    if (govIdType && govIdNumber) {
        // Update placeholder when gov ID type changes
        govIdType.addEventListener('change', function() {
            updateGovIdPlaceholder();
            // Re-validate current number when type changes
            if (govIdNumber.value.trim()) {
                validateGovId(govIdType.value, govIdNumber);
            } else {
                clearFieldError(govIdNumber);
            }
        });
        
        // Initial call to set placeholder
        updateGovIdPlaceholder();

        // Format Aadhar number and validate as user types
        govIdNumber.addEventListener('input', function(e) {
            if (govIdType.value === 'aadhar') {
                const value = e.target.value.replace(/\D/g, '').substring(0, 12);
                const formatted = value.replace(/(\d{4})(?=\d)/g, '$1 ').trim();
                if (e.target.value !== formatted) {
                    e.target.value = formatted;
                }
            } else if (govIdType.value === 'pan') {
                // PAN: uppercase and max 10 characters
                const value = e.target.value.toUpperCase().substring(0, 10);
                if (e.target.value !== value) {
                    e.target.value = value;
                }
            } else {
                // Auto-format other ID types to uppercase
                e.target.value = e.target.value.toUpperCase();
            }

            if (govIdNumber.value.trim()) {
                validateGovId(govIdType.value, govIdNumber);
            } else {
                clearFieldError(govIdNumber);
            }
        });
    }

    function updateGovIdPlaceholder() {
        if (!govIdType || !govIdNumber) return;

        switch (govIdType.value) {
            case 'aadhar':
                govIdNumber.placeholder = '1234 5678 9012';
                break;
            case 'pan':
                govIdNumber.placeholder = 'ABCDE1234F';
                break;
            case 'voter_id':
                govIdNumber.placeholder = 'ABC1234567';
                break;
            case 'passport':
                govIdNumber.placeholder = 'A1234567';
                break;
            case 'driving_license':
                govIdNumber.placeholder = 'DL12345678901234';
                break;
            default:
                govIdNumber.placeholder = 'Enter ID number';
        }
    }

    function validateGovId(type, inputEl) {
        if (!inputEl) return true;
        const raw = inputEl.value.replace(/\s/g, '');
        if (!raw) {
            clearFieldError(inputEl);
            return true;
        }

        switch (type) {
            case 'aadhar':
                if (!/^\d{12}$/.test(raw)) {
                    showError(inputEl, 'Aadhar number must be exactly 12 digits.');
                    return false;
                }
                clearFieldError(inputEl);
                return true;
            case 'pan':
                if (!/^[A-Z]{5}\d{4}[A-Z]$/i.test(raw)) {
                    showError(inputEl, 'PAN must be in the format ABCDE1234F.');
                    return false;
                }
                clearFieldError(inputEl);
                return true;
            case 'voter_id':
                if (!/^[A-Z]{3}\d{7}$/i.test(raw)) {
                    showError(inputEl, 'Voter ID must be 3 letters followed by 7 digits.');
                    return false;
                }
                clearFieldError(inputEl);
                return true;
            case 'passport':
                if (!/^[A-Z0-9]{8}$/i.test(raw)) {
                    showError(inputEl, 'Passport number must be 8 alphanumeric characters.');
                    return false;
                }
                clearFieldError(inputEl);
                return true;
            case 'driving_license':
                if (!/^[A-Z0-9]{16}$/i.test(raw)) {
                    showError(inputEl, 'Driving license number must be 16 alphanumeric characters.');
                    return false;
                }
                clearFieldError(inputEl);
                return true;
            default:
                // 'others' type has no specific pattern validation
                clearFieldError(inputEl);
                return true;
        }
    }

    function clearFieldError(input) {
        if (!input) return;
        input.classList.remove('is-invalid', 'border-red-500', 'focus:border-red-500', 'focus:ring-red-500');
        if (input.parentNode) {
            input.parentNode.querySelectorAll('.error-message').forEach(el => el.remove());
        }
    }

    function showError(input, message) {
        if (!input) return;

        // Remove any existing error for this field first to avoid stacking messages
        if (input.parentNode) {
            input.parentNode.querySelectorAll('.error-message').forEach(el => el.remove());
        }

        // Add generic invalid class plus red border styles
        input.classList.add('is-invalid', 'border-red-500', 'focus:border-red-500', 'focus:ring-red-500');

        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message text-red-600 text-sm mt-1';
        errorDiv.textContent = message;
        
        // Insert after the input
        const parent = input.parentNode;
        if (!parent) return;
        if (input.nextSibling) {
            parent.insertBefore(errorDiv, input.nextSibling);
        } else {
            parent.appendChild(errorDiv);
        }
    }
});