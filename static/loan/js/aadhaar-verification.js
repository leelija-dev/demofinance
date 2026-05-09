// Aadhaar OTP Verification and Data Management
class AadhaarVerification {
    constructor() {
        this.otpSent = false;
        this.verified = false;
        this.countdown = 0;
        this.otpInputs = [];
        this.verificationData = {
            aadhaar: '',
            mobile: ''
        };
        this.personalData = {};
        this.init();
    }

    init() {
        this.setupOTPInputs();
        this.setupEventListeners();
        this.updateAadhaarInputState();
    }

    updateAadhaarInputState() {
        const aadhaarInput = document.getElementById('aadhaar-number');
        if (!aadhaarInput) {
            return;
        }

        const isMobileValid = /^[6-9]\d{9}$/.test(this.verificationData.mobile || '');
        aadhaarInput.disabled = !isMobileValid;

        if (!isMobileValid) {
            aadhaarInput.value = '';
            this.verificationData.aadhaar = '';
            this.clearError('aadhaar');
            this.updateSendButtonState();
        }
    }

    setupOTPInputs() {
        // Get all OTP input elements
        this.otpInputs = document.querySelectorAll('.otp-input');

        this.otpInputs.forEach((input, index) => {
            input.addEventListener('input', (e) => this.handleOTPInput(e, index));
            input.addEventListener('keydown', (e) => this.handleOTPKeydown(e, index));
            input.addEventListener('paste', (e) => this.handleOTPPaste(e));
        });
    }

    mockAadhaarVerification() {
        this.personalData = {
            '@entity': 'in.co.sandbox.kyc.aadhaar.okyc',
            'reference_id': 72585191,
            'status': 'VALID',
            'message': 'Aadhaar Card Exists',
            'care_of': '',
            'full_address': 'Daulatabad, Daulatabad, Daulatabad, Murshidabad, West Bengal, India, 742302',
            'date_of_birth': '19-10-2002',
            'email_hash': '',
            'gender': 'M',
            'name': 'Sahil Kabir',
            'address': {
                '@entity': 'in.co.sandbox.kyc.aadhaar.okyc.address',
                'country': 'India',
                'district': 'Murshidabad',
                'house': '',
                'landmark': 'Daulatabad',
                'pincode': 742302,
                'post_office': 'Daulatabad',
                'state': 'West Bengal',
                'street': 'Test Street',
                'subdistrict': 'Test Sub District',
                'vtc': 'Daulatabad'
            },
            'year_of_birth': 1998,
            'mobile_hash': '32f570e493cc32d02565aa5f1cff567c612ba279d92ac6a060e160ad69b26465',
            // 'photo': 'data:image/png;base64,<your photo data>',
            'share_code': '2345'
        };
        this.verified = true;
        // Mock Aadhaar verification - just show success and populate data
        this.populatePersonalInfo();
        // this.hideOTPSection();
        // Automatically move to next step after successful verification
        this.showSuccess('Aadhaar verified successfully! Moving to next step...');
        setTimeout(() => {
            this.moveToNextStep();
        }, 1500);
    }

    setupEventListeners() {
        // Send OTP button
        const sendOTPBtn = document.getElementById('send-aadhaar-otp');
        if (sendOTPBtn) {
            // sendOTPBtn.addEventListener('click', () => this.sendOTP());
            sendOTPBtn.addEventListener('click', () => this.mockAadhaarVerification());
        }

        // Close OTP modal button
        const closeOtpModalBtn = document.getElementById('close-aadhaar-otp-modal');
        if (closeOtpModalBtn) {
            closeOtpModalBtn.addEventListener('click', () => this.hideOTPSection());
        }

        // Verify OTP button
        const verifyOTPBtn = document.getElementById('verify-aadhaar-otp');
        if (verifyOTPBtn) {
            verifyOTPBtn.addEventListener('click', () => this.verifyOTP());
        }

        // Aadhaar input field
        const aadhaarInput = document.getElementById('aadhaar-number');
        if (aadhaarInput) {
            aadhaarInput.addEventListener('input', (e) => this.handleAadhaarInput(e));
        }

        // Mobile input field
        const mobileInput = document.getElementById('mobile-number');
        if (mobileInput) {
            mobileInput.addEventListener('input', (e) => this.handleMobileInput(e));
        }
    }



