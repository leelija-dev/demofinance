// Loan Application EMI Calculator
(function() {
    'use strict';
    
    // Interest rate mapping based on tenure
    // const tenureToInterest = {
    //     6: 10,
    //     12: 11,
    //     18: 12,
    //     24: 13,
    //     36: 14,
    //     48: 15,
    //     60: 16
    // };

    const tenureToInterest = 0;
    
    // EMI calculation function
    function calculateEMI(principal, rate, time, unit) {

        // console.log('time-',time)
        // console.log('unit-', unit)

        // const rate_of_interest = ((principal * rate / 100) / 3);
        // console.log('rate_of_interest-', rate_of_interest);
        // const realizable_amount = principal + (rate_of_interest * (time/30));    
        // console.log('totalRepayment-', realizable_amount);
        // const emi = realizable_amount / time;
        // console.log('emi--', emi);

        let emi = 0, totalInterest = 0, totalRepayment = 0;
        if (unit === 'weeks'){
            const interestRatePerMonth = principal * rate / 100;
            // console.log('interestRatePerMonth-', interestRatePerMonth)
            totalRepayment = principal + interestRatePerMonth;
            // console.log('totalRepayment-', totalRepayment)
            emi = totalRepayment / time;  
            // console.log('Weekly EMI:', emi.toFixed(2));   
        }else{
            // const interestRatePerMonth = parseFloat(rate / 100) / 3; 
            // // console.log('interestRatePerMonth-', interestRatePerMonth)
            // totalInterest = parseFloat(principal * interestRatePerMonth * (time / 30));
            // console.log('Total Interest:', totalInterest.toFixed(2)); 
            // totalRepayment = parseFloat(principal + totalInterest);
            // // console.log('Total Repayment:', totalRepayment.toFixed(2)); 
            // emi = parseFloat(totalRepayment) / time;
            // // console.log('Daily EMI:', emi.toFixed(2));
            const interestRatePerMonth = principal * rate / 100;
            totalRepayment = principal + interestRatePerMonth;
            emi = totalRepayment / time;
        }
        return emi.toFixed(2);
        // return Math.round(emi);
    }
    
    // Function to fetch address details from India Post API
    async function fetchAddressFromPincode(pincode) {
        try {
            const response = await fetch(`https://api.postalpincode.in/pincode/${pincode}`);
            const data = await response.json();
            // console.log('data---',data);
            
            if (data && data.length > 0 && data[0].Status === 'Success' && data[0].PostOffice && data[0].PostOffice.length > 0) {
                const postOffice = data[0].PostOffice[0];
                return {
                    postOffice: postOffice.Name,
                    city: postOffice.Block || postOffice.Division,
                    district: postOffice.District,
                    state: postOffice.State
                };
            } else {
                throw new Error('No data found for this pincode');
            }
        } catch (error) {
            console.error('Error fetching address details:', error);
            return null;
        }
    }
    
    // Function to auto-fill address fields
    function autoFillAddressFields(pincode, isCurrentAddress = false) {
        const prefix = isCurrentAddress ? 'current_' : '';
        
        // Show loading state
        const postOfficeField = document.getElementById(prefix + 'post_office');
        const cityField = document.getElementById(prefix + 'city_or_town');
        const districtField = document.getElementById(prefix + 'district');
        const stateField = document.getElementById(prefix + 'state');
        
        // Add loading class to fields
        const fields = [postOfficeField, cityField, districtField, stateField];
        fields.forEach(field => {
            if (field && !field.dataset.manuallyEdited) {
                field.classList.add('loading');
                field.value = 'Loading...';
            }
        });
        
        fetchAddressFromPincode(pincode).then(addressData => {
            if (addressData) {
                // Only auto-fill fields that haven't been manually edited
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
                
                // Show success message
                // showToast('Address details auto-filled successfully!', 'success');
            } else {
                // Clear fields if API call failed (only if not manually edited)
                fields.forEach(field => {
                    if (field && !field.dataset.manuallyEdited) {
                        field.value = '';
                        field.classList.remove('loading');
                    }
                });
                
                // Show error message
                showToast('Could not fetch address details for this pincode. Please enter manually.', 'error');
            }
        }).catch(error => {
            // Handle network errors
            fields.forEach(field => {
                if (field && !field.dataset.manuallyEdited) {
                    field.value = '';
                    field.classList.remove('loading');
                }
            });
            
            showToast('Network error. Please check your connection and try again.', 'error');
        });
    }
    
    // Function to setup pincode auto-fill functionality
    function setupPincodeAutoFill() {
        const permanentPincodeField = document.getElementById('post_code');
        const currentPincodeField = document.getElementById('current_post_code');
        
        // Setup for permanent address pincode
        if (permanentPincodeField) {
            permanentPincodeField.addEventListener('blur', function() {
                const pincode = this.value.trim();
                if (pincode.length === 6 && /^\d{6}$/.test(pincode)) {
                    // Add a small delay to show the user that something is happening
                    setTimeout(() => {
                        autoFillAddressFields(pincode, false);
                    }, 100);
                }
            });
        }
        
        // Setup for current address pincode
        if (currentPincodeField) {
            currentPincodeField.addEventListener('blur', function() {
                const pincode = this.value.trim();
                if (pincode.length === 6 && /^\d{6}$/.test(pincode)) {
                    // Add a small delay to show the user that something is happening
                    setTimeout(() => {
                        autoFillAddressFields(pincode, true);
                    }, 100);
                }
            });
        }
    }
    
    // Function to update EMI when loan details change
    function updateEMI() {
        const loanAmountField = document.getElementById('loan_amount');
        const tenureField = document.getElementById('tenure_months');
        const interestField = document.getElementById('interest_rate');
        const emiField = document.getElementById('emi_amount');
        
        if (loanAmountField && tenureField && interestField && emiField) {
            // Clean the loan amount value and parse it
            let loanAmountStr = loanAmountField.value.replace(/,/g, '').replace(/[^\d.]/g, '');
            const loanAmount = parseFloat(loanAmountStr) || 0;
            // Get the numeric tenure value from the selected option
            const selectedOption = tenureField.options[tenureField.selectedIndex];
            // console.log(selectedOption)
            const tenure = selectedOption ? parseInt(selectedOption.dataset.tenureValue) : 0;
            const tenureUnit = selectedOption ? (selectedOption.dataset.tenureUnit) : '';
            // console.log(tenureUnit)
            const interestRate = parseFloat(interestField.value) || 0;
            
            // Clear EMI if any required value is missing or invalid
            if (loanAmount <= 0 || tenure <= 0 || interestRate <= 0 || isNaN(loanAmount) || isNaN(tenure) || isNaN(interestRate)) {
                emiField.value = '';
                return;
            }
            
            // Calculate EMI
            const emi = calculateEMI(loanAmount, interestRate, tenure, tenureUnit);
            
            // Check if calculation resulted in a valid number
            if (isNaN(emi) || emi <= 0) {
                emiField.value = '';
                return;
            }
            
            emiField.value = emi.toLocaleString('en-IN');
            
            // Optional: Show calculation details in console for debugging
            // console.log(`EMI Calculation: Loan Amount: ₹${loanAmount.toLocaleString('en-IN')}, Tenure: ${tenure} months, Interest Rate: ${interestRate}%, EMI: ₹${emi.toLocaleString('en-IN')}`);
        }
    }
    
    // Initialize EMI calculator when DOM is loaded
    function initializeEMICalculator() {
        const tenureField = document.getElementById('tenure_months');
        const interestField = document.getElementById('interest_rate');
        const loanAmountField = document.getElementById('loan_amount');
        
        if (tenureField && interestField) {
            tenureField.addEventListener('change', function() {
                const val = this.value;
                if (tenureToInterest[val]) {
                    interestField.value = tenureToInterest[val];
                    // Update EMI after setting interest rate
                    updateEMI();
                } else {
                    interestField.value = '';
                    updateEMI();
                }
            });
        }
        
        // Add event listeners for EMI calculation
        if (loanAmountField) {
            loanAmountField.addEventListener('input', function() {
                // Remove all non-numeric characters except decimal point
                let value = this.value.replace(/[^\d.]/g, '');
                
                // Handle multiple decimal points - keep only the first one
                const parts = value.split('.');
                if (parts.length > 2) {
                    value = parts[0] + '.' + parts.slice(1).join('');
                }
                
                // Limit to 2 decimal places
                if (parts.length === 2 && parts[1].length > 2) {
                    value = parts[0] + '.' + parts[1].substring(0, 2);
                }
                
                // If value is empty or invalid, clear the field
                if (!value || value === '.' || isNaN(parseFloat(value))) {
                    this.value = '';
                    updateEMI();
                    return;
                }
                
                // Convert to number and format with commas
                const numValue = parseFloat(value);
                if (!isNaN(numValue) && numValue > 0) {
                    // Format with commas (no decimals for display)
                    this.value = Math.floor(numValue).toLocaleString('en-IN');
                } else {
                    this.value = '';
                }
                
                updateEMI();
            });
            
            // Also handle paste events
            loanAmountField.addEventListener('paste', function(e) {
                e.preventDefault();
                const pastedText = (e.clipboardData || window.clipboardData).getData('text');
                // Remove non-numeric characters and paste
                const cleanValue = pastedText.replace(/[^\d.]/g, '');
                this.value = cleanValue;
                this.dispatchEvent(new Event('input'));
            });
            
            // Handle focus events for better UX
            loanAmountField.addEventListener('focus', function() {
                // If field contains only invalid characters, clear it
                const currentValue = this.value.replace(/,/g, '');
                if (currentValue && (isNaN(parseFloat(currentValue)) || parseFloat(currentValue) <= 0)) {
                    this.value = '';
                }
            });
            
            // Handle blur events to ensure proper formatting
            loanAmountField.addEventListener('blur', function() {
                const value = this.value.replace(/,/g, '');
                if (value && !isNaN(parseFloat(value)) && parseFloat(value) > 0) {
                    // Ensure proper formatting on blur
                    this.value = Math.floor(parseFloat(value)).toLocaleString('en-IN');
                } else if (value && (isNaN(parseFloat(value)) || parseFloat(value) <= 0)) {
                    // Clear invalid values
                    this.value = '';
                }
                updateEMI();
            });
        }
        
        if (interestField) {
            interestField.addEventListener('input', updateEMI);
        }
        
        if (tenureField) {
            tenureField.addEventListener('change', updateEMI);
        }
    }

    function setupIFSCAutoFill() {
        const ifscField = document.getElementById('ifsc_code');
        const bankNameField = document.getElementById('bank_name');
        const branchDisplay = document.getElementById('bank-branch-display');
        const ifscError = document.getElementById('error-ifsc_code');
        if (!ifscField || !bankNameField || !branchDisplay) return;

        const IFSC_REGEX = /^[A-Z]{4}0[A-Z0-9]{6}$/;
        let currentLookupToken = 0;

        const setBranchDisplay = (message = '') => {
            branchDisplay.textContent = message;
        };

        const setIFSCError = (message = '') => {
            if (ifscError) {
                ifscError.textContent = message;
            }
            ifscField.classList.toggle('border-red-500', !!message);
        };

        async function lookupBranch(ifsc) {
            const token = ++currentLookupToken;
            setBranchDisplay('Looking up…');
            setIFSCError('');

            const result = await fetchBranchFromIFSC(ifsc);
            if (token !== currentLookupToken) {
                return;
            }

            if (result.success && result.data) {
                const { BANK, BRANCH } = result.data;
                if (BANK) {
                    bankNameField.value = BANK;
                    delete bankNameField.dataset.manuallyEdited;
                }
                if (BRANCH) {
                    setBranchDisplay(`Branch: ${BRANCH}`);
                } else {
                    setBranchDisplay('');
                    setIFSCError('Branch name not returned for this IFSC. Please verify manually.');
                    showToast('Branch name not returned for this IFSC. Please verify manually.', 'warning');
                }
            } else {
                const message = result.message || 'Unable to fetch branch details. Please verify manually.';
                setBranchDisplay('');
                setIFSCError(message);
                showToast(message, 'error');
            }
        }

        function cancelPendingLookup() {
            currentLookupToken += 1;
            setBranchDisplay('');
        }

        function handleIFSCInput() {
            const ifsc = ifscField.value.trim().toUpperCase();
            ifscField.value = ifsc;

            if (!ifsc) {
                cancelPendingLookup();
                setIFSCError('');
                return;
            }

            if (!IFSC_REGEX.test(ifsc)) {
                cancelPendingLookup();
                setIFSCError('Enter a valid IFSC code (e.g., SBIN0001234).');
                return;
            }

            setIFSCError('');
            lookupBranch(ifsc);
        }

        ifscField.addEventListener('input', handleIFSCInput);

        bankNameField.addEventListener('input', () => {
            bankNameField.dataset.manuallyEdited = 'true';
        });

        const initialIFSC = ifscField.value.trim().toUpperCase();
        ifscField.value = initialIFSC;
        if (initialIFSC && IFSC_REGEX.test(initialIFSC)) {
            lookupBranch(initialIFSC);
        } else {
            setBranchDisplay('');
        }
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupIFSCAutoFill);
    } else {
        setupIFSCAutoFill();
    }
    
    // Utility: Format date/time as 'd F Y, H:i' in IST
    function formatDateTimeIST(dateInput) {
        // Accepts a Date object or a string
        let dateObj = (dateInput instanceof Date) ? dateInput : new Date(dateInput);
        // Convert to IST (UTC+5:30)
        let utc = dateObj.getTime() + (dateObj.getTimezoneOffset() * 60000);
        let istOffset = 5.5 * 60 * 60000;
        let istDate = new Date(utc + istOffset);
        // Format: 24 July 2024, 14:30
        const day = istDate.getDate().toString().padStart(2, '0');
        const month = istDate.toLocaleString('en-IN', { month: 'long' });
        const year = istDate.getFullYear();
        const hour = istDate.getHours().toString().padStart(2, '0');
        const minute = istDate.getMinutes().toString().padStart(2, '0');
        return `${day} ${month} ${year}, ${hour}:${minute}`;
    }
    
    // Make functions available globally if needed
    window.calculateEMI = calculateEMI;
    window.updateEMI = updateEMI;
    window.tenureToInterest = tenureToInterest;
    window.fetchAddressFromPincode = fetchAddressFromPincode;
    window.autoFillAddressFields = autoFillAddressFields;
    window.formatDateTimeIST = formatDateTimeIST;
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            initializeEMICalculator();
            setupPincodeAutoFill();
            populateLoanCategorySelect();
            populateLoanTenureSelect();
        });
    } else {
        initializeEMICalculator();
        setupPincodeAutoFill();
        populateLoanCategorySelect();
        populateLoanTenureSelect();
    }

    // Dynamically populate the loan category select field
    function populateLoanCategorySelect() {
        const select = document.getElementById('loan_category');
        if (!select) return;
        // API endpoint for loan categories
        fetch('/agent/api/loan-category?shop_status=inactive')
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(categories => {
                // Remove all options except the first (placeholder)
                select.options.length = 1;
                categories.forEach(cat => {
                    const option = document.createElement('option');
                    option.value = cat.id;
                    option.textContent = cat.name;
                    select.appendChild(option);
                });
                // Re-apply draft selection (if any) after options are loaded
                try {
                    const draft = localStorage.getItem('loanApplicationDraft');
                    if (draft) {
                        const data = JSON.parse(draft);
                        if (data && data.loan_category) {
                            select.value = String(data.loan_category);
                            // Trigger change for any dependent logic
                            select.dispatchEvent(new Event('change'));
                        }
                    }
                } catch (e) {
                    console.warn('Failed to apply draft for loan_category:', e);
                }
            })
            .catch(error => {
                console.error('Error loading loan categories:', error);
            });
    }

    // Dynamically populate the loan tenure select field
    function populateLoanTenureSelect() {
        const select = document.getElementById('tenure_months');
        const interestField = document.getElementById('interest_rate');
        const interestIdField = document.getElementById('interest_rate_id');
        if (!select) return;
        fetch('/agent/api/loan-tenure')
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(tenures => {
                // Remove all options except the first (placeholder)
                select.options.length = 1;
                tenures.forEach(tenure => {
                    // console.log(tenure)
                    const option = document.createElement('option');
                    option.value = tenure.id; // Use tenure_id for form submission
                    option.textContent = tenure.display;
                    option.dataset.interestRate = tenure.interest_rate;
                    option.dataset.interestId = tenure.interest_id;
                    option.dataset.tenureValue = tenure.value; // Store numeric value for EMI calculation
                    option.dataset.tenureUnit  = tenure.unit;
                    select.appendChild(option);
                });
                // Update interest rate when tenure changes
                select.addEventListener('change', function() {
                    const selected = select.options[select.selectedIndex];
                    if (selected && selected.dataset.interestRate && interestField) {
                        interestField.value = selected.dataset.interestRate;
                        // Set the hidden field with the interest_id
                        if (interestIdField) {
                            interestIdField.value = selected.dataset.interestId || '';
                        }
                        updateEMI();
                    }
                });
                // Re-apply draft selection (if any) after options are loaded
                try {
                    const draft = localStorage.getItem('loanApplicationDraft');
                    if (draft) {
                        const data = JSON.parse(draft);
                        if (data && data.tenure_months) {
                            select.value = String(data.tenure_months);
                            // Trigger change to update interest and EMI
                            select.dispatchEvent(new Event('change'));
                        }
                    }
                } catch (e) {
                    console.warn('Failed to apply draft for tenure_months:', e);
                }
            })
            .catch(error => {
                console.error('Error loading loan tenures:', error);
            });
    }
})();

