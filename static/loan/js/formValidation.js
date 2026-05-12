// Loan Application Form Validation
(function () {
  // Track touched state for fields
  if (!window.touchedFields) {
    window.touchedFields = new Set();
  }
  const touchedFields = window.touchedFields;

  // Track whether the current form content was populated from a draft
  if (typeof window.CURRENT_FORM_FROM_DRAFT === 'undefined') {
    window.CURRENT_FORM_FROM_DRAFT = false;
  }

    // Helper: show error for a field
    function showFieldError(field, message) {
        // For current address fields, only show if section is visible and checkbox is unchecked
        const sameAddressCheckbox = document.getElementById('same-address');
        const isCurrentField = ['current_address_line_1', 'current_state', 'current_post_code', 'current_city_or_town', 'current_district', 'residential_proof_type', 'residential_proof_file'].includes(field.name);
        
        if (isCurrentField && sameAddressCheckbox && sameAddressCheckbox.checked) {
            clearFieldError(field);
            touchedFields.delete(field.name); // Remove touched state so error doesn't reappear
            return;
        }
        
        // Only show error if field is touched or after submit/continue, and there is a message
        // Also ensure we don't show errors on page load
        if (!message || (!touchedFields.has(field.name) && !window._showAllErrors)) {
            clearFieldError(field);
            return;
        }
        
        const errDiv = document.getElementById('error-' + field.name);
        if (errDiv) {
            errDiv.textContent = message;
            errDiv.classList.add('text-red-600');
            errDiv.classList.remove('text-green-600');
        }
        field.classList.add('border-red-500');
        field.classList.remove('border-green-500');
    }
    // Helper: clear error for a field
    function clearFieldError(field) {
        const errDiv = document.getElementById('error-' + field.name);
        if (errDiv) {
            errDiv.textContent = '';
            errDiv.classList.remove('text-red-600', 'text-green-600');
        }
        field.classList.remove('border-red-500', 'border-green-500');
    }
    
    // Helper: show success for a field (for account number matching)
    function showFieldSuccess(field, message) {
        if (!touchedFields.has(field.name) && !window._showAllErrors) {
            return;
        }
        
        const errDiv = document.getElementById('error-' + field.name);
        if (errDiv) {
            errDiv.textContent = message;
            errDiv.classList.add('text-green-600');
            errDiv.classList.remove('text-red-600');
        }
        field.classList.add('border-green-500');
        field.classList.remove('border-red-500');
    }
    
    // Make clearFieldError available globally
    window.clearFieldError = clearFieldError;
    
    // Error popup function for account number validation
    function showAccountNumberErrorPopup(message) {
        // Create modal overlay
        const modalOverlay = document.createElement('div');
        modalOverlay.className = 'fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm';
        modalOverlay.id = 'account-number-error-modal';
        
        // Create modal content
        const modalContent = document.createElement('div');
        modalContent.className = 'bg-white dark:bg-gray-900 rounded-xl shadow-xl max-w-md w-full mx-4 p-6';
        
        modalContent.innerHTML = `
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-lg font-semibold text-red-600 dark:text-red-400">Account Number Validation Error</h3>
                <button type="button" onclick="closeAccountNumberErrorPopup()" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none">&times;</button>
            </div>
            <div class="mb-6">
                <p class="text-sm text-gray-700 dark:text-gray-300">${message}</p>
            </div>
            <div class="flex justify-end">
                <button type="button" onclick="closeAccountNumberErrorPopup()" class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 focus:outline-hidden focus:ring-2 focus:ring-red-500 focus:ring-offset-2">
                    OK
                </button>
            </div>
        `;
        
        modalOverlay.appendChild(modalContent);
        document.body.appendChild(modalOverlay);
        
        // Add escape key listener
        document.addEventListener('keydown', handleEscapeKey);
    }
    
    // Function to close the error popup
    function closeAccountNumberErrorPopup() {
        const modal = document.getElementById('account-number-error-modal');
        if (modal) {
            modal.remove();
        }
        document.removeEventListener('keydown', handleEscapeKey);
    }
    
    // Handle escape key for closing modal
    function handleEscapeKey(e) {
        if (e.key === 'Escape') {
            closeAccountNumberErrorPopup();
        }
    }
    
    // Make functions available globally
    window.showAccountNumberErrorPopup = showAccountNumberErrorPopup;
    window.closeAccountNumberErrorPopup = closeAccountNumberErrorPopup;

    // Helper function for API calls
async function callDraftAPI(endpoint, method, data = null) {
    try {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
            },
        };

        // Always start with the API path ending in a slash
        let url = `/agent/api/${endpoint}/`;

        if (method === 'GET') {
            const urlParams = new URLSearchParams(data || {}).toString();
            if (urlParams) {
                url += `?${urlParams}`;
            }
        } else if (data) {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(url, options);
        const result = await response.json();
        if (!result.success) throw new Error(result.message || 'API call failed');
        return result;
    } catch (error) {
        console.error(`Draft API ${method} ${endpoint} failed:`, error);
        throw error;
    }
}

    // Helper: apply a draft object to the form fields without changing any
    // existing validation or preview logic.
    function applyDraftToForm(data) {
        if (!data) return;
        const form = document.getElementById('loan-application-form');
        if (!form) return;

        // Mark that the current form state comes from a draft selection
        window.CURRENT_FORM_FROM_DRAFT = true;

        Object.keys(data).forEach(key => {
            const field = document.querySelector(`[name='${key}']`);
            if (!field) return;

            // Date of birth: also update flatpickr if present
            if (key === 'date_of_birth') {
                try {
                    field.value = data[key];
                    if (field._flatpickr) {
                        field._flatpickr.setDate(field.value || null, true);
                    }
                } catch (e) {
                    console.warn('Failed to apply draft date_of_birth', e);
                }
                return;
            }

            if (field.type === 'file') {
                // Cannot set file input value programmatically; just clear and
                // optionally store filename hint for UI (if helper exists).
                field.value = '';
                const draftFilename = data[key + '_filename'] || data[key] || null;
                if (typeof window.setFileDraftHint === 'function') {
                    try {
                        window.setFileDraftHint(field, draftFilename || null);
                    } catch (e) {
                        console.warn('setFileDraftHint failed', e);
                    }
                } else if (draftFilename) {
                    field.dataset.draftFilename = draftFilename;
                }
            } else if (field.type === 'checkbox') {
                const val = data[key];
                const isChecked = val === 'on' || val === true || val === 'true' || val === 1 || val === '1';
                field.checked = !!isChecked;
                if (field.id === 'same-address' || field.name === 'same_address') {
                    // Reuse existing behavior for toggling current address
                    if (typeof window.toggleCurrentAddress === 'function') {
                        window.toggleCurrentAddress(field);
                    }
                }
            } else {
                field.value = data[key];
            }
        });

        // Ensure current address section reflects same-address state, if used
        const sameAddressCheckboxEl = document.getElementById('same-address');
        if (sameAddressCheckboxEl && typeof window.toggleCurrentAddress === 'function') {
            window.toggleCurrentAddress(sameAddressCheckboxEl);
        }

        // Trigger any dependent calculations (like EMI) after values are set
        setTimeout(() => {
            try {
                const loanAmountEl = document.getElementById('loan_amount');
                if (loanAmountEl && loanAmountEl.value) {
                    loanAmountEl.dispatchEvent(new Event('input', { bubbles: true }));
                    loanAmountEl.dispatchEvent(new Event('blur', { bubbles: true }));
                }
                const tenureEl = document.getElementById('tenure_months');
                if (tenureEl && tenureEl.value) {
                    tenureEl.dispatchEvent(new Event('change', { bubbles: true }));
                }
                const interestEl = document.getElementById('interest_rate');
                if (interestEl) {
                    interestEl.dispatchEvent(new Event('input', { bubbles: true }));
                }
                if (window.updateEMI) {
                    window.updateEMI();
                }
            } catch (e) {
                console.warn('Post-draft apply recalculation failed', e);
            }
        }, 150);
    }

    // Validation rules for custom fields
    function customValidation(field) {
        // File validations
        if (field.type === 'file') {
            const files = field.files;
            if (files && files.length > 0) {
                const file = files[0];

                // 1) Max size 1MB for all document/image uploads
                const maxSize = 1024 * 1024; // 1MB in bytes
                if (file.size > maxSize) {
                    return 'File size must be less than or equal to 1MB.';
                }

                // 2) For photo and signature, only allow image types
                if (field.name === 'photo' || field.name === 'signature') {
                    if (!file.type || !file.type.startsWith('image/')) {
                        return 'Please upload an image file (JPG, PNG, etc.).';
                    }
                }
            }
        }
        
        // Check if same address checkbox is checked
        const sameAddressCheckbox = document.getElementById('same-address');
        const isSame = sameAddressCheckbox && sameAddressCheckbox.checked;
        
        if (field.name === 'account_number') {
            const digitsOnly = field.value.replace(/\D/g, '');
            if (digitsOnly !== field.value) {
                field.value = digitsOnly;
            }
            
            if (field.value) {
                if (digitsOnly.length < 9) {
                    return `Account number must be at least 9 digits (${digitsOnly.length}/9 entered).`;
                }
                if (digitsOnly.length > 18) {
                    return 'Account number cannot exceed 18 digits.';
                }
            }
        }
    
        if (field.name === 'confirm_account_number') {
            const accountField = document.getElementById('account_number');
            const digitsOnly = field.value.replace(/\D/g, '');
            if (digitsOnly !== field.value) {
                field.value = digitsOnly;
            }
            
            if (field.value) {
                if (accountField && accountField.value) {
                    if (digitsOnly !== accountField.value) {
                        return 'Account numbers do not match.';
                    } else {
                        // Show success message when numbers match
                        if (touchedFields.has(field.name) || window._showAllErrors) {
                            showFieldSuccess(field, 'Account numbers match!');
                        }
                    }
                } else if (accountField && !accountField.value) {
                    return 'Please enter the account number first.';
                }
            }
        }
    
        if (field.name === 'bank_name') {
            // if (!field.value.trim()) {
            //     return 'Bank name is required.';
            // }
            if (field.value && field.value.trim()) {
                if (field.value.trim().length < 3) {
                    return 'Bank name must be at least 3 characters.';
                }
            }
        }
    
        if (field.name === 'ifsc_code') {
            if (field.value && field.value.trim()) {
                const value = field.value.trim().toUpperCase();
                field.value = value;
                const ifscRegex = /^[A-Z]{4}0[A-Z0-9]{6}$/;
                // if (!value) {
                //     return 'IFSC code is required.';
                // }
                if (!ifscRegex.test(value)) {
                    return 'Enter a valid IFSC code (e.g., SBIN0001234).';
                }
            }
        }
        
        if (field.name === 'date_of_birth') {
            if (field.value && field.value.trim()) {
                const dobValue = field.value.trim();
                const dob = new Date(dobValue);

                if (isNaN(dob.getTime())) {
                    return 'Please enter a valid date of birth.';
                }

                const today = new Date();
                let age = today.getFullYear() - dob.getFullYear();
                const monthDiff = today.getMonth() - dob.getMonth();
                if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
                    age--;
                }

                if (age < 18) {
                    return 'Applicant must be at least 18 years old.';
                }
                if (age > 70) {
                    return 'Applicant age cannot be more than 70 years.';
                }
            }
        }
        
        // If same address is checked, skip validation for current address fields
        if (isSame && ['current_address_line_1', 'current_state', 'current_post_code'].includes(field.name)) {
            return null;
        }
        
        if (field.name === 'adhar_number') {
            // Remove spaces for validation
            const cleanValue = field.value.replace(/\s/g, '');
            if (!/^\d{12}$/.test(cleanValue)) return 'Adhar number must be exactly 12 digits.';
        }
       if (field.name === 'pan_number') {
            const panValue = field.value.toUpperCase(); // normalize
            field.value = panValue; // optional: force uppercase in field
            if (!/^[A-Z]{5}\d{4}[A-Z]$/.test(panValue)) {
                return 'PAN number must be 5 letters, 4 digits, 1 letter (e.g., ABCDE1234F).';
            }
        } 
        if (field.name === 'contact') {
            if (!/^\d{10}$/.test(field.value)) return 'Contact number must be exactly 10 digits.';
        }
        if (field.name === 'voter_number') {
            if (field.value) {
            if (!/^[A-Za-z]{3}\d{7}$/.test(field.value)) return 'Voter ID must be 3 letters followed by 7 digits (e.g. ABC1234567).';
            }
        }
        if (field.name === 'email') {
            if (field.value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(field.value)) {
                return 'Please enter a valid email address.';
            }
        }
        if (field.name === 'post_code') {
            if (!/^\d{6}$/.test(field.value)) return 'Post code must be exactly 6 digits.';
        }
        if (field.name === 'current_post_code') {
            if (!isSame && !/^\d{6}$/.test(field.value)) return 'Current post code must be exactly 6 digits.';
        }
        if (field.name === 'loan_amount') {
            const amount = parseFloat(field.value.replace(/,/g, ''));
            if (isNaN(amount) || amount <= 0) return 'Please enter a valid loan amount.';
            if (amount < 1000) return 'Loan amount must be at least ₹1,000.';
            if (amount > 10000000) return 'Loan amount cannot exceed ₹1,00,00,000.';
        }
        
        // For current address fields, only require if checkbox is unchecked
        if (!isSame) {
            if (field.name === 'current_post_code') {
                if (!field.value) return 'This field is required.';
            }
            if (field.name === 'current_state') {
                if (!field.value) return 'This field is required.';
            }
            if (field.name === 'current_address_line_1') {
                if (!field.value) return 'This field is required.';
            }
            if (field.name === 'current_city_or_town') {
                if (!field.value) return 'This field is required.';
            }
            if (field.name === 'current_district') {
                if (!field.value) return 'This field is required.';
            }
            // Residential proof is required only if current address is different from permanent address
            if (field.name === 'residential_proof_type') {
                if (!field.value) return 'This field is required when current address differs from permanent address.';
            }
            if (field.name === 'residential_proof_file') {
                if (!field.value) return 'This field is required when current address differs from permanent address.';
            }
        }
        return null;
    }
    // Attach instant validation to all required fields and optional fields that need validation
    function attachInstantValidation() {
        const form = document.getElementById('loan-application-form');
        if (!form) return;
        const requiredFields = form.querySelectorAll('input[required], select[required]');
        const optionalFields = form.querySelectorAll('input[name="email"], input[name="voter_number"]');
        const accountFields = form.querySelectorAll('input[name="account_number"], input[name="confirm_account_number"]');

        // Combine required, optional, and account fields for validation
        const allFields = [...requiredFields, ...optionalFields, ...accountFields];

        allFields.forEach(field => {
            field.addEventListener('input', function() {
                touchedFields.add(this.name);
                clearFieldError(this);
                if (!this.value) {
                    // Only show required error for required fields
                    if (this.hasAttribute('required')) {
                        showFieldError(this, 'This field is required.');
                    }
                } else {
                    // Custom validation
                    const customMsg = customValidation(this);
                    if (customMsg) {
                        showFieldError(this, customMsg);
                    }
                }
                
                // Special handling: if account number changes, revalidate confirm field
                if (this.name === 'account_number') {
                    const confirmField = document.getElementById('confirm_account_number');
                    if (confirmField && confirmField.value && touchedFields.has('confirm_account_number')) {
                        clearFieldError(confirmField);
                        const confirmMsg = customValidation(confirmField);
                        if (confirmMsg) {
                            showFieldError(confirmField, confirmMsg);
                        }
                        // If no error, the success state is already handled in customValidation
                    }
                }
            });
            field.addEventListener('blur', function() {
                touchedFields.add(this.name);
                if (!this.value) {
                    // Only show required error for required fields
                    if (this.hasAttribute('required')) {
                        showFieldError(this, 'This field is required.');
                    }
                } else {
                    const customMsg = customValidation(this);
                    if (customMsg) {
                        showFieldError(this, customMsg);
                    }
                }
            });
            field.addEventListener('change', function() {
                // For select fields, also track on change event
                touchedFields.add(this.name);

                // For file inputs, validate immediately when a file is chosen
                if (this.type === 'file') {
                    clearFieldError(this);

                    // Required check: no file selected
                    if (this.hasAttribute('required') && (!this.files || this.files.length === 0)) {
                        showFieldError(this, 'This field is required.');
                        return;
                    }

                    const customMsg = customValidation(this);
                    if (customMsg) {
                        showFieldError(this, customMsg);
                    } else {
                        clearFieldError(this);
                    }
                }
            });

            // Clear any existing errors and ensure no validation shows by default
            clearFieldError(field);
            // Remove from touched fields to prevent showing errors on page load
            touchedFields.delete(field.name);
        });
    }
    // PAN and Voter ID uppercase logic
    function setupUppercaseInputs() {
        var panInput = document.getElementById('pan_number');
        var voterInput = document.getElementById('voter_number');
        if (panInput) {
            panInput.addEventListener('input', function() {
                this.value = this.value.toUpperCase();
            });
        }
        if (voterInput) {
            voterInput.addEventListener('input', function() {
                this.value = this.value.toUpperCase();
            });
        }
    }
    
    // Name field title case formatting
    function setupNameFormatting() {
        var nameInput = document.getElementById('full_name');
        if (nameInput) {
            nameInput.addEventListener('input', function() {
                // Convert to title case (first letter of each word capitalized)
                this.value = this.value.replace(/\w\S*/g, function(txt) {
                    return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
                });
            });
            
            // Also format on blur for better UX
            nameInput.addEventListener('blur', function() {
                if (this.value) {
                    this.value = this.value.replace(/\w\S*/g, function(txt) {
                        return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
                    });
                }
            });
        }
    }
    
    // Aadhaar number formatting with spaces
    function setupAadhaarFormatting() {
        var aadhaarInput = document.getElementById('adhar_number');
        if (aadhaarInput) {
            aadhaarInput.addEventListener('input', function() {
                // Remove all non-digit characters
                let value = this.value.replace(/\D/g, '');
                
                // Limit to 12 digits
                value = value.slice(0, 12);
                
                // Add spaces after every 4 digits
                let formattedValue = '';
                if (value.length > 0) {
                    formattedValue = value.match(/.{1,4}/g).join(' ');
                }
                
                this.value = formattedValue;
            });
            
            // Handle paste events
            aadhaarInput.addEventListener('paste', function(e) {
                e.preventDefault();
                const pastedText = (e.clipboardData || window.clipboardData).getData('text');
                // Remove non-digit characters and paste
                const cleanValue = pastedText.replace(/\D/g, '');
                this.value = cleanValue;
                this.dispatchEvent(new Event('input'));
            });
        }
    }
    // Initialize flatpickr datepicker for all .datepicker fields

    // ...existing code...
    function setupDatepicker() {
        if (!window.flatpickr) return;

        const today = new Date();

        // Minimal mobile detection for layout decisions (we still force flatpickr)
        const isTouchCapable = (() => {
            try {
                return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
                    || ('ontouchstart' in window) || (navigator.maxTouchPoints && navigator.maxTouchPoints > 0);
            } catch (e) {
                return false;
            }
        })();

        document.querySelectorAll('.datepicker').forEach(function(el) {
            // Ensure input is text so browser won't show native date UI
            try { if (el.type && el.type.toLowerCase() === 'date') el.type = 'text'; } catch (e) {}

            // Always append to body so we can position relative to viewport
            const appendTo = document.body;

            const instance = flatpickr(el, {
                mode: 'single',
                // Underlying value submitted to backend (DB-friendly)
                dateFormat: 'Y-m-d',
                // What the user sees and types in the UI (dd-mm-yyyy)
                altInput: true,
                altFormat: 'd-m-Y',
                // Allow any past date up to today; only future dates are disabled
                maxDate: today,

                allowInput: true,
                clickOpens: true,
                // Force flatpickr UI on mobile (do not use native)
                disableMobile: true,
                appendTo: appendTo,
                static: false,
                position: 'below',
                // Ensure calendar is clickable/touchable above other elements
                onOpen(_, __, fp) {
                    const cal = fp.calendarContainer;
                    if (!cal) return;
                    cal.style.zIndex = '99999';
                    cal.style.transform = 'none';

                    // Align under input for touch devices using fixed positioning
                    if (isTouchCapable) {
                        cal.style.position = 'fixed';

                        const inputRect = el.getBoundingClientRect();
                        const vpW = window.innerWidth || document.documentElement.clientWidth;
                        const vpH = window.innerHeight || document.documentElement.clientHeight;

                        // desired width equals input width but not exceed viewport minus margins
                        const desiredWidth = Math.min(Math.max(300, el.offsetWidth || inputRect.width), vpW - 16);
                        cal.style.width = desiredWidth + 'px';

                        // compute left (clamped to viewport with 8px margin)
                        let left = Math.round(inputRect.left);
                        if (left + desiredWidth > vpW - 8) left = Math.max(8, vpW - 8 - desiredWidth);
                        if (left < 8) left = 8;

                        // compute top under input; if not enough space, place above
                        const topBelow = Math.round(inputRect.bottom);
                        const calH = cal.offsetHeight || 320;
                        let top = topBelow;
                        if (topBelow + calH > vpH - 8 && (inputRect.top - calH) > 8) {
                            top = Math.round(inputRect.top - calH);
                        }

                        cal.style.left = left + 'px';
                        cal.style.top = top + 'px';
                    } else {
                        // Desktop: let flatpickr handle placement but ensure visible z-index
                        cal.style.position = '';
                        cal.style.left = '';
                        cal.style.top = '';
                        cal.style.width = '';
                    }
                },
                onChange(selectedDates, dateStr, fp) {
                    // Keep hidden value in ISO format and run validation, including age limits
                    el.value = dateStr || '';

                    if (el.id === 'date_of_birth') {
                        const visibleInput = fp.altInput || el;
                        // Ensure visible value stays in DD-MM-YYYY even when picked from calendar
                        if (fp.altInput && fp.altInput.value) {
                            visibleInput.value = fp.altInput.value;
                        }

                        if (el.value) {
                            // Mark as touched so showFieldError will display the message
                            touchedFields.add(el.name);
                            const msg = customValidation(el);
                            if (msg) {
                                showFieldError(el, msg);
                                visibleInput.classList.add('border-red-500');
                            } else {
                                clearFieldError(el);
                                visibleInput.classList.remove('border-red-500');
                            }
                        }
                    }
                },
                onReady(_, __, fp) {
                    // Reposition calendar on orientation/resize if open
                    const reposition = () => {
                        if (fp.isOpen) {
                            // trigger open to recalc and re-run onOpen
                            fp.open();
                        }
                    };
                    window.addEventListener('orientationchange', reposition, { passive: true });
                    window.addEventListener('resize', reposition, { passive: true });

                    // cleanup when instance destroyed
                    const origDestroy = fp.destroy.bind(fp);
                    fp.destroy = function() {
                        window.removeEventListener('orientationchange', reposition);
                        window.removeEventListener('resize', reposition);
                        origDestroy();
                    };
                }
            });

            // Use the visible input for typing (altInput when enabled)
            const inputEl = instance.altInput || el;

            // Input mask and validation wiring specifically for DOB field: DD-MM-YYYY
            if (el.id === 'date_of_birth') {
                inputEl.addEventListener('input', function(e) {
                    let v = this.value.replace(/[^0-9]/g, ''); // keep digits only

                    // limit to 8 digits (DDMMYYYY)
                    if (v.length > 8) v = v.slice(0, 8);

                    let formatted = '';
                    if (v.length <= 2) {
                        formatted = v; // D, DD
                    } else if (v.length <= 4) {
                        formatted = v.slice(0, 2) + '-' + v.slice(2); // DD-MM
                    } else {
                        // DD-MM-YYYY (partial year also supported)
                        formatted = v.slice(0, 2) + '-' + v.slice(2, 4) + '-' + v.slice(4);
                    }

                    this.value = formatted;

                    // When full date is entered (DD-MM-YYYY), sync hidden field and run validation
                    if (formatted.length === 10) {
                        const [dd, mm, yyyy] = formatted.split('-');
                        const day = parseInt(dd, 10);
                        const month = parseInt(mm, 10);
                        const year = parseInt(yyyy, 10);

                        if (!isNaN(day) && !isNaN(month) && !isNaN(year) && day >= 1 && day <= 31 && month >= 1 && month <= 12) {
                            // Set underlying input value in ISO format for backend & validation
                            el.value = `${year.toString().padStart(4, '0')}-${mm}-${dd}`;

                            // Mark as touched so showFieldError will display the message
                            touchedFields.add(el.name);
                            const msg = customValidation(el);

                            if (msg) {
                                // Show error message and red border on visible DOB input
                                showFieldError(el, msg);
                                inputEl.classList.add('border-red-500');
                            } else {
                                clearFieldError(el);
                                inputEl.classList.remove('border-red-500');
                            }
                        } else {
                            // Structurally invalid date: keep value but mark as invalid
                            el.value = '';
                            showFieldError(el, 'Please enter a valid date of birth.');
                            inputEl.classList.add('border-red-500');
                        }
                    } else {
                        // Incomplete date while typing: don't wipe what user typed, just clear backend value
                        el.value = '';
                        inputEl.classList.remove('border-red-500');
                        // Do not clear the error text here; let blur/submit logic decide
                    }
                });
            }

            // keep existing input restrictions on the field the user types into
            inputEl.addEventListener('keypress', function(e) {
                const char = String.fromCharCode(e.which || e.keyCode);
                if (!/[0-9\-]/.test(char)) e.preventDefault();
            });
            inputEl.addEventListener('paste', function(e) {
                const pasteData = (e.clipboardData || window.clipboardData).getData('text');
                if (!/^[0-9\-]*$/.test(pasteData)) e.preventDefault();
            });
        });
    }