    handleAadhaarInput(e) {
        let digits = e.target.value.replace(/\D/g, '');
        if (digits.length > 12) {
            digits = digits.slice(0, 12);
        }

        const formatted = (digits.match(/.{1,4}/g) || []).join(' ');
        e.target.value = formatted;
        this.verificationData.aadhaar = digits;

        // Update send button state
        this.updateSendButtonState();

        // Clear error
        this.clearError('aadhaar');
    }

    // handleAadhaarInput(e) {
    //     let value = e.target.value.replace(/\D/g, '');
    //     if (value.length > 12) {
    //         value = value.slice(0, 12);
    //     }
    //     e.target.value = value;
    //     this.verificationData.aadhaar = value;

    //     // Clear previous verification if Aadhaar changes (only if already verified)
    //     if (this.verified && this.verificationData.aadhaar.length === 12) {
    //         // Only reset if user had completed verification and then changed the number
    //         this.resetVerification();
    //     }

    //     // Update send button state
    //     this.updateSendButtonState();
    // }










    populatePersonalInfo() {
        // Extract data from API response
        const data = this.personalData;

        const addressData = data.address || {};

        // Populate personal info fields with Aadhaar data
        const personalFields = {
            'full_name': data.name,
            'father_name': data.care_of && data.care_of.replace(/^S\/O\s*:/, '').trim(),
            'date_of_birth': data.date_of_birth,
            'gender': data.gender,
            'address': data.full_address || `${addressData.house || ''}, ${addressData.street || ''}`.trim(),
            'pincode': addressData.pincode
        };

        // Update DOM fields by ID
        Object.entries(personalFields).forEach(([fieldId, value]) => {
            const field = document.getElementById(fieldId);
            if (field && value) {
                field.value = value;
                // Trigger change event for any dependent logic
                field.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });

        // Also update Alpine.js personalInfo object if it exists
        if (window.Alpine) {
            // Find the Alpine.js loanApplication component
            const appElement = document.querySelector('[x-data*="loanApplication"]');
            if (appElement) {
                const alpineData = Alpine.$data(appElement);
                if (alpineData && alpineData.personalInfo) {
                    // Track which fields are populated by Aadhaar
                    const aadhaarPopulatedFields = {};

                    // Update Alpine.js personalInfo object and track populated fields
                    if (personalFields.full_name) {
                        alpineData.personalInfo.full_name = personalFields.full_name;
                        aadhaarPopulatedFields.full_name = true;
                    }
                    if (personalFields.father_name) {
                        alpineData.personalInfo.father_name = personalFields.father_name;
                        aadhaarPopulatedFields.father_name = true;
                    }
                    if (personalFields.date_of_birth) {
                        alpineData.personalInfo.date_of_birth = personalFields.date_of_birth;
                        aadhaarPopulatedFields.date_of_birth = true;
                    }
                    if (personalFields.gender) {
                        alpineData.personalInfo.gender = personalFields.gender;
                        aadhaarPopulatedFields.gender = true;
                    }
                    if (personalFields.address) {
                        alpineData.personalInfo.address = personalFields.address;
                        aadhaarPopulatedFields.address = true;
                    }
                    if (personalFields.pincode) {
                        alpineData.personalInfo.pincode = personalFields.pincode;
                        aadhaarPopulatedFields.pincode = true;
                    }

                    // Store the populated fields tracking
                    alpineData.aadhaarPopulatedFields = aadhaarPopulatedFields;

                    console.log('Updated Alpine.js personalInfo:', alpineData.personalInfo);
                    console.log('Aadhaar populated fields:', aadhaarPopulatedFields);
                }
            }
        }

        // Populate address fields with Aadhaar data
        this.populateAddressFields();

        // Handle photo if available
        this.populatePhoto(data.photo);

        // Sync with Alpine.js personalInfo object
        console.log('this.syncWithAlpineJS()');
        this.syncWithAlpineJS();

        // Update hidden fields
        const hiddenAadhaar = document.getElementById('hidden-aadhaar');
        if (hiddenAadhaar) {
            hiddenAadhaar.value = this.verificationData.aadhaar;
        }
    }

    handleMobileInput(e) {
        let value = e.target.value.replace(/\D/g, '');
        if (value.length > 10) {
            value = value.slice(0, 10);
        }
        e.target.value = value;
        this.verificationData.mobile = value;

        this.updateAadhaarInputState();

        // Clear error
        this.clearError('mobile');
    }

    handleOTPInput(e, index) {
        const input = e.target;
        const value = input.value;

        if (value.length === 1) {
            // Move to next input
            if (index < this.otpInputs.length - 1) {
                this.otpInputs[index + 1].focus();
            }
        } else if (value.length > 1) {
            // Handle paste or multiple digits
            input.value = value.slice(0, 1);
            if (index < this.otpInputs.length - 1) {
                this.otpInputs[index + 1].focus();
            }
        }

        // Auto-verify when all digits are entered
        if (this.isAllOTPFieldsFilled()) {
            setTimeout(() => this.verifyOTP(), 100);
        }
    }

    handleOTPKeydown(e, index) {
        if (e.key === 'Backspace' && e.target.value === '') {
            // Move to previous input
            if (index > 0) {
                this.otpInputs[index - 1].focus();
            }
        }
    }

    handleOTPPaste(e) {
        e.preventDefault();
        const pastedData = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);

        // Distribute pasted digits across inputs
        for (let i = 0; i < Math.min(pastedData.length, this.otpInputs.length); i++) {
            this.otpInputs[i].value = pastedData[i];
        }

        // Auto-verify if all digits are filled
        if (this.isAllOTPFieldsFilled()) {
            setTimeout(() => this.verifyOTP(), 100);
        }
    }

