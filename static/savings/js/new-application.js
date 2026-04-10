(function () {
    if (!window.touchedFields) {
        window.touchedFields = new Set();
    }
    const touchedFields = window.touchedFields;

    function getErrorKeyForField(field) {
        const id = field && field.id ? String(field.id) : '';
        const name = field && field.name ? String(field.name) : '';
        if (name) return name;
        if (id === 'saving_type') return 'product_type';
        if (id === 'saving_product') return 'product_id';
        return id;
    }

    function showFieldError(field, message) {
        const key = getErrorKeyForField(field);
        if (!key) return;

        const sameAddressCheckbox = document.getElementById('same-address');
        const isCurrentField = ['current_address_line_1', 'current_state', 'current_post_code', 'current_city_or_town', 'current_district', 'residential_proof_type', 'residential_proof_file'].includes(key);
        if (isCurrentField && sameAddressCheckbox && sameAddressCheckbox.checked) {
            clearFieldError(field);
            touchedFields.delete(key);
            return;
        }

        if (!message || (!touchedFields.has(key) && !window._showAllErrors)) {
            clearFieldError(field);
            return;
        }

        const errDiv = document.getElementById('error-' + key);
        if (errDiv) errDiv.textContent = message;
        if (key === 'product_id') {
            const btn = document.getElementById('saving_product_button');
            if (btn && btn.classList) btn.classList.add('border-red-500');
        } else {
            if (field && field.classList) field.classList.add('border-red-500');
        }
    }

    function clearFieldError(field) {
        const key = getErrorKeyForField(field);
        if (!key) return;
        const errDiv = document.getElementById('error-' + key);
        if (errDiv) errDiv.textContent = '';
        if (key === 'product_id') {
            const btn = document.getElementById('saving_product_button');
            if (btn && btn.classList) btn.classList.remove('border-red-500');
        } else {
            if (field && field.classList) field.classList.remove('border-red-500');
        }
    }

    window.clearFieldError = clearFieldError;

    function toTitleCase(value) {
        const s = (value || '').toString();
        if (!s.trim()) return s;

        return s
            .split(' ')
            .map(part => {
                const p = part.trim();
                if (!p) return '';
                return p
                    .split('-')
                    .map(seg => {
                        if (!seg) return '';
                        const first = seg.charAt(0).toUpperCase();
                        const rest = seg.slice(1).toLowerCase();
                        return first + rest;
                    })
                    .join('-');
            })
            .join(' ')
            .replace(/\s+/g, ' ')
            .trim();
    }

    function toTitleCaseLive(value) {
        const s = (value || '').toString();
        if (!s) return s;

        return s
            .split(' ')
            .map(part => {
                if (!part) return '';
                return part
                    .split('-')
                    .map(seg => {
                        if (!seg) return '';
                        const first = seg.charAt(0).toUpperCase();
                        const rest = seg.slice(1).toLowerCase();
                        return first + rest;
                    })
                    .join('-');
            })
            .join(' ');
    }

    function setupTitleCaseInputs() {
        const ids = [
            'full_name',
            'nominee_name',
            'nominee_relationship',

            'address_line_1',
            'address_line_2',
            'landmark',
            'post_office',
            'city_or_town',
            'district',
            'state',

            'current_address_line_1',
            'current_address_line_2',
            'current_landmark',
            'current_post_office',
            'current_city_or_town',
            'current_district',
            'current_state',
        ];
        ids.forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('input', function () {
                const start = this.selectionStart;
                const end = this.selectionEnd;
                const oldValue = this.value || '';
                const formatted = toTitleCaseLive(oldValue);
                if (formatted !== oldValue) {
                    this.value = formatted;
                    if (typeof start === 'number' && typeof end === 'number') {
                        try {
                            this.setSelectionRange(start, end);
                        } catch (e) {}
                    }
                }
            });
            el.addEventListener('blur', function () {
                const formatted = toTitleCase(this.value);
                if (formatted !== this.value) this.value = formatted;
            });
        });
    }

    function normalizeNomineeKycNumberByType() {
        const nomineeKycTypeEl = document.getElementById('nominee_kyc_type');
        const nomineeKycNumberEl = document.getElementById('nominee_kyc_number');
        if (!nomineeKycTypeEl || !nomineeKycNumberEl) return;

        const type = (nomineeKycTypeEl.value || '').trim().toLowerCase();

        if (type === 'aadhaar') {
            let value = (nomineeKycNumberEl.value || '').replace(/\D/g, '');
            value = value.slice(0, 12);
            nomineeKycNumberEl.value = value ? value.match(/.{1,4}/g).join(' ') : '';
        } else if (type === 'pan') {
            nomineeKycNumberEl.value = (nomineeKycNumberEl.value || '').toUpperCase();
        }
    }

    function setupNomineeKycTypeDrivenFormatting() {
        const nomineeKycTypeEl = document.getElementById('nominee_kyc_type');
        const nomineeKycNumberEl = document.getElementById('nominee_kyc_number');
        if (!nomineeKycTypeEl || !nomineeKycNumberEl) return;

        nomineeKycTypeEl.addEventListener('change', function () {
            touchedFields.add(getErrorKeyForField(this));
            clearFieldError(this);
            normalizeNomineeKycNumberByType();
            touchedFields.add(getErrorKeyForField(nomineeKycNumberEl));
            const msg = customValidation(nomineeKycNumberEl);
            if (msg) showFieldError(nomineeKycNumberEl, msg);
            else clearFieldError(nomineeKycNumberEl);
        });

        nomineeKycNumberEl.addEventListener('input', function () {
            normalizeNomineeKycNumberByType();
        });
    }

    function setupDobFlatpickr() {
        const dobEl = document.getElementById('date_of_birth');
        if (!dobEl) return;
        if (!dobEl.classList || !dobEl.classList.contains('dob-datepicker')) return;
        if (typeof window.flatpickr !== 'function') return;

        const initialDate = (dobEl.value || '').trim();

        if (dobEl._flatpickr) {
            try {
                if (initialDate) dobEl._flatpickr.setDate(initialDate, true);
            } catch (e) {}
            return;
        }

        const instance = window.flatpickr(dobEl, {
            mode: 'single',
            dateFormat: 'Y-m-d',
            altInput: true,
            altFormat: 'd-m-Y',
            allowInput: true,
            maxDate: 'today',
            disableMobile: true,
            defaultDate: initialDate || null,
        });

        const inputEl = instance && instance.altInput ? instance.altInput : dobEl;

        if (dobEl.id === 'date_of_birth') {
            inputEl.addEventListener('input', function () {
                let v = (this.value || '').replace(/[^0-9]/g, '');

                if (v.length > 8) v = v.slice(0, 8);

                let formatted = '';
                if (v.length <= 2) {
                    formatted = v;
                } else if (v.length <= 4) {
                    formatted = v.slice(0, 2) + '-' + v.slice(2);
                } else {
                    formatted = v.slice(0, 2) + '-' + v.slice(2, 4) + '-' + v.slice(4);
                }

                this.value = formatted;

                if (formatted.length === 10) {
                    const parts = formatted.split('-');
                    const dd = parts[0];
                    const mm = parts[1];
                    const yyyy = parts[2];

                    const day = parseInt(dd, 10);
                    const month = parseInt(mm, 10);
                    const year = parseInt(yyyy, 10);

                    if (!isNaN(day) && !isNaN(month) && !isNaN(year) && day >= 1 && day <= 31 && month >= 1 && month <= 12) {
                        dobEl.value = `${year.toString().padStart(4, '0')}-${mm}-${dd}`;
                        try {
                            if (dobEl._flatpickr) dobEl._flatpickr.setDate(dobEl.value, false);
                        } catch (e) {}

                        touchedFields.add(getErrorKeyForField(dobEl));
                        const msg = customValidation(dobEl);

                        if (msg) {
                            showFieldError(dobEl, msg);
                            inputEl.classList.add('border-red-500');
                        } else {
                            clearFieldError(dobEl);
                            inputEl.classList.remove('border-red-500');
                        }
                    } else {
                        dobEl.value = '';
                        showFieldError(dobEl, 'Please enter a valid date of birth.');
                        inputEl.classList.add('border-red-500');
                    }
                } else {
                    dobEl.value = '';
                    inputEl.classList.remove('border-red-500');
                }
            });
        }
    }

    window.validateNomineeSection = function validateNomineeSection() {
        const nomineeNameEl = document.getElementById('nominee_name');
        const nomineeRelationshipEl = document.getElementById('nominee_relationship');
        const nomineeKycTypeEl = document.getElementById('nominee_kyc_type');
        const nomineeKycNumberEl = document.getElementById('nominee_kyc_number');
        const nomineeKycDocEl = document.getElementById('nominee_kyc_document');

        if (!nomineeNameEl || !nomineeRelationshipEl || !nomineeKycTypeEl || !nomineeKycNumberEl || !nomineeKycDocEl) {
            return true;
        }

        let ok = true;

        const nomineeName = (nomineeNameEl.value || '').trim();
        const nomineeRelationship = (nomineeRelationshipEl.value || '').trim();
        const nomineeKycType = (nomineeKycTypeEl.value || '').trim();
        const nomineeKycNumber = (nomineeKycNumberEl.value || '').trim();
        const nomineeKycDoc = nomineeKycDocEl.files && nomineeKycDocEl.files.length ? nomineeKycDocEl.files[0] : null;

        clearFieldError(nomineeNameEl);
        clearFieldError(nomineeRelationshipEl);
        clearFieldError(nomineeKycTypeEl);
        clearFieldError(nomineeKycNumberEl);
        clearFieldError(nomineeKycDocEl);

        if (!nomineeName) {
            showFieldError(nomineeNameEl, 'This field is required.');
            ok = false;
        }
        if (!nomineeRelationship) {
            showFieldError(nomineeRelationshipEl, 'This field is required.');
            ok = false;
        }
        // if (!nomineeKycType) {
        //     showFieldError(nomineeKycTypeEl, 'This field is required.');
        //     ok = false;
        // }
        // if (!nomineeKycNumber) {
        //     showFieldError(nomineeKycNumberEl, 'This field is required.');
        //     ok = false;
        // } else {
        if (nomineeKycNumber) {
            const msg = customValidation(nomineeKycNumberEl);
            if (msg) {
                showFieldError(nomineeKycNumberEl, msg);
                ok = false;
            }
        }
        // if (!nomineeKycDoc) {
        //     showFieldError(nomineeKycDocEl, 'This field is required.');
        //     ok = false;
        // }

        return ok;
    };

    function customValidation(field) {
        const key = getErrorKeyForField(field);

        const sameAddressCheckbox = document.getElementById('same-address');
        const isSame = sameAddressCheckbox && sameAddressCheckbox.checked;

        if (field && field.type === 'file') {
            const files = field.files;
            if (files && files.length > 0) {
                const file = files[0];
                const maxSize = 1024 * 1024;
                if (file.size > maxSize) {
                    return 'File size must be less than or equal to 1MB.';
                }
                if (key === 'photo') {
                    if (!file.type || !file.type.startsWith('image/')) {
                        return 'Please upload an image file (JPG, PNG, etc.).';
                    }
                }
            }
        }

        if (key === 'date_of_birth') {
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

        if (isSame && ['current_address_line_1', 'current_state', 'current_post_code', 'current_city_or_town', 'current_district', 'residential_proof_type', 'residential_proof_file'].includes(key)) {
            return null;
        }

        if (key === 'adhar_number') {
            const cleanValue = (field.value || '').replace(/\s/g, '');
            if (!/^\d{12}$/.test(cleanValue)) return 'Adhar number must be exactly 12 digits.';
        }

        if (key === 'pan_number') {
            const panValue = (field.value || '').toUpperCase();
            field.value = panValue;
            if (!/^[A-Z]{5}\d{4}[A-Z]$/.test(panValue)) {
                return 'PAN number must be 5 letters, 4 digits, 1 letter (e.g., ABCDE1234F).';
            }
        }

        if (key === 'nominee_kyc_number') {
            const nomineeKycTypeEl = document.getElementById('nominee_kyc_type');
            const nomineeType = (nomineeKycTypeEl?.value || '').trim().toLowerCase();
            const raw = (field.value || '').trim();

            if (!raw) return null;

            if (!nomineeType) return 'Please select Nominee KYC Type first.';

            if (nomineeType === 'aadhaar') {
                const cleanValue = raw.replace(/\s/g, '');
                if (!/^\d{12}$/.test(cleanValue)) return 'Nominee Aadhaar number must be exactly 12 digits.';
            }

            if (nomineeType === 'pan') {
                const panValue = raw.toUpperCase();
                field.value = panValue;
                if (!/^[A-Z]{5}\d{4}[A-Z]$/.test(panValue)) {
                    return 'Nominee PAN number must be 5 letters, 4 digits, 1 letter (e.g., ABCDE1234F).';
                }
            }
        }

        if (key === 'contact') {
            const digitsOnly = (field.value || '').replace(/\D/g, '');
            if (digitsOnly !== field.value) field.value = digitsOnly;
            if (!/^\d{10}$/.test(field.value || '')) return 'Contact number must be exactly 10 digits.';
        }

        if (key === 'post_code') {
            if (!/^\d{6}$/.test(field.value || '')) return 'Post code must be exactly 6 digits.';
        }

        if (key === 'current_post_code') {
            if (!isSame && !/^\d{6}$/.test(field.value || '')) return 'Current post code must be exactly 6 digits.';
        }

        if (key === 'product_type') {
            const productType = document.getElementById('product_type')?.value || '';
            if (!productType) return 'This field is required.';
        }

        if (key === 'product_id') {
            const productId = document.getElementById('product_id')?.value || '';
            if (!productId) return 'This field is required.';
        }

        // interest_rate and tenure are derived from selected Product (Option A)

        if (!isSame) {
            if (key === 'current_address_line_1' && !field.value) return 'This field is required.';
            if (key === 'current_post_code' && !field.value) return 'This field is required.';
            if (key === 'current_city_or_town' && !field.value) return 'This field is required.';
            if (key === 'current_district' && !field.value) return 'This field is required.';
            if (key === 'current_state' && !field.value) return 'This field is required.';
            if (key === 'residential_proof_type' && !field.value) return 'This field is required when current address differs from permanent address.';
            if (key === 'residential_proof_file' && !field.value) return 'This field is required when current address differs from permanent address.';
        }

        return null;
    }

    function syncHiddenProductFieldsFromCurrentSelection() {
        const typeSelect = document.getElementById('saving_type');
        const productSelect = document.getElementById('saving_product');

        const hiddenProductType = document.getElementById('product_type');
        const hiddenProductId = document.getElementById('product_id');

        if (typeSelect && hiddenProductType && !hiddenProductType.value) {
            const selectedText = (typeSelect.options && typeSelect.selectedIndex >= 0)
                ? (typeSelect.options[typeSelect.selectedIndex]?.text || '')
                : '';
            const code = getProductTypeCodeFromName(selectedText);
            hiddenProductType.value = code || '';
        }

        if (productSelect && hiddenProductId) {
            hiddenProductId.value = productSelect.value || '';
        }
    }

    function validateAllFields() {
        const form = document.getElementById('savings-application-form');
        if (!form) return false;
        let valid = true;

        ['nominee_kyc_type', 'nominee_kyc_number', 'nominee_kyc_document', 'photo', 'signature'].forEach((id) => {
            const el = document.getElementById(id);
            if (el && el.hasAttribute && el.hasAttribute('required')) el.removeAttribute('required');
        });

        syncHiddenProductFieldsFromCurrentSelection();

        window._showAllErrors = true;

        const requiredFields = form.querySelectorAll('input[required], select[required]');
        requiredFields.forEach(field => {
            const key = getErrorKeyForField(field);
            const sameAddressCheckbox = document.getElementById('same-address');
            const isCurrentField = ['current_address_line_1', 'current_state', 'current_post_code', 'current_city_or_town', 'current_district', 'residential_proof_type', 'residential_proof_file'].includes(key);

            if (['nominee_kyc_type', 'nominee_kyc_number', 'nominee_kyc_document', 'photo', 'signature'].includes(key)) {
                clearFieldError(field);
                return;
            }

            if (isCurrentField && sameAddressCheckbox && sameAddressCheckbox.checked) {
                clearFieldError(field);
                return;
            }

            clearFieldError(field);

            if (field.type === 'file') {
                if (field.hasAttribute('required') && (!field.files || field.files.length === 0)) {
                    showFieldError(field, 'This field is required.');
                    valid = false;
                    return;
                }
            } else {
                if (!field.value) {
                    showFieldError(field, 'This field is required.');
                    valid = false;
                    return;
                }
            }

            const customMsg = customValidation(field);
            if (customMsg) {
                showFieldError(field, customMsg);
                valid = false;
            }
        });

        ['product_type'].forEach(id => {
            const hidden = document.getElementById(id);
            if (!hidden) return;
            const msg = customValidation(hidden);
            if (msg) {
                const key = getErrorKeyForField(hidden);
                const errDiv = document.getElementById('error-' + key);
                if (errDiv) errDiv.textContent = msg;
                valid = false;
            }
        });

        ['product_id'].forEach(id => {
            const hidden = document.getElementById(id);
            if (!hidden) return;
            const msg = customValidation(hidden);
            if (msg) {
                const key = getErrorKeyForField(hidden);
                const errDiv = document.getElementById('error-' + key);
                if (errDiv) errDiv.textContent = msg;
                valid = false;
            }
        });

        if (typeof window.validateNomineeSection === 'function') {
            const nomineeOk = window.validateNomineeSection();
            if (!nomineeOk) valid = false;
        }

        setTimeout(() => { window._showAllErrors = false; }, 100);
        return valid;
    }

    function attachInstantValidation() {
        const form = document.getElementById('savings-application-form');
        if (!form) return;

        const requiredFields = form.querySelectorAll('input[required], select[required]');
        const extraFields = form.querySelectorAll('input#adhar_number, input#pan_number, input#contact, input#post_code, input#current_post_code');
        const allFields = [...requiredFields, ...extraFields];

        const unique = [];
        const seen = new Set();
        allFields.forEach(f => {
            const key = getErrorKeyForField(f);
            if (!key || seen.has(key)) return;
            seen.add(key);
            unique.push(f);
        });

        unique.forEach(field => {
            field.addEventListener('input', function () {
                const key = getErrorKeyForField(this);
                touchedFields.add(key);
                clearFieldError(this);
                if (['nominee_kyc_type', 'nominee_kyc_number', 'nominee_kyc_document', 'photo', 'signature'].includes(key)) {
                    return;
                }
                if (!this.value) {
                    if (this.hasAttribute('required')) {
                        showFieldError(this, 'This field is required.');
                    }
                } else {
                    const msg = customValidation(this);
                    if (msg) showFieldError(this, msg);
                }
            });

            field.addEventListener('blur', function () {
                const key = getErrorKeyForField(this);
                touchedFields.add(key);
                if (['nominee_kyc_type', 'nominee_kyc_number', 'nominee_kyc_document', 'photo', 'signature'].includes(key)) {
                    return;
                }
                if (!this.value) {
                    if (this.hasAttribute('required')) {
                        showFieldError(this, 'This field is required.');
                    }
                } else {
                    const msg = customValidation(this);
                    if (msg) showFieldError(this, msg);
                }
            });

            field.addEventListener('change', function () {
                const key = getErrorKeyForField(this);
                touchedFields.add(key);

                if (['nominee_kyc_type', 'nominee_kyc_number', 'nominee_kyc_document', 'photo', 'signature'].includes(key)) {
                    clearFieldError(this);
                    return;
                }

                if (this.type === 'file') {
                    clearFieldError(this);
                    if (this.hasAttribute('required') && (!this.files || this.files.length === 0)) {
                        showFieldError(this, 'This field is required.');
                        return;
                    }
                    const msg = customValidation(this);
                    if (msg) showFieldError(this, msg);
                    else clearFieldError(this);
                    return;
                }

                clearFieldError(this);
                if (!this.value) {
                    if (this.hasAttribute('required')) {
                        showFieldError(this, 'This field is required.');
                    }
                } else {
                    const msg = customValidation(this);
                    if (msg) showFieldError(this, msg);
                }
            });

            clearFieldError(field);
            touchedFields.delete(getErrorKeyForField(field));
        });
    }

    function setupUppercaseInputs() {
        const panInput = document.getElementById('pan_number');
        if (panInput) {
            panInput.addEventListener('input', function () {
                this.value = (this.value || '').toUpperCase();
            });
        }
    }

    function setupAadhaarFormatting() {
        const aadhaarInput = document.getElementById('adhar_number');
        if (!aadhaarInput) return;
        aadhaarInput.addEventListener('input', function () {
            let value = (this.value || '').replace(/\D/g, '');
            value = value.slice(0, 12);
            let formattedValue = '';
            if (value.length > 0) {
                formattedValue = value.match(/.{1,4}/g).join(' ');
            }
            this.value = formattedValue;
        });
        aadhaarInput.addEventListener('paste', function (e) {
            e.preventDefault();
            const pastedText = (e.clipboardData || window.clipboardData).getData('text');
            const cleanValue = pastedText.replace(/\D/g, '');
            this.value = cleanValue;
            this.dispatchEvent(new Event('input'));
        });
    }
    function getProductTypeCodeFromName(name) {
        const n = (name || '').toString().trim().toLowerCase();
        if (!n) return '';
        if (n.includes('rd') || n.includes('recurring') || n.includes('recuring') || n.includes('recurr')) return 'rd';
        if (n.includes('fd') || n.includes('fixed')) return 'fd';
        return '';
    }

    function getInvestLabelPrefixFromTenureUnit(unit) {
        const u = (unit || '').toString().trim().toLowerCase();
        if (u === 'days') return 'Daily';
        if (u === 'weeks') return 'Weekly';
        if (u === 'months') return 'Monthly';
        if (u === 'years') return 'Yearly';
        return '';
    }

    function updateInstallmentAmountLabel() {}

    function toggleAmountFields() {}

    window.SAVINGS_MASTER = window.SAVINGS_MASTER || {
        loaded: false,
        types: [],
        interests: [],
        tenures: [],
    };

    function setSelectOptions(selectEl, options, placeholder) {
        if (!selectEl) return;
        selectEl.innerHTML = '';
        selectEl.insertAdjacentHTML('beforeend', `<option value="">${placeholder}</option>`);
        options.forEach(opt => {
            const optionEl = document.createElement('option');
            optionEl.value = opt.value;
            optionEl.textContent = opt.label;
            if (opt && opt.data) {
                Object.keys(opt.data).forEach(k => {
                    if (opt.data[k] !== undefined && opt.data[k] !== null) {
                        optionEl.dataset[k] = String(opt.data[k]);
                    }
                });
            }
            selectEl.appendChild(optionEl);
        });

        if (selectEl && selectEl.id === 'saving_product') {
            refreshSavingProductCustomDropdown();
        }
    }

    function setSavingProductPanelOpen(open) {
        const panel = document.getElementById('saving_product_panel');
        if (!panel) return;
        panel.classList.toggle('hidden', !open);
        if (open) {
            renderSavingProductCustomOptions('');
        }
    }

    function renderSavingProductCustomOptions(query) {
        const selectEl = document.getElementById('saving_product');
        const container = document.getElementById('saving_product_options');
        if (!selectEl || !container) return;

        const q = (query || '').toString().trim().toLowerCase();
        const current = selectEl.value || '';
        const opts = Array.from(selectEl.options || []).filter(o => !!o.value);

        const filtered = q
            ? opts.filter(o => (o.text || '').toLowerCase().includes(q))
            : opts;

        container.innerHTML = '';

        function optionDisplayParts(optionEl) {
            const ds = (optionEl && optionEl.dataset) ? optionEl.dataset : {};
            const rawAmount = ds.amount ? `₹${ds.amount}` : '';
            const rawInterest = ds.interest ? `${ds.interest}%` : '';
            const rawTenure = ds.tenure || '';
            const freq = (ds.frequency || '').trim();

            const amount = freq
                ? `${rawAmount} (${freq})`.trim()
                : (rawAmount || (optionEl.text || '-'));
            const interest = rawInterest || '-';
            const tenure = rawTenure || '-';
            return { amount, interest, tenure };
        }

        if (!filtered.length) {
            container.insertAdjacentHTML(
                'beforeend',
                '<div class="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">No results</div>'
            );
            return;
        }

        container.insertAdjacentHTML(
            'beforeend',
            `<div class="flex items-center justify-between px-3 py-2 text-xs font-semibold text-gray-500 dark:text-gray-400">
                <div class="flex-1 pr-3">Amount</div>
                <div class="flex-1 pr-3">Interest</div>
                <div class="flex-1 text-right">Tenure</div>
            </div>`
        );

        filtered.forEach(o => {
            const active = o.value === current;
            const parsed = optionDisplayParts(o);
            container.insertAdjacentHTML(
                'beforeend',
                `<button type="button" data-value="${o.value}" class="w-full px-3 py-2 text-left text-sm rounded-md ${active ? 'bg-brand-50 text-brand-700 dark:bg-white/10 dark:text-white' : 'text-gray-800 hover:bg-gray-50 dark:text-white/90 dark:hover:bg-white/10'}">
                    <span class="flex items-center justify-between">
                        <span class="block truncate flex-1 pr-3">${parsed.amount}</span>
                        <span class="block truncate flex-1 pr-3">${parsed.interest}</span>
                        <span class="block truncate flex-1 text-right">${parsed.tenure}</span>
                    </span>
                </button>`
            );
        });

        container.querySelectorAll('button[data-value]').forEach(btn => {
            btn.addEventListener('click', function () {
                const val = this.getAttribute('data-value') || '';
                selectEl.value = val;
                selectEl.dispatchEvent(new Event('change', { bubbles: true }));
                refreshSavingProductCustomDropdown();
                setSavingProductPanelOpen(false);
            });
        });
    }

    function refreshSavingProductCustomDropdown() {
        const selectEl = document.getElementById('saving_product');
        const btnText = document.getElementById('saving_product_button_text');
        const btn = document.getElementById('saving_product_button');
        const wrapper = document.getElementById('saving_product_dropdown');

        if (!wrapper) return;
        if (!selectEl || !btnText || !btn) {
            wrapper.style.display = 'none';
            return;
        }

        const selected = selectEl.options && selectEl.selectedIndex >= 0
            ? selectEl.options[selectEl.selectedIndex]
            : null;
        if (selected && selected.value) {
            const ds = selected.dataset || {};
            if (ds.amount || ds.interest || ds.tenure || ds.frequency) {
                const amount = ds.amount ? `₹${ds.amount}` : '';
                const freq = (ds.frequency || '').trim();
                const amountPart = freq ? `${amount} (${freq})`.trim() : (amount || '');
                const interestPart = ds.interest ? `${ds.interest}%` : '';
                const tenurePart = ds.tenure ? ds.tenure : '';

                const parts = [amountPart, interestPart, tenurePart].filter(Boolean);
                btnText.textContent = parts.length ? parts.join(' - ') : (selected.text || 'Select Product');
            } else {
                btnText.textContent = selected.text || 'Select Product';
            }
        } else {
            btnText.textContent = 'Select Product';
        }
    }

    function setupSavingProductCustomDropdown() {
        const wrapper = document.getElementById('saving_product_dropdown');
        const btn = document.getElementById('saving_product_button');
        const panel = document.getElementById('saving_product_panel');

        if (!wrapper || !btn || !panel) return;

        btn.addEventListener('click', function () {
            const isOpen = !panel.classList.contains('hidden');
            setSavingProductPanelOpen(!isOpen);
        });

        document.addEventListener('click', function (e) {
            if (!wrapper.contains(e.target)) {
                setSavingProductPanelOpen(false);
            }
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                setSavingProductPanelOpen(false);
            }
        });

        refreshSavingProductCustomDropdown();
    }

    function resetProductFields() {
        const interestRate = document.getElementById('interest_rate');
        const tenureInput = document.getElementById('tenure');
        const interestRateInput = document.getElementById('interest_rate');

        if (interestRate) interestRate.value = '';
        if (tenureInput) tenureInput.value = '';
        if (interestRateInput) interestRateInput.value = '';
    }

    function populateSavingTypes() {
        const typeSelect = document.getElementById('saving_type');
        const options = window.SAVINGS_MASTER.types.map(t => ({ value: t.id, label: t.name }));
        setSelectOptions(typeSelect, options, 'Select Saving Type');
    }

    function populateSavingProductsByCode(code) {
        const productSelect = document.getElementById('saving_product');
        if (!productSelect) return;

        if (code !== 'fd' && code !== 'rd') {
            setSelectOptions(productSelect, [], 'Select Product');
            return;
        }

        const products = code === 'rd'
            ? (window.SAVINGS_MASTER.daily_products || [])
            : (window.SAVINGS_MASTER.one_time_deposits || []);

        const frequencyFromTenureUnit = (unit) => {
            const u = (unit || '').toString().toLowerCase();
            if (u === 'days' || u === 'day') return 'daily';
            if (u === 'weeks' || u === 'week') return 'weekly';
            if (u === 'months' || u === 'month') return 'monthly';
            if (u === 'years' || u === 'year') return 'yearly';
            return '';
        };

        const options = products.map(p => ({
            value: p.id,
            label: `₹${p.deposit_amount} @ ${p.interest_rate}% - ${p.tenure} ${(p.tenure_unit || (code === 'rd' ? 'days' : 'months'))}`,
            data: {
                amount: p.deposit_amount,
                interest: p.interest_rate,
                tenure: `${p.tenure} ${(p.tenure_unit || (code === 'rd' ? 'days' : 'months'))}`,
                frequency: code === 'rd' ? frequencyFromTenureUnit(p.tenure_unit || 'days') : '',
            }
        }));
        setSelectOptions(productSelect, options, 'Select Product');
    }

    function syncHiddenProductTypeFromSavingType(typeId) {
        const hiddenProductType = document.getElementById('product_type');
        const type = window.SAVINGS_MASTER.types.find(t => t.id === typeId);
        const code = getProductTypeCodeFromName(type?.name);
        if (hiddenProductType) hiddenProductType.value = code || '';
    }

    function syncHiddenFieldsFromProduct(productId) {
        const hiddenProductId = document.getElementById('product_id');
        const hiddenInterestRate = document.getElementById('interest_rate');
        const hiddenTenure = document.getElementById('tenure');

        if (hiddenProductId) hiddenProductId.value = productId || '';
        if (!productId) {
            if (hiddenInterestRate) hiddenInterestRate.value = '';
            if (hiddenTenure) hiddenTenure.value = '';
            return;
        }

        const productType = document.getElementById('product_type')?.value || '';
        const products = productType === 'rd'
            ? (window.SAVINGS_MASTER.daily_products || [])
            : (window.SAVINGS_MASTER.one_time_deposits || []);
        const product = products.find(p => p.id === productId);
        if (!product) {
            if (hiddenInterestRate) hiddenInterestRate.value = '';
            if (hiddenTenure) hiddenTenure.value = '';
            return;
        }

        if (hiddenInterestRate) hiddenInterestRate.value = String(product.interest_rate ?? '');
        if (hiddenTenure) hiddenTenure.value = String(product.tenure ?? '');
    }

    async function setupMasterDrivenProductDetails() {
        try {
            await window.loadSavingsMasterData();
            populateSavingTypes();

            window.SAVINGS_MASTER.one_time_deposits = window.SAVINGS_MASTER.one_time_deposits || [];
            window.SAVINGS_MASTER.daily_products = window.SAVINGS_MASTER.daily_products || [];
        } catch (e) {
            console.error(e);
            return;
        }

        const typeSelect = document.getElementById('saving_type');
        const productSelect = document.getElementById('saving_product');

        if (typeSelect) {
            typeSelect.addEventListener('change', function () {
                const typeId = this.value;
                resetProductFields();
                syncHiddenProductTypeFromSavingType(typeId);

                const selectedText = (this.options && this.selectedIndex >= 0)
                    ? (this.options[this.selectedIndex]?.text || '')
                    : '';
                const codeFromText = getProductTypeCodeFromName(selectedText);
                const code = codeFromText || (document.getElementById('product_type')?.value || '');

                const hiddenProductType = document.getElementById('product_type');
                if (hiddenProductType) hiddenProductType.value = code || '';

                const errType = document.getElementById('error-product_type');
                if (errType) errType.textContent = '';
                clearFieldError(this);

                const errProduct = document.getElementById('error-product_id');
                if (errProduct) errProduct.textContent = '';

                populateSavingProductsByCode(code);
                toggleAmountFields();

                if (productSelect) productSelect.value = '';
            });
        }

        if (productSelect) {
            productSelect.addEventListener('change', function () {
                const hiddenProductId = document.getElementById('product_id');
                if (hiddenProductId) hiddenProductId.value = this.value || '';
                syncHiddenFieldsFromProduct(this.value);

                const errProduct = document.getElementById('error-product_id');
                if (errProduct) errProduct.textContent = '';
                clearFieldError(this);
            });
        }
    }

    function autoFillAddressFields(pincode, isCurrentAddress = false) {
        const prefix = isCurrentAddress ? 'current_' : '';

        const postOfficeField = document.getElementById(prefix + 'post_office');
        const cityField = document.getElementById(prefix + 'city_or_town');
        const districtField = document.getElementById(prefix + 'district');
        const stateField = document.getElementById(prefix + 'state');

        const fields = [postOfficeField, cityField, districtField, stateField];
        fields.forEach(field => {
            if (field && !field.dataset.manuallyEdited) {
                field.classList.add('loading');
                field.value = 'Loading...';
            }
        });

        window.fetchAddressFromPincode(pincode).then(addressData => {
            if (addressData) {
                if (postOfficeField && !postOfficeField.dataset.manuallyEdited) {
                    postOfficeField.value = addressData.postOffice;
                    postOfficeField.classList.remove('loading');
                    postOfficeField.classList.add('auto-filled');
                    postOfficeField.dispatchEvent(new Event('input'));
                }
                if (cityField && !cityField.dataset.manuallyEdited) {
                    cityField.value = addressData.city;
                    cityField.classList.remove('loading');
                    cityField.classList.add('auto-filled');
                    cityField.dispatchEvent(new Event('input'));
                }
                if (districtField && !districtField.dataset.manuallyEdited) {
                    districtField.value = addressData.district;
                    districtField.classList.remove('loading');
                    districtField.classList.add('auto-filled');
                    districtField.dispatchEvent(new Event('input'));
                }
                if (stateField && !stateField.dataset.manuallyEdited) {
                    stateField.value = addressData.state;
                    stateField.classList.remove('loading');
                    stateField.classList.add('auto-filled');
                    stateField.dispatchEvent(new Event('input'));
                }
            } else {
                fields.forEach(field => {
                    if (field && !field.dataset.manuallyEdited) {
                        field.value = '';
                        field.classList.remove('loading');
                    }
                });
            }
        }).catch(() => {
            fields.forEach(field => {
                if (field && !field.dataset.manuallyEdited) {
                    field.value = '';
                    field.classList.remove('loading');
                }
            });
        });
    }

    function setupPincodeAutoFill() {
        const permanentPincodeField = document.getElementById('post_code');
        const currentPincodeField = document.getElementById('current_post_code');

        if (permanentPincodeField) {
            permanentPincodeField.addEventListener('blur', function () {
                const pincode = this.value.trim();
                if (pincode.length === 6 && /^\d{6}$/.test(pincode)) {
                    setTimeout(() => autoFillAddressFields(pincode, false), 100);
                }
            });
        }

        if (currentPincodeField) {
            currentPincodeField.addEventListener('blur', function () {
                const pincode = this.value.trim();
                if (pincode.length === 6 && /^\d{6}$/.test(pincode)) {
                    setTimeout(() => autoFillAddressFields(pincode, true), 100);
                }
            });
        }
    }

    function setCurrentAddressVisibilityAndRequired(isSameAddress) {
        const currentSection = document.getElementById('current-address-section');
        const residentialProofEls = document.querySelectorAll('.residential-proof-section');
        const currentRequired = [
            'current_address_line_1', 'current_post_code', 'current_city_or_town', 'current_district', 'current_state'
        ];

        if (currentSection) currentSection.style.display = isSameAddress ? 'none' : '';
        residentialProofEls.forEach(el => el.style.display = isSameAddress ? 'none' : '');

        currentRequired.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.required = !isSameAddress;
        });

        const proofType = document.getElementById('residential_proof_type');
        const proofFile = document.getElementById('residential_proof_file');
        if (proofType) proofType.required = !isSameAddress;
        if (proofFile) proofFile.required = !isSameAddress;
    }

    function setupSameAddressToggle() {
        const sameAddressCheckbox = document.getElementById('same-address');
        if (!sameAddressCheckbox) return;

        sameAddressCheckbox.addEventListener('change', function () {
            setCurrentAddressVisibilityAndRequired(this.checked);
        });

        setCurrentAddressVisibilityAndRequired(sameAddressCheckbox.checked);
    }

    function setupAddressManualEditTracking() {
        const manualEditIds = [
            'post_office', 'city_or_town', 'district', 'state',
            'current_post_office', 'current_city_or_town', 'current_district', 'current_state'
        ];

        manualEditIds.forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('input', () => {
                el.dataset.manuallyEdited = 'true';
            });
        });
    }

    function setFieldValue(id, value) {
        const el = document.getElementById(id);
        if (!el) return;
        el.value = value == null ? '' : value;
        if (id === 'date_of_birth') {
            try {
                if (el._flatpickr) {
                    const v = (el.value || '').trim();
                    if (v) el._flatpickr.setDate(v, true);
                    else el._flatpickr.clear();
                }
            } catch (e) {}
        }
        el.dispatchEvent(new Event('input'));
        el.dispatchEvent(new Event('change'));
    }

    function bindLookupButton() {
        const lookupBtn = document.getElementById('customer_lookup_btn');
        if (lookupBtn) lookupBtn.addEventListener('click', window.fetchExistingCustomer);
    }

    function setupExistingCustomerSuggestions() {
        const inputEl = document.getElementById('customer_lookup_query');
        const panel = document.getElementById('customer_lookup_suggestions_panel');
        const listEl = document.getElementById('customer_lookup_suggestions_list');
        if (!inputEl || !panel || !listEl) return;

        let lastFetchId = 0;
        let lastQuery = null;
        let debounceTimer = null;
        let cachedEmptyLoaded = false;

        const pageSize = 10;
        let isLoading = false;
        let hasMore = false;
        let nextOffset = 0;

        const isBranch = window.location.pathname.startsWith('/branch/');
        const isAgent = window.location.pathname.startsWith('/agent/');
        const baseUrl = isBranch
            ? '/branch/savings/api/customer-lookup/'
            : (isAgent ? '/agent/savings/api/customer-lookup/' : '/savings/api/customer-lookup/');

        const escapeHtml = (s) => {
            return String(s == null ? '' : s)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        };

        const openPanel = () => {
            panel.classList.remove('hidden');
            updatePanelMaxHeight();
        };

        const closePanel = () => {
            panel.classList.add('hidden');
        };

        const renderLoading = () => {
            listEl.innerHTML = '<div class="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">Loading…</div>';
        };

        const renderEmpty = () => {
            listEl.innerHTML = '<div class="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">No customers found</div>';
        };

        const renderLoadingMore = () => {
            if (listEl.querySelector('[data-loading-more="1"]')) return;
            listEl.insertAdjacentHTML(
                'beforeend',
                '<div data-loading-more="1" class="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">Loading…</div>'
            );
        };

        const clearLoadingMore = () => {
            const el = listEl.querySelector('[data-loading-more="1"]');
            if (el) el.remove();
        };

        const updatePanelMaxHeight = () => {
            try {
                const rect = inputEl.getBoundingClientRect();
                const available = Math.max(160, Math.floor(window.innerHeight - rect.bottom - 16));
                const capped = Math.min(available, 320);
                panel.style.maxHeight = `${capped}px`;
                panel.style.overflowY = 'auto';
            } catch (e) {
                panel.style.maxHeight = '18rem';
                panel.style.overflowY = 'auto';
            }
        };

        const ensureScrollableOrLoadMore = () => {
            if (!hasMore) return;
            if (isLoading) return;
            if (panel.classList.contains('hidden')) return;

            const threshold = 2;
            if (panel.scrollHeight <= panel.clientHeight + threshold) {
                fetchMoreSuggestions();
            }
        };

        const bindItemClicks = (rootEl) => {
            rootEl.querySelectorAll('button[data-customer-id]').forEach((btn) => {
                if (btn.dataset.boundClick === '1') return;
                btn.dataset.boundClick = '1';
                btn.addEventListener('click', () => {
                    const cid = (btn.getAttribute('data-customer-id') || '').trim();
                    if (!cid) return;
                    inputEl.value = cid;
                    closePanel();
                    if (typeof window.fetchExistingCustomer === 'function') {
                        window.fetchExistingCustomer();
                    }
                });
            });
        };

        const renderItems = (customers, { append } = { append: false }) => {
            if (!customers || !customers.length) {
                if (!append) renderEmpty();
                return;
            }

            if (!append) listEl.innerHTML = '';
            customers.forEach((c) => {
                const fullName = escapeHtml(c.full_name || '');
                const customerId = escapeHtml(c.customer_id || '');
                const pan = escapeHtml(c.pan_number || '-');
                const aadhaar = escapeHtml(c.adhar_number || '-');

                const fdCount = Number(c.fd_count || 0);
                const rdCount = Number(c.rd_count || 0);
                const showCounts = (fdCount > 0) || (rdCount > 0);
                const countsText = showCounts ? ` | FD:<span class="font-semibold">&nbsp;${fdCount}</span> , RD:<span class="font-semibold">&nbsp;${rdCount}</span>` : '';

                listEl.insertAdjacentHTML(
                    'beforeend',
                    `<button type="button" class="w-full px-3 py-2 text-left text-sm rounded-md text-gray-800 hover:bg-gray-50 dark:text-white/90 dark:hover:bg-white/10" data-customer-id="${customerId}">
                        <div class="font-medium">${fullName}</div>
                        <div class="text-xs text-gray-500 dark:text-gray-400">PAN: ${pan} | Aadhaar: ${aadhaar}&nbsp;&nbsp;&nbsp;&nbsp;${countsText}</div>
                    </button>`
                );
            });

            bindItemClicks(listEl);
        };

        const fetchSuggestions = async (query, { allowEmpty } = { allowEmpty: false }) => {
            const q = (query || '').trim();
            if (!allowEmpty && !q) {
                renderEmpty();
                return;
            }

            isLoading = true;
            const fetchId = ++lastFetchId;
            lastQuery = q;

            hasMore = false;
            nextOffset = 0;

            renderLoading();
            openPanel();

            try {
                const url = `${baseUrl}?suggest=1&limit=${pageSize}&offset=0&q=${encodeURIComponent(q)}`;
                const res = await fetch(url, { method: 'GET', credentials: 'same-origin' });
                const data = await res.json();
                if (fetchId !== lastFetchId) return;

                if (!res.ok || !data || !data.success) {
                    renderEmpty();
                    return;
                }
                renderItems(data.customers || [], { append: false });
                hasMore = !!data.has_more;
                nextOffset = typeof data.next_offset === 'number' ? data.next_offset : (hasMore ? pageSize : 0);
                setTimeout(ensureScrollableOrLoadMore, 0);
            } catch (e) {
                if (fetchId !== lastFetchId) return;
                renderEmpty();
            } finally {
                isLoading = false;
            }
        };

        const fetchMoreSuggestions = async () => {
            if (!hasMore) return;
            if (isLoading) return;
            const q = (lastQuery || '').trim();
            if (!q && !cachedEmptyLoaded) return;

            isLoading = true;
            const fetchId = lastFetchId;
            renderLoadingMore();

            try {
                const url = `${baseUrl}?suggest=1&limit=${pageSize}&offset=${nextOffset}&q=${encodeURIComponent(q)}`;
                const res = await fetch(url, { method: 'GET', credentials: 'same-origin' });
                const data = await res.json();
                if (fetchId !== lastFetchId) return;

                if (!res.ok || !data || !data.success) {
                    hasMore = false;
                    return;
                }

                clearLoadingMore();
                renderItems(data.customers || [], { append: true });
                hasMore = !!data.has_more;
                nextOffset = typeof data.next_offset === 'number' ? data.next_offset : (hasMore ? (nextOffset + pageSize) : nextOffset);
                setTimeout(ensureScrollableOrLoadMore, 0);
            } catch (e) {
                hasMore = false;
            } finally {
                clearLoadingMore();
                isLoading = false;
            }
        };

        const scheduleFetch = (allowEmpty) => {
            if (debounceTimer) clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                fetchSuggestions(inputEl.value, { allowEmpty });
            }, 250);
        };

        inputEl.addEventListener('focus', () => {
            if (!cachedEmptyLoaded) {
                cachedEmptyLoaded = true;
                fetchSuggestions('', { allowEmpty: true });
                return;
            }

            const q = (inputEl.value || '').trim();
            if (q) {
                fetchSuggestions(q, { allowEmpty: false });
            } else {
                openPanel();
            }
        });

        inputEl.addEventListener('input', () => {
            scheduleFetch(false);
        });

        panel.addEventListener('scroll', () => {
            const threshold = 40;
            if (panel.scrollTop + panel.clientHeight >= panel.scrollHeight - threshold) {
                fetchMoreSuggestions();
            }
        });

        window.addEventListener('resize', () => {
            if (!panel.classList.contains('hidden')) updatePanelMaxHeight();
        });

        document.addEventListener('click', (e) => {
            if (e.target === inputEl) return;
            if (panel.contains(e.target)) return;
            closePanel();
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closePanel();
        });
    }

    function showPreviewModal() {
        const modal = document.getElementById('preview-modal');
        if (!modal) return;
        populatePreviewFields();
        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }

    function hidePreviewModal() {
        const modal = document.getElementById('preview-modal');
        if (!modal) return;
        modal.classList.add('hidden');
        document.body.style.overflow = '';
    }

    function populatePreviewFields() {
        const form = document.getElementById('savings-application-form');
        if (!form) return;

        const formData = new FormData(form);

        const useExistingDocsEl = document.getElementById('use_existing_documents');
        const useExistingDocsChecked = !!(useExistingDocsEl && useExistingDocsEl.checked);
        const canReusePanCard = !!(useExistingDocsEl && (useExistingDocsEl.dataset.reusablePanCard || '') === '1');
        const canReuseIdProofBack = !!(useExistingDocsEl && (useExistingDocsEl.dataset.reusableIdProofBack || '') === '1');
        const canReuseIdProof = !!(useExistingDocsEl && (useExistingDocsEl.dataset.reusableIdProof || '') === '1');
        const canReusePhoto = !!(useExistingDocsEl && (useExistingDocsEl.dataset.reusablePhoto || '') === '1');
        const canReuseSignature = !!(useExistingDocsEl && (useExistingDocsEl.dataset.reusableSignature || '') === '1');
        const previewUseExisting = document.getElementById('preview_use_existing_documents');
        if (previewUseExisting) previewUseExisting.value = useExistingDocsChecked ? 'Yes' : 'No';

        const sameAddressCheckbox = document.getElementById('same-address');
        const isSameAddress = !!(sameAddressCheckbox && sameAddressCheckbox.checked);
        if (sameAddressCheckbox && sameAddressCheckbox.checked) {
            formData.set('current_address_line_1', formData.get('address_line_1'));
            formData.set('current_address_line_2', formData.get('address_line_2'));
            formData.set('current_landmark', formData.get('landmark'));
            formData.set('current_post_office', formData.get('post_office'));
            formData.set('current_city_or_town', formData.get('city_or_town'));
            formData.set('current_district', formData.get('district'));
            formData.set('current_state', formData.get('state'));
            formData.set('current_country', formData.get('country'));
            formData.set('current_post_code', formData.get('post_code'));

            formData.delete('residential_proof_type');
            formData.delete('residential_proof_file');
        }

        const currentSection = document.getElementById('current-address-preview-section');
        const currentSameNote = document.getElementById('current-address-same-note');
        const proofSection = document.getElementById('residential-proof-preview-section');
        if (currentSection) currentSection.style.display = isSameAddress ? 'none' : '';
        if (proofSection) proofSection.style.display = isSameAddress ? 'none' : '';
        if (currentSameNote) currentSameNote.style.display = isSameAddress ? '' : 'none';

        for (const [fieldName, value] of formData.entries()) {
            const previewField = document.getElementById('preview_' + fieldName);
            if (previewField) {
                if (
                    fieldName.includes('_proof') ||
                    fieldName === 'photo' ||
                    fieldName === 'signature' ||
                    fieldName === 'id_proof' ||
                    fieldName === 'pan_card_document' ||
                    fieldName === 'id_proof_back' ||
                    fieldName === 'residential_proof_file' ||
                    fieldName === 'nominee_kyc_document'
                ) {
                    const fileInput = document.getElementById(fieldName);
                    if (fileInput && fileInput.type === 'file' && fileInput.files && fileInput.files.length > 0) {
                        previewField.value = fileInput.files[0].name;
                    } else {
                        const coreExistingDocsFields = ['id_proof', 'pan_card_document', 'photo', 'signature'];
                        if (useExistingDocsChecked && coreExistingDocsFields.includes(fieldName)) {
                            if (fieldName === 'pan_card_document' && !canReusePanCard) {
                                previewField.value = 'No file selected';
                            } else {
                                previewField.value = 'Using existing documents';
                            }
                        } else if (useExistingDocsChecked && fieldName === 'id_proof_back') {
                            previewField.value = canReuseIdProofBack ? 'Using existing documents' : 'No file selected';
                        } else {
                            previewField.value = 'No file selected';
                        }
                    }
                } else {
                    previewField.value = value || '';
                }
            }
        }

        const panPreview = document.getElementById('preview_pan_card_document');
        const panInput = document.getElementById('pan_card_document');
        if (panPreview && panInput && panInput.type === 'file') {
            if (panInput.files && panInput.files.length > 0) {
                panPreview.value = panInput.files[0].name;
            } else if (useExistingDocsChecked && canReusePanCard) {
                panPreview.value = 'Using existing documents';
            } else {
                panPreview.value = 'No file selected';
            }
        }

        const syncFilePreview = (fieldName, canReuse) => {
            const previewEl = document.getElementById('preview_' + fieldName);
            const inputEl = document.getElementById(fieldName);
            if (!previewEl || !inputEl || inputEl.type !== 'file') return;

            if (inputEl.files && inputEl.files.length > 0) {
                previewEl.value = inputEl.files[0].name;
                return;
            }

            if (useExistingDocsChecked && canReuse) {
                previewEl.value = 'Using existing documents';
            } else {
                previewEl.value = 'No file selected';
            }
        };

        syncFilePreview('id_proof', canReuseIdProof);
        syncFilePreview('photo', canReusePhoto);
        syncFilePreview('signature', canReuseSignature);
        syncFilePreview('id_proof_back', canReuseIdProofBack);

        const selectFields = ['gender', 'residential_proof_type', 'saving_type', 'saving_product'];
        selectFields.forEach(fieldName => {
            const field = document.getElementById(fieldName);
            const previewFieldId = fieldName === 'saving_product' ? 'preview_saving_product' : ('preview_' + fieldName);
            const previewField = document.getElementById(previewFieldId);
            if (field && previewField && field.tagName === 'SELECT') {
                const selectedOption = field.options[field.selectedIndex];
                if (fieldName === 'saving_product' && selectedOption && selectedOption.value) {
                    const ds = selectedOption.dataset || {};
                    if (ds.amount || ds.interest || ds.tenure || ds.frequency) {
                        const amount = ds.amount ? `₹${ds.amount}` : '';
                        const freq = (ds.frequency || '').trim();
                        const amountPart = freq ? `${amount} (${freq})`.trim() : (amount || '');
                        const interestPart = ds.interest ? `${ds.interest}%` : '';
                        const tenurePart = ds.tenure ? ds.tenure : '';
                        const parts = [amountPart, interestPart, tenurePart].filter(Boolean);
                        previewField.value = parts.length ? parts.join(' - ') : (selectedOption.text || '');
                    } else {
                        previewField.value = selectedOption.text || '';
                    }
                } else {
                    previewField.value = selectedOption ? selectedOption.text : '';
                }
            }
        });
    }

    function setupPreviewModal() {
        const closeBtn = document.getElementById('close-preview-x');
        if (closeBtn) closeBtn.addEventListener('click', hidePreviewModal);

        const cancelBtn = document.getElementById('close-preview');
        if (cancelBtn) cancelBtn.addEventListener('click', hidePreviewModal);

        const submitBtn = document.getElementById('submit-preview');
        if (submitBtn) {
            submitBtn.addEventListener('click', function () {
                const form = document.getElementById('savings-application-form');
                if (!form) return;
                if (typeof form.requestSubmit === 'function') {
                    form.requestSubmit();
                } else {
                    const evt = new Event('submit', { bubbles: true, cancelable: true });
                    form.dispatchEvent(evt);
                }
                hidePreviewModal();
            });
        }

        const modal = document.getElementById('preview-modal');
        if (modal) {
            modal.addEventListener('click', function (e) {
                if (e.target === modal) {
                    hidePreviewModal();
                }
            });
        }

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                hidePreviewModal();
            }
        });

        const continueBtn = document.getElementById('continue-btn');
        if (continueBtn) {
            continueBtn.addEventListener('click', function (e) {
                e.preventDefault();
                const form = document.getElementById('savings-application-form');
                if (!form) return;

                if (!validateAllFields()) {
                    const firstError = form.querySelector('.border-red-500');
                    if (firstError) firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    return false;
                }
                showPreviewModal();
            });
        }
    }

    window.toggleAmountFields = toggleAmountFields;
    window.setFieldValue = setFieldValue;

    document.addEventListener('DOMContentLoaded', function () {
        (function initializeCleanState() {
            document.querySelectorAll('[id^="error-"]').forEach(el => el.textContent = '');
            document.querySelectorAll('.border-red-500').forEach(el => el.classList.remove('border-red-500'));
            touchedFields.clear();
            window._showAllErrors = false;

            ['nominee_kyc_type', 'nominee_kyc_number', 'nominee_kyc_document', 'photo', 'signature'].forEach((id) => {
                const el = document.getElementById(id);
                if (el && el.hasAttribute && el.hasAttribute('required')) el.removeAttribute('required');
            });
        })();

        attachInstantValidation();
        setupTitleCaseInputs();
        setupUppercaseInputs();
        setupAadhaarFormatting();
        setupNomineeKycTypeDrivenFormatting();
        setupDobFlatpickr();
        setupSavingProductCustomDropdown();
        if (window.loadSavingsMasterData) setupMasterDrivenProductDetails();
        if (window.fetchAddressFromPincode) {
            setupPincodeAutoFill();
            setupSameAddressToggle();
            setupAddressManualEditTracking();
        }
        bindLookupButton();
        setupExistingCustomerSuggestions();
        setupPreviewModal();
    });
})();