async function fetchBranchFromIFSC(ifscCode) {
    const ifsc = ifscCode.trim().toUpperCase();
    if (!/^[A-Z]{4}0[A-Z0-9]{6}$/.test(ifsc)) {
        return { success: false, message: '' };   //Enter a valid IFSC code (e.g., SBIN0001234).
    }
    try {
        const response = await fetch(`https://ifsc.razorpay.com/${ifsc}`);
        if (!response.ok) {
            throw new Error(`IFSC lookup failed with status ${response.status}`);
        }
        const data = await response.json();
        return { success: true, data };
    } catch (error) {
        console.error('[IFSC Lookup] Error:', error);
        return { success: false, message: 'Unable to fetch branch details. Please re-check the IFSC or try again later.' };
    }
}
window.fetchBranchFromIFSC = fetchBranchFromIFSC;


// /**
//  * Attach inline edit handlers for customer fields (edit, validate, save, cancel).
//  * @param {Object} data - Customer data object (must include customer_id and field values).
//  * @param {Function} showToast - Function to show toast messages.
//  */
// function attachInlineEditHandlers(data, showToast) {
//     document.addEventListener('click', function(e) {
//         // Full Name edit icon
//         if (e.target.closest('#editFullNameIcon')) {
//             const fullNameValue = document.getElementById('fullNameValue');
//             fullNameValue.innerHTML = `
//                 <input type="text" id="editFullNameInput" class="w-full px-2 py-1 border rounded" value="${data.full_name || ''}" name="full_name">
//                 <div id="nameErrorMsg" class="text-xs text-red-500 mt-1"></div>
//                 <button class="inlineEditSaveBtn ml-2 px-2 py-1 text-xs bg-brand-500 text-white rounded"
//                     data-field="full_name" data-input="editFullNameInput" data-display="fullNameValue">Save</button>
//                 <button id="cancelFullNameBtn" class="ml-2 px-2 py-1 text-xs bg-red-500 text-white rounded">Cancel</button>
//             `;
//             setTimeout(() => {
//                 const input = document.getElementById('editFullNameInput');
//                 const errorMsg = document.getElementById('nameErrorMsg');
//                 function toTitleCase(str) {
//                     return str.replace(/\w\S*/g, function(txt) {
//                         return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
//                     });
//                 }
//                 input.addEventListener('input', function() {
//                     input.value = toTitleCase(input.value);
//                     errorMsg.textContent = !input.value.trim() ? 'Name cannot be empty.' : '';
//                 });
//                 input.addEventListener('blur', function() {
//                     input.value = toTitleCase(input.value);
//                 });
//             }, 10);
//         }
//         // Date of Birth edit icon
//         if (e.target.closest('#editDateOfBirthIcon')) {
//             const dateOfBirthValue = document.getElementById('dateOfBirthValue');
//             let dobValue = data.date_of_birth ? new Date(data.date_of_birth).toISOString().slice(0, 10) : '';
//             dateOfBirthValue.innerHTML = `
//                 <input type="text" id="editDobInput" class="w-full px-2 py-1 border rounded" value="${dobValue}">
//                 <button class="inlineEditSaveBtn ml-2 px-2 py-1 text-xs bg-brand-500 text-white rounded"
//                     data-field="date_of_birth" data-input="editDobInput" data-display="dateOfBirthValue">Save</button>
//                 <button id="cancelDobBtn" class="ml-2 px-2 py-1 text-xs bg-red-500 text-white rounded">Cancel</button>
//             `;
//             if (window.flatpickr) {
//                 const today = new Date();
//                 const maxDate = new Date(today.getFullYear() - 21, today.getMonth(), today.getDate());
//                 flatpickr("#editDobInput", {
//                     mode: 'single',
//                     dateFormat: 'Y-m-d',
//                     maxDate: maxDate,
//                     allowInput: true
//                 });
//             }
//         }
//         // Gender edit icon
//         if (e.target.closest('#editGenderIcon')) {
//             const genderValue = document.getElementById('genderValue');
//             genderValue.innerHTML = `
//                 <select id="editGenderSelect" class="w-full px-2 py-1 border rounded">
//                     <option value="male" ${data.gender.toLowerCase() === 'male' ? 'selected' : ''}>Male</option>
//                     <option value="female" ${data.gender.toLowerCase() === 'female' ? 'selected' : ''}>Female</option>
//                     <option value="other" ${data.gender.toLowerCase() === 'other' ? 'selected' : ''}>Other</option>
//                 </select>
//                 <button class="inlineEditSaveBtn ml-2 px-2 py-1 text-xs bg-brand-500 text-white rounded"
//                     data-field="gender" data-input="editGenderSelect" data-display="genderValue">Save</button>
//                 <button id="cancelGenderBtn" class="ml-2 px-2 py-1 text-xs bg-red-500 text-white rounded">Cancel</button>
//             `;
//         }
//         // Contact edit icon
//         if (e.target.closest('#editContactIcon')) {
//             const contactValue = document.getElementById('contactValue');
//             contactValue.innerHTML = `
//                 <input type="text" id="editContactInput" class="w-full px-2 py-1 border rounded" maxlength="10" value="${data.contact || ''}">
//                 <div id="contactErrorMsg" class="text-xs text-red-500 mt-1"></div>
//                 <button class="inlineEditSaveBtn ml-2 px-2 py-1 text-xs bg-brand-500 text-white rounded"
//                     data-field="contact" data-input="editContactInput" data-display="contactValue">Save</button>
//                 <button id="cancelContactBtn" class="ml-2 px-2 py-1 text-xs bg-red-500 text-white rounded">Cancel</button>
//             `;
//             setTimeout(() => {
//                 const input = document.getElementById('editContactInput');
//                 const errorMsg = document.getElementById('contactErrorMsg');
//                 input.addEventListener('input', function() {
//                     let val = input.value.replace(/\D/g, '');
//                     input.value = val;
//                     errorMsg.textContent = val.length !== 10 ? 'Contact number must be exactly 10 digits.' : '';
//                 });
//             }, 10);
//         }
//         // Email edit icon
//         if (e.target.closest('#editEmailIcon')) {
//             const emailValue = document.getElementById('emailValue');
//             emailValue.innerHTML = `
//                 <input type="email" id="editEmailInput" class="w-full px-2 py-1 border rounded" value="${data.email || ''}">
//                 <div id="emailErrorMsg" class="text-xs text-red-500 mt-1"></div>
//                 <button class="inlineEditSaveBtn ml-2 px-2 py-1 text-xs bg-brand-500 text-white rounded"
//                     data-field="email" data-input="editEmailInput" data-display="emailValue">Save</button>
//                 <button id="cancelEmailBtn" class="ml-2 px-2 py-1 text-xs bg-red-500 text-white rounded">Cancel</button>
//             `;
//             setTimeout(() => {
//                 const input = document.getElementById('editEmailInput');
//                 const errorMsg = document.getElementById('emailErrorMsg');
//                 input.addEventListener('input', function() {
//                     const val = input.value;
//                     const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
//                     errorMsg.textContent = val && !emailRegex.test(val) ? 'Please enter a valid email address.' : '';
//                 });
//             }, 10);
//         }
//         // Aadhaar edit icon
//         if (e.target.closest('#editAadharIcon')) {
//             const aadharValue = document.getElementById('aadharValue');
//             aadharValue.innerHTML = `
//                 <input type="text" id="editAadharInput" class="w-full px-2 py-1 border rounded" maxlength="12" value="${data.adhar_number || ''}">
//                 <div id="aadharErrorMsg" class="text-xs text-red-500 mt-1"></div>
//                 <button class="inlineEditSaveBtn ml-2 px-2 py-1 text-xs bg-brand-500 text-white rounded"
//                     data-field="adhar_number" data-input="editAadharInput" data-display="aadharValue">Save</button>
//                 <button id="cancelAadharNumberBtn" class="ml-2 px-2 py-1 text-xs bg-red-500 text-white rounded">Cancel</button>
//             `;
//             setTimeout(() => {
//                 const input = document.getElementById('editAadharInput');
//                 const errorMsg = document.getElementById('aadharErrorMsg');
//                 input.addEventListener('input', function() {
//                     let val = input.value.replace(/\D/g, '');
//                     input.value = val;
//                     errorMsg.textContent = val.length !== 12 ? 'Aadhaar number must be exactly 12 digits.' : '';
//                 });
//             }, 10);
//         }
//         // PAN edit icon
//         if (e.target.closest('#editPanIcon')) {
//             const panValue = document.getElementById('panValue');
//             panValue.innerHTML = `
//                 <input type="text" id="editPanInput" class="w-full px-2 py-1 border rounded uppercase" maxlength="10" value="${data.pan_number || ''}">
//                 <div id="panErrorMsg" class="text-xs text-red-500 mt-1"></div>
//                 <button class="inlineEditSaveBtn ml-2 px-2 py-1 text-xs bg-brand-500 text-white rounded"
//                     data-field="pan_number" data-input="editPanInput" data-display="panValue">Save</button>
//                 <button id="cancelPanNumberBtn" class="ml-2 px-2 py-1 text-xs bg-red-500 text-white rounded">Cancel</button>
//             `;
//             setTimeout(() => {
//                 const input = document.getElementById('editPanInput');
//                 const errorMsg = document.getElementById('panErrorMsg');
//                 input.addEventListener('input', function() {
//                     input.value = input.value.toUpperCase();
//                     const val = input.value;
//                     const panRegex = /^[A-Z]{5}\d{4}[A-Z]$/;
//                     if (val.length !== 10) {
//                         errorMsg.textContent = 'PAN must be exactly 10 characters.';
//                     } else if (!panRegex.test(val)) {
//                         errorMsg.textContent = 'Invalid PAN format. Format: 5 letters, 4 digits, 1 letter.';
//                     } else {
//                         errorMsg.textContent = '';
//                     }
//                 });
//             }, 10);
//         }
//         // Voter edit icon
//         if (e.target.closest('#editVoterIcon')) {
//             const voterValue = document.getElementById('voterValue');
//             voterValue.innerHTML = `
//                 <input type="text" id="editVoterInput" class="w-full px-2 py-1 border rounded uppercase" maxlength="10" value="${data.voter_number || ''}">
//                 <div id="voterErrorMsg" class="text-xs text-red-500 mt-1"></div>
//                 <button class="inlineEditSaveBtn ml-2 px-2 py-1 text-xs bg-brand-500 text-white rounded"
//                     data-field="voter_number" data-input="editVoterInput" data-display="voterValue">Save</button>
//                 <button id="cancelVoterNumberBtn" class="ml-2 px-2 py-1 text-xs bg-red-500 text-white rounded">Cancel</button>
//             `;
//             setTimeout(() => {
//                 const input = document.getElementById('editVoterInput');
//                 const errorMsg = document.getElementById('voterErrorMsg');
//                 input.addEventListener('input', function() {
//                     input.value = input.value.toUpperCase();
//                     const val = input.value;
//                     const voterRegex = /^[A-Z]{3}\d{7}$/;
//                     if (val.length !== 10) {
//                         errorMsg.textContent = 'Voter ID must be exactly 10 characters.';
//                     } else if (!voterRegex.test(val)) {
//                         errorMsg.textContent = 'Invalid Voter ID format. Format: 3 letters, 7 digits.';
//                     } else {
//                         errorMsg.textContent = '';
//                     }
//                 });
//             }, 10);
//         }