// ...existing code...
    // function setupDatepicker() {
    //     if (window.flatpickr) {
    //       // Calculate the date 21 years ago from today
    //       const today = new Date();
    //       const maxDate = new Date(
    //         today.getFullYear() - 21,
    //         today.getMonth(),
    //         today.getDate()
    //       );
    
    //       document.querySelectorAll(".datepicker").forEach(function (el) {
    //         flatpickr(el, {
    //           mode: "single",
    //           dateFormat: "Y-m-d",
    //           maxDate: maxDate,
    //           allowInput: true,
    //         });
    
    //         // Restrict input to numbers, hyphen, and slash only
    //         el.addEventListener("keypress", function (e) {
    //           const char = String.fromCharCode(e.which);
    //           if (!/[0-9\-\/]/.test(char)) {
    //             e.preventDefault();
    //           }
    //         });
    
    //         // Prevent pasting invalid characters
    //         el.addEventListener("paste", function (e) {
    //           const pasteData = (e.clipboardData || window.clipboardData).getData(
    //             "text"
    //           );
    //           if (!/^[0-9\-\/]*$/.test(pasteData)) {
    //             e.preventDefault();
    //           }
    //         });
    //       });
    //     }
    //   }
      
    // Toggle current address section and validation based on checkbox
    function setupCurrentAddressToggle() {
        var checkbox = document.getElementById('same-address');
        if (!checkbox) return;
        
        checkbox.addEventListener('change', function() {
            toggleCurrentAddress(this);
        });  
        
        // Initial state
        toggleCurrentAddress(checkbox);
    }
    
    // Function to update current address fields with permanent address values
    function updateCurrentAddress() {
        const sameAddressCheckbox = document.getElementById('same-address');
        if (sameAddressCheckbox && sameAddressCheckbox.checked) {
            const addressLine1 = document.getElementById('address_line_1');
            const addressLine2 = document.getElementById('address_line_2');
            const landmark = document.getElementById('landmark');
            const postOffice = document.getElementById('post_office');
            const cityOrTown = document.getElementById('city_or_town');
            const district = document.getElementById('district');
            const state = document.getElementById('state');
            const country = document.getElementById('country');
            const postCode = document.getElementById('post_code');
            
            const currentAddressLine1 = document.getElementById('current_address_line_1');
            const currentAddressLine2 = document.getElementById('current_address_line_2');
            const currentLandmark = document.getElementById('current_landmark');
            const currentPostOffice = document.getElementById('current_post_office');
            const currentCityOrTown = document.getElementById('current_city_or_town');
            const currentDistrict = document.getElementById('current_district');
            const currentState = document.getElementById('current_state');
            const currentCountry = document.getElementById('current_country');
            const currentPostCode = document.getElementById('current_post_code');
            
            if (addressLine1 && currentAddressLine1) currentAddressLine1.value = addressLine1.value;
            if (addressLine2 && currentAddressLine2) currentAddressLine2.value = addressLine2.value;
            if (landmark && currentLandmark) currentLandmark.value = landmark.value;
            if (postOffice && currentPostOffice) currentPostOffice.value = postOffice.value;
            if (cityOrTown && currentCityOrTown) currentCityOrTown.value = cityOrTown.value;
            if (district && currentDistrict) currentDistrict.value = district.value;
            if (state && currentState) currentState.value = state.value;
            if (country && currentCountry) currentCountry.value = country.value;
            if (postCode && currentPostCode) currentPostCode.value = postCode.value;
            
            // Reset manually edited flags when copying from permanent address
            const currentFields = [currentPostOffice, currentCityOrTown, currentDistrict, currentState];
            currentFields.forEach(field => {
                if (field) {
                    delete field.dataset.manuallyEdited;
                }
            });
            
            // Clear residential proof fields when same address is checked
            const residentialProofTypeSelect = document.getElementById('residential_proof_type');
            const residentialProofFileInput = document.getElementById('residential_proof_file');
            
            if (residentialProofTypeSelect) {
                residentialProofTypeSelect.selectedIndex = 0;
                clearFieldError(residentialProofTypeSelect);
            }
            
            if (residentialProofFileInput) {
                residentialProofFileInput.value = '';
                clearFieldError(residentialProofFileInput);
            }
        }
    }
    
    // Make updateCurrentAddress available globally
    window.updateCurrentAddress = updateCurrentAddress;
    
    // Toggle current address section and handle address copying
    function toggleCurrentAddress(checkbox) {
        const currentAddressSection = document.getElementById('current-address-section');
        const residentialProofSection = document.querySelector('.residential-proof-section');
        
        if (checkbox.checked) {
            currentAddressSection.classList.add('hidden');
            if (residentialProofSection) {
                residentialProofSection.classList.add('hidden');
            }
            updateCurrentAddress();
            // Clear errors for current address fields and remove required attribute
            ['current_address_line_1', 'current_state', 'current_post_code', 'current_city_or_town', 'current_district', 'residential_proof_type', 'residential_proof_file'].forEach(id => {
                const field = document.getElementById(id);
                if (field) {
                    clearFieldError(field);
                    // Remove required attribute when same address is checked to prevent browser validation on hidden fields
                    field.removeAttribute('required');
                }
            });
        } else {
            currentAddressSection.classList.remove('hidden');
            if (residentialProofSection) {
                residentialProofSection.classList.remove('hidden');
            }
            // Clear any existing errors but don't trigger validation yet
            ['current_address_line_1', 'current_state', 'current_post_code', 'current_city_or_town', 'current_district', 'residential_proof_type', 'residential_proof_file'].forEach(id => {
                const field = document.getElementById(id);
                if (field) {
                    clearFieldError(field);
                }
            });
            
            // Re-add required attribute for fields that should be required when same address is not checked
            const requiredFields = ['current_address_line_1', 'current_state', 'current_post_code', 'current_city_or_town', 'current_district', 'residential_proof_type', 'residential_proof_file'];
            requiredFields.forEach(id => {
                const field = document.getElementById(id);
                if (field) {
                    // Re-add required attribute for fields that are originally required
                    const originalRequired = field.getAttribute('data-original-required');
                    if (originalRequired === 'true' || field.getAttribute('required') !== null) {
                        field.setAttribute('required', 'required');
                    }
                }
            });
        }
    }
    
    // Add event listeners to permanent address fields to update current address when checkbox is checked
    function setupAddressFieldListeners() {
        const sameAddressCheckbox = document.getElementById('same-address');
        if (!sameAddressCheckbox) return;
        
        const permanentAddressFields = [
            'address_line_1', 'address_line_2', 'landmark', 'post_office', 
            'city_or_town', 'district', 'state', 'country', 'post_code'
        ];
        
        permanentAddressFields.forEach(fieldName => {
            const field = document.getElementById(fieldName);
            if (field) {
                field.addEventListener('input', function() {
                    if (sameAddressCheckbox.checked) {
                        updateCurrentAddress();
                    }
                });
            }
        });
    }
    
    // Make toggleCurrentAddress available globally
    window.toggleCurrentAddress = toggleCurrentAddress;
    
    // Preview Modal Functions
    function showPreviewModal() {
        const modal = document.getElementById('preview-modal');
        if (!modal) return;
        
        // Ensure draft checkbox reflects whether this form was loaded
        // from a draft (via the draft modal). Merely *having* drafts
        // should not auto-check this for a fresh application.
        if (window.CURRENT_FORM_FROM_DRAFT) {
            const draftCheckbox = document.getElementById('save-draft-checkbox');
            if (draftCheckbox) {
                draftCheckbox.checked = true;
            }
        }

        // Populate preview fields with form data
        populatePreviewFields();
        
        // Show the modal
        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden'; // Prevent background scrolling
    }
    
    function hidePreviewModal() {
        const modal = document.getElementById('preview-modal');
        if (!modal) return;
        
        modal.classList.add('hidden');
        document.body.style.overflow = ''; // Restore scrolling
    }
    
    function populatePreviewFields() {
        const form = document.getElementById('loan-application-form');
        if (!form) return;

        // Get all form fields
        const formData = new FormData(form);

        // Handle same address checkbox
        const sameAddressCheckbox = document.getElementById('same-address');
        if (sameAddressCheckbox && sameAddressCheckbox.checked) {
            // Copy permanent address to current address fields
            formData.set('current_address_line_1', formData.get('address_line_1'));
            formData.set('current_address_line_2', formData.get('address_line_2'));
            formData.set('current_landmark', formData.get('landmark'));
            formData.set('current_post_office', formData.get('post_office'));
            formData.set('current_city_or_town', formData.get('city_or_town'));
            formData.set('current_district', formData.get('district'));
            formData.set('current_state', formData.get('state'));
            formData.set('current_country', formData.get('country'));
            formData.set('current_post_code', formData.get('post_code'));

            // Clear residential proof fields when same address is checked
            formData.delete('residential_proof_type');
            formData.delete('residential_proof_file');

            // Clear the file input field
            const residentialProofFileInput = document.getElementById('residential_proof_file');
            if (residentialProofFileInput) {
                residentialProofFileInput.value = '';
            }

            // Clear the select field
            const residentialProofTypeSelect = document.getElementById('residential_proof_type');
            if (residentialProofTypeSelect) {
                residentialProofTypeSelect.selectedIndex = 0;
            }
        }

        // Populate all preview fields
        for (const [fieldName, value] of formData.entries()) {
            const previewField = document.getElementById('preview_' + fieldName);
            if (!previewField) continue;

            if (
                fieldName.includes('_proof') ||
                fieldName === 'photo' ||
                fieldName === 'signature' ||
                fieldName === 'collaterol' ||
                fieldName === 'residential_proof_file' ||
                fieldName === 'pan_card_document'
            ) {
                const fileInput = document.getElementById(fieldName);
                if (fileInput && fileInput.type === 'file' && fileInput.files && fileInput.files.length > 0) {
                    previewField.value = fileInput.files[0].name;
                } else {
                    previewField.value = 'No file selected';
                }
            } else {
                previewField.value = value || '';
            }
        }

        // Handle select fields that might not be captured by FormData
        const selectFields = ['loan_category', 'tenure_months', 'gender', 'residential_proof_type'];
        selectFields.forEach(fieldName => {
            const field = document.getElementById(fieldName);
            const previewField = document.getElementById('preview_' + fieldName);
            if (field && previewField) {
                const selectedOption = field.options[field.selectedIndex];
                previewField.value = selectedOption ? selectedOption.text : '';
            }
        });

        // Hide product-related sections if no data is found
        if (sameAddressCheckbox && sameAddressCheckbox.checked) {
            hideCurrentAddressSections();
        }else{
            hideCurrentAddressSections('flex');
        }
        hideEmptyProductSections();
    }
    
    function hideCurrentAddressSections(display = "none") {
        // Check processing fees section - hide entire section if no fees
        const currentAddressLine1Field = document.getElementById('preview_current_address_line_1');
        console.log('******************1')
        if (currentAddressLine1Field) {
            // First check if processing fee field has data
            const currentAddressSection = currentAddressLine1Field.parentElement;
            console.log('******************2')
            if(currentAddressSection) {
                const currentAddressContainer = currentAddressSection.parentElement;
                console.log('******************3')
                if(currentAddressContainer) {
                    currentAddressContainer.style.display = display;
                    const currentAddressSectionHR = currentAddressContainer.previousElementSibling;
                    console.log('******************4')
                    if (currentAddressSectionHR) {
                        currentAddressSectionHR.style.display = display;
                    }
                    const currentAddressSectionDIV = currentAddressSectionHR.previousElementSibling;
                    console.log('******************5')
                    if (currentAddressSectionDIV) {
                        currentAddressSectionDIV.style.display = display == 'flex' ? 'block' : display;
                    }
                }
            }
        }
    }
    
    function hideEmptyProductSections() {
        // Hide/show individual product field containers based on data
        const productContainers = [
            'preview_selected_product',
            'preview_loan_percentage_container',
            'preview_sale_price_container', 
            'preview_processing_fee_container',
            'preview_down_payment_container',
            'preview_total_loan_amount_container',
            'preview_product_main_category_container',
            'preview_product_subcategory_container',
            'preview_product_type_container'
        ];
        
        productContainers.forEach(containerId => {
            let container = document.getElementById(containerId);
            if (!containerId.endsWith("_container")) {
                container = container.parentElement;
            }
            if (container) {
                const input = container.querySelector('input');
                if (input && input.value && input.value.trim() !== '') {
                    container.style.display = 'block';
                } else {
                    container.style.display = 'none';
                }
            }
        });
        
        // Check processing fees section - hide entire section if no fees
        const processingFeesContainer = document.getElementById('preview_processing_fees_container');
        if (processingFeesContainer) {
            // First check if processing fee field has data
            const processingFeeField = document.getElementById('preview_processing_fee');
            let hasProcessingFee = false;
            
            if (processingFeeField && processingFeeField.value && processingFeeField.value.trim() !== '') {
                hasProcessingFee = true;
            }
            
            // Also check Alpine data for additional fees
            const modal = document.getElementById('preview-modal');
            let hasAlpineFees = false;
            
            if (modal && window.Alpine) {
                try {
                    // Try to get Alpine data for the modal
                    const alpineData = window.Alpine.$data(modal);
                    if (alpineData && alpineData.processingFees && alpineData.processingFees.length > 0) {
                        hasAlpineFees = true;
                    }
                } catch (e) {
                    // Fallback to field checking if Alpine access fails
                }
            }
            
            // Show container only if there are any processing fees
            if (hasProcessingFee || hasAlpineFees) {
                processingFeesContainer.style.display = 'block';
            } else {
                processingFeesContainer.style.display = 'none';
            }


            const processingFeesSectionHR = processingFeesContainer.previousElementSibling;
            if (processingFeesSectionHR) {
                // Show entire section only if there are any processing fees
                if (hasProcessingFee || hasAlpineFees) {
                    processingFeesSectionHR.style.display = 'block';
                } else {
                    processingFeesSectionHR.style.display = 'none';
                }
            }


            const processingFeesSectionDIV = processingFeesSectionHR.previousElementSibling;
            if (processingFeesSectionDIV) {
                // Show entire section only if there are any processing fees
                if (hasProcessingFee || hasAlpineFees) {
                    processingFeesSectionDIV.style.display = 'block';
                } else {
                    processingFeesSectionDIV.style.display = 'none';
                }
            }
        }
    }
    
    function setupPreviewModal() {
        // Close modal when clicking the X button
        const closeBtn = document.getElementById('close-preview-x');
        if (closeBtn) {
            closeBtn.addEventListener('click', hidePreviewModal);
        }
        
        // Close modal when clicking the Cancel button
        const cancelBtn = document.getElementById('close-preview');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', hidePreviewModal);
        }
        
        // Submit form when clicking the Submit button
        const submitBtn = document.getElementById('submit-preview');
        if (submitBtn) {
            submitBtn.addEventListener('click', function() {
                // Trigger form submission 
                console.log(typeof confirmSubmit);
                if (typeof confirmSubmit === 'function') {
                    // Call confirmSubmit function from new-application-cards.html
                    console.log('calling........................');
                    confirmSubmit();
                    console.log('called........................');
                } else {
                    const form = document.getElementById('loan-application-form');
                    console.log('form  :  ', form);
                    if (form) {
                        console.log('calling form submit........................');
                        // Reset isSubmitting to allow the event to be processed
                        if (typeof isSubmitting !== 'undefined') {
                            isSubmitting = false;
                        }
                        form.dispatchEvent(new Event('submit'));
                        console.log('called form submit........................');
                    } 
                }
                console.log('Hiding preview ...........................')
                hidePreviewModal();
            });
        }
        
        // Close modal when clicking outside
        const modal = document.getElementById('preview-modal');
        if (modal) {
            modal.addEventListener('click', function(e) {
                if (e.target === modal) {
                    hidePreviewModal();
                }
            });
        }
        
        // Close modal with Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                hidePreviewModal();
            }
        });
    }
        
    // Make functions available globally
    window.showPreviewModal = showPreviewModal;
    window.hidePreviewModal = hidePreviewModal;
    
    // Validate all required fields and return true if all valid, false otherwise
    function validateAllFields() {
        const form = document.getElementById('loan-application-form');
        if (!form) return false;
        let valid = true;
        
        // Only show all errors during form submission
        window._showAllErrors = true;
        
        // Check account number validation first and show popup if there are errors
        const accountNumberField = document.getElementById('account_number');
        const confirmAccountNumberField = document.getElementById('confirm_account_number');
        
        if (accountNumberField) {
            // Clear any existing errors first
            clearFieldError(accountNumberField);
            
            // Only validate if value is provided (optional field)
            if (accountNumberField.value.trim()) {
                // Run custom validation on account number
                const accountErrorMsg = customValidation(accountNumberField);
                if (accountErrorMsg) {
                    showFieldError(accountNumberField, accountErrorMsg);
                    valid = false;
                    showAccountNumberErrorPopup(accountErrorMsg);
                }
            }
        }
        
        // Check confirm account number if account number is valid
        if (valid && confirmAccountNumberField) {
            clearFieldError(confirmAccountNumberField);
            
            // Only validate if value is provided (optional field)
            if (confirmAccountNumberField.value.trim()) {
                // Run custom validation on confirm account number
                const confirmErrorMsg = customValidation(confirmAccountNumberField);
                if (confirmErrorMsg) {
                    showFieldError(confirmAccountNumberField, confirmErrorMsg);
                    valid = false;
                    showAccountNumberErrorPopup(confirmErrorMsg);
                }
            }
        }
        
        // If account number validation failed, return early
        if (!valid) {
            setTimeout(() => { window._showAllErrors = false; }, 100);
            return false;
        }
        
        const requiredFields = form.querySelectorAll('input[required], select[required]');
        requiredFields.forEach(field => {
            // For current address fields, skip validation if checkbox is checked
            const sameAddressCheckbox = document.getElementById('same-address');
            const isCurrentField = ['current_address_line_1', 'current_state', 'current_post_code', 'current_city_or_town', 'current_district', 'residential_proof_type', 'residential_proof_file'].includes(field.name);
            
            if (isCurrentField && sameAddressCheckbox && sameAddressCheckbox.checked) {
                clearFieldError(field);
                return;
            }
            
            clearFieldError(field);
            if (!field.value) {
                showFieldError(field, 'This field is required.');
                valid = false;
            } else {
                const customMsg = customValidation(field);
                if (customMsg) {
                    showFieldError(field, customMsg);
                    valid = false;
                }
            }
        });
        
        // Reset the flag after validation
        setTimeout(() => { window._showAllErrors = false; }, 100);
        return valid;
    }
    
    // Intercept Continue button to validate before showing preview modal
    window.addEventListener('DOMContentLoaded', async function() {
        // Initialize clean state - no validation errors on page load
        function initializeCleanState() {
            // Clear all error messages
            document.querySelectorAll('[id^="error-"]').forEach(el => el.textContent = '');
            // Remove red borders
            document.querySelectorAll('.border-red-500').forEach(el => el.classList.remove('border-red-500'));
            // Clear touched fields to prevent showing errors by default
            touchedFields.clear();
            // Reset the show all errors flag
            window._showAllErrors = false;
        }
        
        // Initialize clean state
        initializeCleanState();
        
        // Store original required attributes for residential proof fields
        const residentialProofFields = ['residential_proof_type', 'residential_proof_file'];
        residentialProofFields.forEach(id => {
            const field = document.getElementById(id);
            if (field && field.hasAttribute('required')) {
                field.setAttribute('data-original-required', 'true');
            }
        });
        
        attachInstantValidation();
        setupUppercaseInputs();
        setupNameFormatting();
        setupAadhaarFormatting();
        setupDatepicker();
        setupCurrentAddressToggle();
        setupPreviewModal();
        
        // Add event listeners to permanent address fields to update current address when checkbox is checked
        const permanentAddressFields = ['address_line_1', 'address_line_2', 'landmark', 'post_office', 'city_or_town', 'district', 'state', 'country', 'post_code'];
        permanentAddressFields.forEach(fieldName => {
            const field = document.getElementById(fieldName);
            if (field) {
                field.addEventListener('input', function() {
                    const sameAddressCheckbox = document.getElementById('same-address');
                    if (sameAddressCheckbox && sameAddressCheckbox.checked) {
                        updateCurrentAddress();
                    }
                });
            }
        });
        
        // Add event listeners to current address fields to prevent auto-fill when manually editing
        const currentAddressFields = ['current_post_office', 'current_city_or_town', 'current_district', 'current_state'];
        currentAddressFields.forEach(fieldName => {
            const field = document.getElementById(fieldName);
            if (field) {
                field.addEventListener('input', function() {
                    // If user manually edits a field, don't let auto-fill override it
                    this.dataset.manuallyEdited = 'true';
                    this.classList.remove('auto-filled');
                });
            }
        });
        
        // Add event listeners to permanent address fields to remove auto-filled class when manually edited
        const permanentAddressFieldsForAutoFill = ['post_office', 'city_or_town', 'district', 'state'];
        permanentAddressFieldsForAutoFill.forEach(fieldName => {
            const field = document.getElementById(fieldName);
            if (field) {
                field.addEventListener('input', function() {
                    this.classList.remove('auto-filled');
                });
            }
        });
        
        var continueBtn = document.getElementById('continue-btn');
        var form = document.getElementById('loan-application-form');
        if (continueBtn && form) {
            continueBtn.addEventListener('click', function(e) {
                console.log("Cotinue Clicked");
                e.preventDefault();
                if (!validateAllFields()) {
                    console.log("Validation failed");
                    // Optionally scroll to first error
                    const firstError = form.querySelector('.border-red-500');
                    if (firstError) firstError.scrollIntoView({behavior: 'smooth', block: 'center'});
                    return false;
                }
                // If valid, show the preview modal
                showPreviewModal();
            });
        }
        
        // Save as Draft checkbox logic: if checked on submit, save draft
        const saveDraftCheckbox = document.getElementById('save-draft-checkbox');
        const submitPreviewBtn = document.getElementById('submit-preview');
        let lastDraftChecked = saveDraftCheckbox ? saveDraftCheckbox.checked : false;
        if (submitPreviewBtn && saveDraftCheckbox) {
            // Use a flag to prevent double toast on modal open
            saveDraftCheckbox.addEventListener('change', async function() {
                if (saveDraftCheckbox.checked) {
                    // Ensure EMI is up to date before capturing form data
                    if (window.updateEMI) {
                        try { window.updateEMI(); } catch (e) { console.warn('updateEMI() failed before draft save', e); }
                    }
                    const form = document.getElementById('loan-application-form');
                    const formData = new FormData(form);
                    // localStorage.setItem('loanApplicationDraft', JSON.stringify(Object.fromEntries(formData.entries())));
                    try {
                        await callDraftAPI('save-draft', 'POST', {
                            user_id: window.CURRENT_USER_ID,
                            user_type: window.CURRENT_USER_TYPE ? window.CURRENT_USER_TYPE.replace(/\/$/, '') : window.CURRENT_USER_TYPE,
                            draft_data: Object.fromEntries(formData.entries())
                        });
                    } catch (error) {
                        console.error('Failed to save draft:', error);
                        showToast('Failed to save draft. Please try again.', 'error');
                    }
                    // Only show toast if this is a real user change (not just modal open)
                    if (!lastDraftChecked) {
                        showToast('Application saved as draft! You can resume your application later from this device.', 'success');
                    }
                } else {
                    try {
                        await callDraftAPI('delete-draft', 'DELETE', {
                            user_id: window.CURRENT_USER_ID,
                            user_type: window.CURRENT_USER_TYPE ? window.CURRENT_USER_TYPE.replace(/\/$/, '') : window.CURRENT_USER_TYPE
                        });
                    } catch (error) {
                        console.error('Failed to delete draft:', error);
                    }
                    // localStorage.removeItem('loanApplicationDraft');
                    // No toast when unchecked
                }
                lastDraftChecked = saveDraftCheckbox.checked;
            });
        }
        
        try {
            const draftResult = await callDraftAPI('get-draft', 'GET', {
                user_id: window.CURRENT_USER_ID,
                user_type: window.CURRENT_USER_TYPE ? window.CURRENT_USER_TYPE.replace(/\/$/, '') : window.CURRENT_USER_TYPE
            });

            // Do NOT prefill the form automatically anymore. We only keep
            // the draft metadata so the preview checkbox and draft modal
            // can reflect that a draft exists and show its details.
            if (draftResult.draft_data) {
                window.HAS_LOAN_DRAFT = true;
                window.LAST_LOAN_DRAFT_RESULT = draftResult;
            }
        } catch (error) {
            console.error('Failed to load draft:', error);
        }
        
        // Wire up draft icon modal open/close
        const draftIconBtn = document.getElementById('draft-icon-button');
        const draftModal = document.getElementById('draft-info-modal');
        const draftModalBody = document.getElementById('draft-modal-body');
        const draftModalClose = document.getElementById('draft-modal-close');
        const draftModalCloseFooter = document.getElementById('draft-modal-close-footer');
        const draftModalContinue = document.getElementById('draft-modal-continue');

        function hideDraftModal() {
            if (draftModal) {
                draftModal.classList.add('hidden');
            }
            document.body.style.overflow = '';
        }

        async function showDraftModal() {
            if (!draftModal || !draftModalBody) return;

            // When opening, ensure Continue is disabled until a draft is selected
            if (draftModalContinue) {
                draftModalContinue.disabled = true;
                draftModalContinue.classList.add('opacity-50', 'cursor-not-allowed');
            }

            draftModalBody.innerHTML = '<p class="text-gray-500 dark:text-gray-400 text-sm">Loading draft details...</p>';

            let result = window.LAST_LOAN_DRAFT_RESULT;
            if (!result) {
            try {
                result = await callDraftAPI('get-draft', 'GET', {
                    user_id: window.CURRENT_USER_ID,
                    user_type: window.CURRENT_USER_TYPE ? window.CURRENT_USER_TYPE.replace(/\/$/, '') : window.CURRENT_USER_TYPE
                });
                window.LAST_LOAN_DRAFT_RESULT = result;
            } catch (err) {
                console.error('Failed to load draft for modal:', err);
                draftModalBody.innerHTML = '<p class="text-red-600 text-sm">Failed to load draft details.</p>';
                draftModal.classList.remove('hidden');
                document.body.style.overflow = 'hidden';
                return;
                }
            }

            if (!result || !result.draft_data) {
                draftModalBody.innerHTML = '<p class="text-gray-600 dark:text-gray-300 text-sm">No draft found for this user.</p>';
                if (draftModalContinue) {
                    draftModalContinue.disabled = true;
                    draftModalContinue.classList.add('opacity-50', 'cursor-not-allowed');
                }
            } else {
                const raw = result.draft_data;
                const drafts = Array.isArray(raw) ? raw : (raw ? [raw] : []);
                const safe = (v) => (v === undefined || v === null || v === '' ? '-' : String(v));

                if (!drafts.length) {
                    draftModalBody.innerHTML = '<p class="text-gray-600 dark:text-gray-300 text-sm">No draft found for this user.</p>';
                    if (draftModalContinue) {
                        draftModalContinue.disabled = true;
                        draftModalContinue.classList.add('opacity-50', 'cursor-not-allowed');
                    }
                } else {
                    // Store list globally so Continue button can use it
                    window._CURRENT_DRAFT_LIST = drafts;

                    draftModalBody.innerHTML = `
                        <div class="space-y-2">
                            <p class="text-xs text-gray-600 dark:text-gray-300 mb-2">
                                Select a draft to load into the form:
                            </p>
                            <ul class="space-y-1 text-xs">
                                ${drafts.map((d, idx) => `
                                    <li data-draft-index="${idx}" data-draft-id="${safe(d._draft_id || '')}">
                                        <div class="flex items-start gap-2 p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-800">
                                            <label class="flex-1 flex items-start gap-2 cursor-pointer">
                                                <input type="radio" name="draft-choice" value="${idx}" class="mt-0.5">
                                                <div class="flex-1 space-y-0.5">
                                                    <div class="font-semibold text-gray-800 dark:text-gray-100">
                                                        ${safe(d.full_name)}
                                                    </div>
                                                    <div class="text-gray-500 dark:text-gray-400">
                                                        Aadhaar: ${safe(d.adhar_number)} &nbsp; PAN: ${safe(d.pan_number)}
                                                    </div>
                                                    <div class="text-gray-500 dark:text-gray-400">
                                                        Loan Amount: ${safe(d.loan_amount)}
                                                    </div>
                                                </div>
                                            </label>
                                            <button type="button" class="ml-2 text-[11px] text-red-500 hover:text-red-600 draft-delete-btn" title="Delete draft">
                                                <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none">
                                                  <path d="M4 6H20M16 6L15.7294 5.18807C15.4671 4.40125 15.3359 4.00784 15.0927 3.71698C14.8779 3.46013 14.6021 3.26132 14.2905 3.13878C13.9376 3 13.523 3 12.6936 3H11.3064C10.477 3 10.0624 3 9.70951 3.13878C9.39792 3.26132 9.12208 3.46013 8.90729 3.71698C8.66405 4.00784 8.53292 4.40125 8.27064 5.18807L8 6M18 6V16.2C18 17.8802 18 18.7202 17.673 19.362C17.3854 19.9265 16.9265 20.3854 16.362 20.673C15.7202 21 14.8802 21 13.2 21H10.8C9.11984 21 8.27976 21 7.63803 20.673C7.07354 20.3854 6.6146 19.9265 6.32698 19.362C6 18.7202 6 17.8802 6 16.2V6M14 10V17M10 10V17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                                                </svg>
                                            </button>
                                        </div>
                                    </li>
                                `).join('')}
                            </ul>
                            <p class="mt-2 text-[11px] text-gray-500 dark:text-gray-400">
                                After choosing a draft, click Continue to prefill the form below.
                            </p>
                        </div>`;

                    // After rendering radio buttons, wire them to enable Continue only when a choice is made
                    if (draftModalContinue) {
                        draftModalContinue.disabled = true;
                        draftModalContinue.classList.add('opacity-50', 'cursor-not-allowed');

                        const radios = draftModalBody.querySelectorAll('input[name="draft-choice"]');
                        radios.forEach(r => {
                            r.addEventListener('change', () => {
                                if (r.checked) {
                                    draftModalContinue.disabled = false;
                                    draftModalContinue.classList.remove('opacity-50', 'cursor-not-allowed');
                                }
                            });
                        });
                    }
                }
            }

            draftModal.classList.remove('hidden');
            draftModal.classList.add('flex');
            document.body.style.overflow = 'hidden';
        }

        if (draftIconBtn && draftModal) {
            draftIconBtn.addEventListener('click', function (e) {
                e.preventDefault();
                showDraftModal();
            });
        }

        if (draftModalClose) {
            draftModalClose.addEventListener('click', hideDraftModal);
        }
        if (draftModalCloseFooter) {
            draftModalCloseFooter.addEventListener('click', hideDraftModal);
        }
        if (draftModalContinue && draftModal && draftModalBody) {
            draftModalContinue.addEventListener('click', function () {
                const drafts = window._CURRENT_DRAFT_LIST || [];
                if (!drafts.length) {
                    hideDraftModal();
                    return;
                }
                const chosen = draftModalBody.querySelector('input[name="draft-choice"]:checked');
                const idx = chosen ? parseInt(chosen.value, 10) : 0;
                const draft = drafts[idx] || drafts[0];
                if (draft) {
                    applyDraftToForm(draft);
                }
                hideDraftModal();
            });
        }

        if (draftModal) {
            draftModal.addEventListener('click', function (e) {
                if (e.target === draftModal) hideDraftModal();
            });
        }

        // Delegate click handling for per-draft delete buttons inside the modal
        if (draftModal && draftModalBody) {
            draftModalBody.addEventListener('click', async function (e) {
                const deleteBtn = e.target.closest('.draft-delete-btn');
                if (!deleteBtn) return;

                const li = deleteBtn.closest('li[data-draft-index]');
                if (!li) return;

                const draftId = li.getAttribute('data-draft-id');
                const idxStr = li.getAttribute('data-draft-index');
                const idx = idxStr ? parseInt(idxStr, 10) : -1;

                const drafts = window._CURRENT_DRAFT_LIST || [];
                const draft = idx >= 0 ? drafts[idx] : null;

                // Remove immediately from UI and in-memory list for responsiveness
                if (idx >= 0) {
                    drafts.splice(idx, 1);
                    window._CURRENT_DRAFT_LIST = drafts;
                }
                li.remove();

                // Fire delete API in background; if it fails, just log it.
                if (draftId) {
                    try {
                        await callDraftAPI('delete-draft', 'DELETE', {
                            user_id: window.CURRENT_USER_ID,
                            user_type: window.CURRENT_USER_TYPE ? window.CURRENT_USER_TYPE.replace(/\/$/, '') : window.CURRENT_USER_TYPE,
                            draft_id: draftId,
                        });
                    } catch (err) {
                        console.error('Failed to delete draft', err);
                    }
                }

                // If no drafts left, show empty message
                if (!drafts.length) {
                    draftModalBody.innerHTML = '<p class="text-gray-600 dark:text-gray-300 text-sm">No draft found for this user.</p>';
                }
            });
        }
    });
})();