    isAllOTPFieldsFilled() {
        return Array.from(this.otpInputs).every(input => input.value.length === 1);
    }

    getOTPValue() {
        return Array.from(this.otpInputs).map(input => input.value).join('');
    }

    async sendOTP(continueWithExistingCustomer = false) {
        console.log('continueWithExistingCustomer  ->  ', continueWithExistingCustomer)
        if (!this.validateAadhaar()) {
            return;
        }

        const sendBtn = document.getElementById('send-aadhaar-otp');
        const originalText = sendBtn.textContent;

        try {
            // Show loading state
            sendBtn.disabled = true;
            sendBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Sending...';

            const response = await fetch('/agent/api/send-aadhaar-otp/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    aadhaar: this.verificationData.aadhaar,
                    continue_with_existing_customer: continueWithExistingCustomer,
                    application_source: (window.location && window.location.pathname && window.location.pathname.includes('new-application-cards')) ? 'new-application-cards' : ''
                })
            });

            const data = await response.json();
            console.log(data);
            console.log(data.success);

            if (data.success) {
                if (data.customer_exists) {
                    // Show customer details popup
                    this.showCustomerDetailsPopup(data.customer_data, data.loan_history, data.customer_blocked);
                } else {
                    // Proceed with OTP verification
                    this.otpSent = true;
                    this.showSuccess('OTP sent to your Aadhaar-linked mobile number');
                    this.startCountdown();
                    this.showOTPSection();
                }
            } else {
                const isNewApplicationCardsFlow = window.location && window.location.pathname && window.location.pathname.includes('new-application-cards');
                if (isNewApplicationCardsFlow && data.code === 'RUNNING_LOAN') {
                    if (typeof window.showToast === 'function') {
                        window.showToast(data.message || 'This customer cannot apply for a new loan because there is already a running loan.', 'error');
                    }
                    return;
                }
                this.showError('aadhaar', data.message || 'Failed to send OTP');
            }
        } catch (error) {
            console.error('Send OTP error:', error);
            this.showError('aadhaar', 'Network error. Please try again.');
        } finally {
            // Restore button state
            sendBtn.disabled = false;
            sendBtn.textContent = originalText;
        }
    }

    async verifyOTP() {
        const otp = this.getOTPValue();

        if (otp.length !== 6) {
            this.showError('aadhaar_otp', 'Please enter 6-digit OTP');
            return;
        }

        const verifyBtn = document.getElementById('verify-aadhaar-otp');
        const originalText = verifyBtn.textContent;

        try {
            // Show loading state
            verifyBtn.disabled = true;
            verifyBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Verifying...';

            const response = await fetch('/agent/api/verify-aadhaar-otp/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    aadhaar: this.verificationData.aadhaar,
                    otp: otp
                })
            });

            const data = await response.json();

            if (data.success) {
                this.personalData = data.aadhaar_data || {};
                if(this.personalData.message != null && this.personalData.message != 'Invalid OTP'){
                    this.verified = true;
                    this.showSuccess('Aadhaar verified successfully! Moving to next step...');
                    this.populatePersonalInfo();
                    this.hideOTPSection();
                    // Automatically move to next step after successful verification
                    setTimeout(() => {
                        this.moveToNextStep();
                    }, 1500);
                } else {
                    this.verified = false;
                    this.showError('aadhaar_otp', 'Invalid OTP. Please enter correct OTP.');
                    this.clearOTPInputs();
                }
            } else {
                this.verified = false;
                this.showError('aadhaar_otp', (data && data.message ? data.message : 'Invalid OTP') + '. Please enter correct OTP.');
                this.clearOTPInputs();
            }
        } catch (error) {
            console.error('Verify OTP error:', error);
            this.verified = false;
            this.showError('aadhaar_otp', 'Network error. Please try again.');
        } finally {
            // Restore button state
            verifyBtn.disabled = false;
            verifyBtn.textContent = originalText;
        }
    }

    populatePhoto(photoData) {
        if (photoData) {
            console.log('Photo data available:', photoData);

            // Get the Alpine.js component and set the photo
            const appElement = document.querySelector('[x-data*="loanApplication"]');
            if (appElement) {
                const alpineData = Alpine.$data(appElement);
                if (alpineData) {
                    alpineData.aadhaarPhoto = "data:image/jpeg;base64," + photoData;
                    console.log('Aadhaar photo set in Alpine.js data');
                }
            }
        }
    }

    populateAddressFields() {
        // Extract data from API response
        const data = this.personalData;
        const addressData = data.address || {};

        const cleanAddressPart = (value) => {
            const v = String(value ?? '').trim();
            if (!v || v === '_' || v === '-') return '';
            return v;
        };

        const house = cleanAddressPart(addressData.house);
        const street = cleanAddressPart(addressData.street);
        const vtc = cleanAddressPart(addressData.vtc);
        const addressLine1FromParts = [house, street].filter(Boolean).join(', ').trim();
        const addressLine1 = /[a-zA-Z0-9]/.test(addressLine1FromParts) ? addressLine1FromParts : vtc;

        // Populate permanent address fields with Aadhaar data
        const addressFields = {
            // 'address_line_1': `${addressData.house || ''}, ${addressData.street || ''}`.trim(),
            'address_line_1': addressLine1,
            'post_code': addressData.pincode,
            'city_or_town': addressData.vtc || addressData.district,
            'district': addressData.district,
            'state': addressData.state,
            'country': addressData.country || 'India'
        };

        // Update DOM fields by ID
        Object.entries(addressFields).forEach(([fieldId, value]) => {
            const field = document.getElementById(fieldId);
            if (field && value) {
                field.value = value;
                // Trigger change event for any dependent logic
                field.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });

        // Also update Alpine.js addressData object if it exists
        if (window.Alpine) {
            // Find the Alpine.js loanApplication component
            const appElement = document.querySelector('[x-data*="loanApplication"]');
            if (appElement) {
                const alpineData = Alpine.$data(appElement);
                if (alpineData && alpineData.addressData && alpineData.addressData.permanent) {
                    // Update Alpine.js addressData.permanent object
                    alpineData.addressData.permanent.address_line_1 = addressFields.address_line_1 || '';
                    alpineData.addressData.permanent.post_code = addressData.pincode || '';
                    alpineData.addressData.permanent.city_or_town = addressData.district || addressData.vtc || '';
                    alpineData.addressData.permanent.district = addressData.district || '';
                    alpineData.addressData.permanent.state = addressData.state || '';
                    alpineData.addressData.permanent.country = addressData.country || 'India';
                    alpineData.addressData.permanent.post_office = addressData.post_office || '';
                    alpineData.addressData.permanent.landmark = addressData.landmark || '';

                    console.log('Updated Alpine.js addressData.permanent:', alpineData.addressData.permanent);
                    Object.assign(alpineData.addressData.current, alpineData.addressData.permanent);
                }
            }
        }

        // Also populate the personal info address field for consistency
        const personalAddressField = document.getElementById('address');
        const fullAddress = `${addressData.house || ''}, ${addressData.street || ''}, ${addressData.district || ''}, ${addressData.state || ''} - ${addressData.pincode || ''}`.trim();
        if (personalAddressField) {
            personalAddressField.value = fullAddress;
            personalAddressField.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    syncWithAlpineJS() {
        // Check if Alpine.js loanApplication component exists
        console.log("Check if Alpine.js loanApplication component exists ---- ",window.Alpine && window.Alpine.$data);
        console.log(window.Alpine)
        console.log(window.Alpine.$data)        
        if (window.Alpine && window.Alpine.$data) {
            // Find the loanApplication component
            console.log("Find the loanApplication component")
            const appElement = document.querySelector('[x-data*="loanApplication"]');
            if (appElement) {
                const alpineData = Alpine.$data(appElement);
                if (alpineData && alpineData.personalInfo) {
                    // Extract data from API response
                    console.log("Extract data from API response");
                    const data = this.personalData;
                    const addressData = data.address || {};

                    // Update Alpine.js personalInfo object
                    console.log("Update Alpine.js personalInfo object");
                    alpineData.personalInfo = {
                        ...alpineData.personalInfo,
                        full_name: data.name || '',
                        father_name: data.care_of || '',
                        date_of_birth: data.date_of_birth || '',
                        gender: data.gender || '',
                        address: data.full_address || `${addressData.house || ''}, ${addressData.street || ''}`.trim(),
                        pincode: addressData.pincode || ''
                    };

                    // Update Alpine.js addressData object
                    console.log("Update Alpine.js addressData object")
                    if (alpineData.addressData) {
                        alpineData.addressData.permanent = {
                            ...alpineData.addressData.permanent,
                            address_line_1: `${addressData.house || ''}, ${addressData.street || ''}`.trim(),
                            post_code: addressData.pincode || '',
                            city_or_town: addressData.district || addressData.vtc,
                            district: addressData.district,
                            state: addressData.state,
                            country: addressData.country || 'India'
                        };

                        // If same address is checked, also update current address
                        console.log("If same address is checked, also update current address");
                        if (alpineData.addressData.sameAddress) {
                            alpineData.addressData.current = {
                                ...alpineData.addressData.current,
                                address_line_1: `${addressData.house || ''}, ${addressData.street || ''}`.trim(),
                                post_code: addressData.pincode || '',
                                city_or_town: addressData.district || addressData.vtc,
                                district: addressData.district,
                                state: addressData.state,
                                country: addressData.country || 'India'
                            };
                        }
                    }
                }

                // Update verification data in Alpine.js
                console.log("Update verification data in Alpine.js");
                if (alpineData.verificationData) {
                    alpineData.verificationData.aadhaar = this.verificationData.aadhaar;
                    alpineData.verificationData.mobile = this.verificationData.mobile;
                }

                // Set OTP verified status
                alpineData.otpVerified = this.verified === true;
                console.log("alpineData.otpVerified ---- ",this.verified);

                // Trigger Alpine reactivity
                Alpine.$data(appElement);
            }
        }
    }

    isVerified() {
        return this.verified === true;
    }

    startCountdown() {
        this.countdown = 120;
        const countdownElement = document.getElementById('otp-countdown');

        const interval = setInterval(() => {
            this.countdown--;
            if (countdownElement) {
                countdownElement.textContent = this.countdown;
            }

            if (this.countdown <= 0) {
                clearInterval(interval);
                this.enableResend();
            }
        }, 1000);
    }

    enableResend() {
        const sendBtn = document.getElementById('send-aadhaar-otp');
        if (sendBtn) {
            sendBtn.disabled = false;
            sendBtn.textContent = 'Resend OTP';
        }
    }

    hideOTPSection() {
        const otpModal = document.getElementById('aadhaarOtpModal');
        const otpSection = document.getElementById('otp-section');

        if (otpModal) {
            otpModal.classList.add('hidden');
        }
        if (otpSection) {
            otpSection.style.display = 'none';
            otpSection.classList.add('hidden');
        }

        this.clearOTPInputs();
        this.clearError('aadhaar_otp');
    }


    moveToNextStep() {
        console.log('Start moveToNextStep ------------------------------------------------');
        // Find the Alpine.js loanApplication component and trigger nextStep
        const appElement = document.querySelector('[x-data*="loanApplication"]');
        console.log('appElement ------------------------------------------------');
        if (appElement && window.Alpine) {
            console.log('appElement && window.Alpine ------------------------------------------------');
            const alpineData = Alpine.$data(appElement);
            console.log('alpineData ------------------------------------------------');
            if (alpineData && alpineData.nextStep) {
                console.log('alpineData && alpineData.nextStep ------------------------------------------------');
                alpineData.nextStep();
                console.log('alpineData.nextStep ------------------------------------------------');
            }
        }
    }

    updateSendButtonState() {
        const sendBtn = document.getElementById('send-aadhaar-otp');
        if (sendBtn) {
            sendBtn.disabled = this.verificationData.aadhaar.length !== 12;
        }
    }
    showOTPSection() {
        const otpModal = document.getElementById('aadhaarOtpModal');
        const otpSection = document.getElementById('otp-section');

        if (otpModal) {
            otpModal.classList.remove('hidden');
        }
        if (otpSection) {
            otpSection.style.display = 'block';
            otpSection.classList.remove('hidden');
        }

        if (this.otpInputs && this.otpInputs.length > 0) {
            this.otpInputs[0].focus();
        }
    }

    validateAadhaar() {
        if (!this.verificationData.aadhaar) {
            this.showError('aadhaar', 'Please enter Aadhaar number');
            return false;
        }

        if (!/^\d{12}$/.test(this.verificationData.aadhaar)) {
            this.showError('aadhaar', 'Please enter a valid 12-digit Aadhaar number');
            return false;
        }

        this.clearError('aadhaar');
        return true;
    }

    clearOTPInputs() {
        this.otpInputs.forEach(input => {
            input.value = '';
        });
        if (this.otpInputs.length > 0) {
            this.otpInputs[0].focus();
        }
    }

    resetVerification() {
        this.verified = false;
        this.otpSent = false;
        this.countdown = 0;
        this.clearOTPInputs();
        this.hideOTPSection();
        this.clearError('aadhaar_otp');
    }

    showError(field, message) {
        const errorElement = document.getElementById(`error-${field}`);
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.classList.add('text-red-600');
        }

        // Add error class to input field
        const inputField = document.getElementById(field);
        if (inputField) {
            inputField.classList.add('border-red-500');
        }
    }

    clearError(field) {
        const errorElement = document.getElementById(`error-${field}`);
        if (errorElement) {
            errorElement.textContent = '';
            errorElement.classList.remove('text-red-600');
        }

        // Remove error class from input field
        const inputField = document.getElementById(field);
        if (inputField) {
            inputField.classList.remove('border-red-500');
        }
    }

    getCSRFToken() {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        return csrfToken ? csrfToken.value : '';
    }

    showSuccess(message) {
        // Simple success message - you can customize this
        console.log('Success:', message);
        // You could also use a toast notification or update UI
    }

    showCustomerDetailsPopup(customerData, loanHistory, customer_blocked) {
        const canProceedWithCustomer = !!customer_blocked;
        // Create modal HTML
        const modalHtml = `
            <div id="customer-details-modal" class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-9999">
                <div class="relative top-20 mx-auto p-4 border w-36 max-w-lg shadow-lg rounded-lg bg-white">
                    <div class="mt-3">
                        <div class="flex items-center justify-between mb-4">
                            <h3 class="text-lg font-medium text-gray-900">Existing Customer Found</h3>
                            <button id="close-customer-modal" class="text-gray-400 hover:text-gray-600">
                                <span class="sr-only">Close</span>
                                <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                                </svg>
                            </button>
                        </div>
                        
                        <div class="grid grid-cols-1 gap-6">
                            <!-- Customer Information with Photo -->
                            <div class="space-y-4">
                                <div class="flex items-center justify-between">
                                    <span class="text-sm font-medium text-gray-600">Customer ID:</span>
                                    <span class="text-sm text-gray-900">${customerData.customer_id}</span>
                                </div>
                                <div class="flex items-center justify-between">
                                    <span class="text-sm font-medium text-gray-600">Full Name:</span>
                                    <span class="text-sm text-gray-900">${customerData.full_name}</span>
                                </div>
                                <div class="flex items-center justify-between">
                                    <span class="text-sm font-medium text-gray-600">Father Name:</span>
                                    <span class="text-sm text-gray-900">${customerData.father_name || 'N/A'}</span>
                                </div>
                                <div class="flex items-center justify-between">
                                    <span class="text-sm font-medium text-gray-600">Date of Birth:</span>
                                    <span class="text-sm text-gray-900">${customerData.date_of_birth || 'N/A'}</span>
                                </div>
                                <div class="flex items-center justify-between">
                                    <span class="text-sm font-medium text-gray-600">Gender:</span>
                                    <span class="text-sm text-gray-900">${customerData.gender || 'N/A'}</span>
                                </div>
                                <div class="flex items-center justify-between">
                                    <span class="text-sm font-medium text-gray-600">Contact:</span>
                                    <span class="text-sm text-gray-900">${customerData.contact || 'N/A'}</span>
                                </div>
                                <div class="flex items-center justify-between">
                                    <span class="text-sm font-medium text-gray-600">Email:</span>
                                    <span class="text-sm text-gray-900">${customerData.email || 'N/A'}</span>
                                </div>
                                <div class="flex items-center justify-between">
                                    <span class="text-sm font-medium text-gray-600">Guarantor Name:</span>
                                    <span class="text-sm text-gray-900">${customerData.guarantor_name || 'N/A'}</span>
                                </div>
                                <div class="flex items-center justify-between">
                                    <span class="text-sm font-medium text-gray-600">Aadhaar Number:</span>
                                    <span class="text-sm text-gray-900">${customerData.aadhar_number}</span>
                                </div>
                                <div class="flex items-center justify-between">
                                    <span class="text-sm font-medium text-gray-600">PAN Number:</span>
                                    <span class="text-sm text-gray-900">${customerData.pan_number || 'N/A'}</span>
                                </div>
                            </div>
                            <div class="space-y-4">
                                <h4 class="text-md font-semibold text-gray-800 mb-3">Loan History</h4>
                                <div class="space-y-2 max-h-48 overflow-y-auto">
                                    ${loanHistory.length > 0 ?
                loanHistory.map(loan => `
                                                <div class="bg-gray-50 p-3 rounded border">
                                                    <div class="flex items-center justify-between mb-2">
                                                        <span class="text-sm font-medium text-gray-700">${loan.loan_ref_no}</span>
                                                        <span class="text-xs px-2 py-1 rounded-full ${loan.status === 'disbursed' ? 'bg-green-100 text-green-800' :
                        loan.status === 'active' ? 'bg-blue-100 text-blue-800' :
                            loan.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                                'bg-gray-100 text-gray-800'
                    }">${loan.status}</span>
                                                    </div>
                                                    <div class="text-xs text-gray-600 space-y-1">
                                                        <div>Submitted: ${loan.submitted_at || 'N/A'}</div>
                                                        ${loan.approved_at ? `<div>Approved: ${loan.approved_at}</div>` : ''}
                                                        ${loan.disbursed_at ? `<div>Disbursed: ${loan.disbursed_at}</div>` : ''}
                                                    </div>
                                                </div>
                                            `).join('')
                : '<p class="text-sm text-gray-500">No loan history found</p>'
            }
                                </div>
                            </div>
                            <div> ${canProceedWithCustomer ? 'Do you want to proceed with this customer?' : 'An loan is already active for this customer.'} </div>
                            ${canProceedWithCustomer ? `<div class="flex items-center justify-between">
                                <button id="proceed-with-customer" class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
                                    Yes
                                </button>
                                <button id="cancel-customer-modal" class="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500">
                                    No
                                </button>
                            </div>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Add modal to body
        document.body.insertAdjacentHTML('afterend', modalHtml);

        // Add event listeners
        document.getElementById('close-customer-modal').addEventListener('click', () => this.closeCustomerModal());
        const cancelBtn = document.getElementById('cancel-customer-modal');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.closeCustomerModal());
        }
        const proceedBtn = document.getElementById('proceed-with-customer');
        if (proceedBtn) {
            proceedBtn.addEventListener('click', () => {
                // Close the customer details modal first
                this.closeCustomerModal();
                // Populate data to Alpine variables
                this.populateExistingCustomerData(customerData);

                setTimeout(() => {
                    this.moveToNextStep();
                }, 1500);
            });
        }

        // Close modal on background click
        document.getElementById('customer-details-modal').addEventListener('click', (e) => {
            if (e.target.id === 'customer-details-modal') {
                this.closeCustomerModal();
            }
        });
    }

    closeCustomerModal() {
        const modal = document.getElementById('customer-details-modal');
        if (modal) {
            modal.remove();
        }
    }


    

    populateExistingCustomerData(customerData) {
        console.log('populateExistingCustomerData', customerData);
        // Get the Alpine.js component and populate data
        const appElement = document.querySelector('[x-data*="loanApplication"]');
        if (appElement && window.Alpine) {
            const alpineData = Alpine.$data(appElement);
            if (alpineData && alpineData.personalInfo) {
                // Populate personal info
                alpineData.personalInfo = {
                    ...alpineData.personalInfo,
                    full_name: customerData.full_name || '',
                    father_name: customerData.father_name || '',
                    date_of_birth: customerData.date_of_birth || '',
                    gender: customerData.gender || '',
                    contact: customerData.contact || '',
                    email: customerData.email || '',
                    pan_number: customerData.pan_number || '',
                    aadhaar_number: customerData.aadhar_number || '',
                    voter_number: customerData.voter_number || '',
                    guarantor_name: customerData.guarantor_name || '',
                    pincode: customerData.address_data?.post_code || '',
                };
                console.log(alpineData.personalInfo);

                // Populate address data if available
                if (customerData.address_data && alpineData.addressData && alpineData.addressData.permanent) {
                    alpineData.addressData.permanent = {
                        ...alpineData.addressData.permanent,
                        address_line_1: customerData.address_data.address_line_1 || '',
                        address_line_2: customerData.address_data.address_line_2 || '',
                        landmark: customerData.address_data.landmark || '',
                        city_or_town: customerData.address_data.city_or_town || '',
                        district: customerData.address_data.district || '',
                        state: customerData.address_data.state || '',
                        post_code: customerData.address_data.post_code || '',
                        country: customerData.address_data.country || ''
                    };
                    // Copy to current address if same address is checked
                    if (alpineData.addressData.sameAddress) {
                        Object.assign(alpineData.addressData.current, alpineData.addressData.permanent);
                    }

                    const existingFullAddress = `${alpineData.addressData.permanent.address_line_1}, ${alpineData.addressData.permanent.post_office}, ${alpineData.addressData.permanent.city_or_town}, ${alpineData.addressData.permanent.district}, ${alpineData.addressData.permanent.state} - ${alpineData.addressData.permanent.post_code}`.trim();
                    alpineData.personalInfo.address = existingFullAddress;
                }

                // Populate bank details if available
                if (customerData.bank_data && alpineData.bankDetails) {
                    alpineData.bankDetails = {
                        ...alpineData.bankDetails,
                        account_number: customerData.bank_data.account_number || '',
                        bank_name: customerData.bank_data.bank_name || '',
                        ifsc_code: customerData.bank_data.ifsc_code || '',
                        account_type: customerData.bank_data.account_type.toLowerCase() || ''
                    };
                }

                // Populate documents if available

                console.log('customerData.documents_data', customerData.documents_data)
                console.log('alpineData.documents', alpineData.documents)
                if (customerData.documents_data && alpineData.documents) {
                    this.handleFileOfExixtingCustomer(customerData.documents_data.guarantor_id_proof, 'guarantor_id_proof', alpineData.documents);
                    this.handleFileOfExixtingCustomer(customerData.documents_data.id_proof, 'id_proof', alpineData.documents);
                    this.handleFileOfExixtingCustomer(customerData.documents_data.id_proof_back, 'id_proof_back', alpineData.documents);
                    this.handleFileOfExixtingCustomer(customerData.documents_data.pan_card_document, 'pan_card', alpineData.documents);
                    this.handleFileOfExixtingCustomer(customerData.documents_data.photo, 'photo', alpineData.documents);
                    this.handleFileOfExixtingCustomer(customerData.documents_data.signature, 'signature', alpineData.documents);
                    this.handleFileOfExixtingCustomer(customerData.documents_data.income_proof, 'income_proof', alpineData.documents);
                }

                // Store photo data for display
                if (customerData.photo_data) {
                    alpineData.customerPhoto = customerData.photo_data;
                }

                // Set verification data
                if (alpineData.verificationData) {
                    alpineData.verificationData.aadhaar = customerData.aadhar_number;
                    alpineData.verificationData.mobile = customerData.contact;
                }

                // Set selected customer ID
                alpineData.selectedCustomerId = customerData.customer_id;

                // Mark as verified
                alpineData.otpVerified = true;
                alpineData.panVerificationStatus = 'linked';

                console.log('Populated existing customer data:', customerData);
            }
        }
    }
    handleFileOfExixtingCustomer(file, documentType, alpineDataDocuments) {
        // Helper function to convert base64 to File object
        function base64ToFile(base64, filename, mimeType) {
            const byteCharacters = atob(base64);
            const byteArrays = [];
            
            for (let offset = 0; offset < byteCharacters.length; offset += 512) {
                const slice = byteCharacters.slice(offset, offset + 512);
                const byteNumbers = new Array(slice.length);
                for (let i = 0; i < slice.length; i++) {
                    byteNumbers[i] = slice.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                byteArrays.push(byteArray);
            }
            
            const blob = new Blob(byteArrays, {type: mimeType});
            return new File([blob], filename, {type: mimeType});
        }

        if (file) {
            let fileObj;
            if (typeof file === 'string') {
                // Convert base64 string to File object, assuming JPEG format
                fileObj = base64ToFile(file, documentType + '.jpg', 'image/jpeg');
            } else {
                // Already a File object
                fileObj = file;
            }
            
            // Store file in documents object
            alpineDataDocuments[documentType] = fileObj;

            // Clear any existing error for this document type
            if (alpineDataDocuments.errors && alpineDataDocuments.errors[documentType]) {
                alpineDataDocuments.errors[documentType] = null;
            }

            console.log(`File populated: ${documentType}`, fileObj);
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function () {
    window.aadhaarVerification = new AadhaarVerification();
});

// Export for global access
window.AadhaarVerification = AadhaarVerification;