//         // Generic save handler for inline edits
//         if (e.target && e.target.classList.contains('inlineEditSaveBtn')) {
//             const field = e.target.getAttribute('data-field');
//             const inputId = e.target.getAttribute('data-input');
//             const value = document.getElementById(inputId).value;
//             const displayId = e.target.getAttribute('data-display');
//             const payload = {};
//             payload[field] = value;

//             const csrfElem = document.querySelector('[name=csrfmiddlewaretoken]');
//             if (!csrfElem) {
//                 showToast('CSRF token not found. Please reload the page.', 'error');
//                 return;
//             }

//             fetch(`/agent/api/edit-customer/${data.customer_id}/`, {
//                 method: 'POST',
//                 headers: {
//                     'Content-Type': 'application/json',
//                     'X-CSRFToken': csrfElem.value
//                 },
//                 body: JSON.stringify(payload)
//             })
//             .then(resp => resp.json())
//             .then(respData => {
//                 if (respData.success) {
//                     // After save, restore to non-editable view and re-enable edit icon
//                     if (field === 'full_name') {
//                         document.getElementById(displayId).innerHTML = `<p class="text-sm text-gray-800 dark:text-white">${value}</p>`;
//                     } else if (field === 'date_of_birth') {
//                         document.getElementById(displayId).innerHTML = `<p class="text-sm text-gray-800 dark:text-white">${value ? value : ''}</p>`;
//                     } else if (field === 'gender') {
//                         document.getElementById(displayId).innerHTML = `<p class="text-sm text-gray-800 dark:text-white">${value.charAt(0).toUpperCase() + value.slice(1)}</p>`;
//                     } else {
//                         document.getElementById(displayId).innerHTML = `<p class="text-sm text-gray-800 dark:text-white">${value}</p>`;
//                     }
//                     showToast(field.charAt(0).toUpperCase() + field.slice(1) + ' updated!', 'success');
//                     data[field] = value; // update local data for cancel
//                 } else {
//                     showToast(respData.detail || 'Failed to update', 'error');
//                 }
//             });
//         }

//         // Cancel handlers
//         if (e.target && e.target.id === 'cancelFullNameBtn') {
//             document.getElementById('fullNameValue').innerHTML = `<p class="text-sm text-gray-800 dark:text-white">${data.full_name}</p>`;
//         }
//         if (e.target && e.target.id === 'cancelDobBtn') {
//             document.getElementById('dateOfBirthValue').innerHTML = `<p class="text-sm text-gray-800 dark:text-white">${data.date_of_birth ? data.date_of_birth : ''}</p>`;
//         }
//         if (e.target && e.target.id === 'cancelGenderBtn') {
//             document.getElementById('genderValue').innerHTML = `<p class="text-sm text-gray-800 dark:text-white">${data.gender.charAt(0).toUpperCase() + data.gender.slice(1)}</p>`;
//         }
//         if (e.target && e.target.id === 'cancelContactBtn') {
//             document.getElementById('contactValue').innerHTML = `<p class="text-sm text-gray-800 dark:text-white">${data.contact}</p>`;
//         }
//         if (e.target && e.target.id === 'cancelEmailBtn') {
//             document.getElementById('emailValue').innerHTML = `<p class="text-sm text-gray-800 dark:text-white">${data.email}</p>`;
//         }
//         if (e.target && e.target.id === 'cancelAadharNumberBtn') {
//             document.getElementById('aadharValue').innerHTML = `<p class="text-sm text-gray-800 dark:text-white">${data.adhar_number}</p>`;
//         }
//         if (e.target && e.target.id === 'cancelPanNumberBtn') {
//             document.getElementById('panValue').innerHTML = `<p class="text-sm text-gray-800 dark:text-white">${data.pan_number}</p>`;
//         }
//         if (e.target && e.target.id === 'cancelVoterNumberBtn') {
//             document.getElementById('voterValue').innerHTML = `<p class="text-sm text-gray-800 dark:text-white">${data.voter_number}</p>`;
//         }
//     });
// }

// // Export for use in other scripts
// window.attachInlineEditHandlers = attachInlineEditHandlers;