
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === name + "=") {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Prevent duplicate form submissions
let isSubmitting = false;

function toTitleCase(str) {
    return (str || "").replace(/\w\S*/g, function (txt) {
        return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
    });
}

const fullNameField = document.getElementById("full_name");
if (fullNameField) {
    fullNameField.addEventListener("input", function () {
        fullNameField.value = toTitleCase(fullNameField.value);
    });
    fullNameField.addEventListener("blur", function () {
        fullNameField.value = toTitleCase(fullNameField.value);
    });
}

const fatherNameField = document.getElementById("father_name");
if (fatherNameField) {
    fatherNameField.addEventListener("input", function () {
        fatherNameField.value = toTitleCase(fatherNameField.value);
    });
    fatherNameField.addEventListener("blur", function () {
        fatherNameField.value = toTitleCase(fatherNameField.value);
    });
}

const guarantorNameField = document.getElementById("guarantor_name");
if (guarantorNameField) {
    guarantorNameField.addEventListener("input", function () {
        guarantorNameField.value = toTitleCase(guarantorNameField.value);
    });
    guarantorNameField.addEventListener("blur", function () {
        guarantorNameField.value = toTitleCase(guarantorNameField.value);
    });
}

document
    .getElementById("loan-application-form")
    .addEventListener("submit", async function (e) {
        e.preventDefault();
        // Form submission is now handled by Alpine.js submitApplication function
        // This old event listener is disabled to prevent conflicts
        return false;
    });

// Clear error message for a field when its value changes
["input", "change"].forEach((eventType) => {
    document
        .querySelectorAll(
            "#loan-application-form input, #loan-application-form select",
        )
        .forEach((field) => {
            field.addEventListener(eventType, function () {
                const errDiv = document.getElementById("error-" + this.name);
                if (errDiv) errDiv.textContent = "";
            });
        });
});
// Explicitly clear error for loan_category on change
const loanCategoryField = document.getElementById("loan_category");
if (loanCategoryField) {
    loanCategoryField.addEventListener("change", function () {
        const errDiv = document.getElementById("error-loan_category");
        if (errDiv) {
            if (this.value) {
                errDiv.textContent = "";
            } else {
                // Only show error if field has been touched or form is being submitted
                if (
                    (window.touchedFields &&
                        window.touchedFields.has("loan_category")) ||
                    window._showAllErrors
                ) {
                    errDiv.textContent = "This field is required.";
                }
            }
        }
    });
}

function validateStep(stepNumber) {
    const stepDiv = document.getElementById("step-" + stepNumber);
    if (!stepDiv) return true;

    let valid = true;
    window._showAllErrors = true;

    const inputs = stepDiv.querySelectorAll(
        "input[required], select[required]",
    );
    inputs.forEach((field) => {
        // Skip hidden fields (like current address fields if same as permanent)
        if (field.offsetParent === null && field.type !== "hidden") return;

        // Custom validation check
        const errMsg = window.customValidation
            ? window.customValidation(field)
            : null;

        if (!field.value.trim()) {
            if (window.showFieldError)
                window.showFieldError(field, "This field is required.");
            valid = false;
        } else if (errMsg) {
            if (window.showFieldError) window.showFieldError(field, errMsg);
            valid = false;
        } else {
            if (window.clearFieldError) window.clearFieldError(field);
        }
    });

    window._showAllErrors = false;

    if (!valid) {
        const firstError = stepDiv.querySelector(".border-red-500");
        if (firstError)
            firstError.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    return valid;
}

// Make validation functions available globally
window.showFieldError = function (field, message) {
    const errDiv = document.getElementById("error-" + field.name);
    if (errDiv) errDiv.textContent = message;
    field.classList.add("border-red-500");
};

window.clearFieldError = function (field) {
    const errDiv = document.getElementById("error-" + field.name);
    if (errDiv) errDiv.textContent = "";
    field.classList.remove("border-red-500");
};

// Current address toggle functionality
window.toggleCurrentAddress = function (checkbox) {
    const currentAddressSection = document.getElementById(
        "current-address-section",
    );
    const residentialProofSections = document.querySelectorAll(
        ".residential-proof-section",
    );

    if (checkbox.checked) {
        // Hide current address section
        if (currentAddressSection) {
            currentAddressSection.style.display = "none";
        }
        if (residentialProofSections.length > 0) {
            residentialProofSections.forEach((section) => {
                section.style.display = "none";
            });
        }

        // Copy permanent address to current address fields
        const permanentFields = [
            "address_line_1",
            "address_line_2",
            "landmark",
            "post_office",
            "city_or_town",
            "district",
            "state",
            "country",
            "post_code",
        ];
        permanentFields.forEach((fieldName) => {
            const permanentField = document.getElementById(fieldName);
            const currentFieldName =
                fieldName === "post_code"
                    ? "current_post_code"
                    : "current_" + fieldName;
            const currentField = document.getElementById(currentFieldName);

            if (permanentField && currentField) {
                currentField.value = permanentField.value;
                // Clear any errors on current field
                window.clearFieldError(currentField);
            }
        });
    } else {
        // Show current address section
        if (currentAddressSection) {
            currentAddressSection.style.display = "flex";
        }
        if (residentialProofSections.length > 0) {
            residentialProofSections.forEach((section) => {
                section.style.display = "block";
            });
        }

        // Clear current address fields
        const currentFields = [
            "current_address_line_1",
            "current_address_line_2",
            "current_landmark",
            "current_post_office",
            "current_city_or_town",
            "current_district",
            "current_state",
            "current_country",
            "current_post_code",
        ];
        currentFields.forEach((fieldName) => {
            const field = document.getElementById(fieldName);
            if (field) {
                field.value = "";
                window.clearFieldError(field);
            }
        });
    }
};

// Initialize current address toggle when DOM is ready
document.addEventListener("DOMContentLoaded", function () {
    const sameAddressCheckbox = document.getElementById("same-address");
    if (sameAddressCheckbox) {
        sameAddressCheckbox.addEventListener("change", function () {
            window.toggleCurrentAddress(this);
        });
        // Initialize the state
        window.toggleCurrentAddress(sameAddressCheckbox);
    }

    // Processing fees modal functionality
    const processingFeesModal = document.getElementById("processingFeesModal");
    const closeProcessingFeesModalBtn = document.getElementById(
        "close-processing-fees-modal",
    );

    if (closeProcessingFeesModalBtn) {
        closeProcessingFeesModalBtn.addEventListener("click", function () {
            if (processingFeesModal) {
                processingFeesModal.style.display = "none";
                document.body.style.overflow = "";
            }
        });
    }
});

// Show preview modal function
window.showPreviewModal = function () {
    const modal = document.getElementById("preview-modal");
    if (modal) {
        modal.classList.remove("hidden");
        modal.classList.add("flex");
        document.body.style.overflow = "hidden";
    }
};

// Show processing fees modal function
window.showProcessingFeesModal = function () {
    const modal = document.getElementById("processingFeesModal");
    console.log(modal);
    if (modal) {
        modal.style.display = "flex";
        modal.style.justifyContent = "center";
        modal.style.alignItems = "center";
        document.body.style.overflow = "hidden";
    }
};

window.customValidation = function (field) {
    // File validations
    if (field.type === "file") {
        const files = field.files;
        if (files && files.length > 0) {
            const file = files[0];
            const maxSize = 1024 * 1024; // 1MB
            if (file.size > maxSize) {
                return "File size must be less than or equal to 1MB.";
            }
            if (field.name === "photo" || field.name === "signature") {
                if (!file.type || !file.type.startsWith("image/")) {
                    return "Please upload an image file (JPG, PNG, etc.).";
                }
            }
        }
    }

    // Check if same address checkbox is checked
    const sameAddressCheckbox = document.getElementById("same-address");
    const isSame = sameAddressCheckbox && sameAddressCheckbox.checked;

    if (field.name === "adhar_number") {
        const cleanValue = field.value.replace(/\s/g, "");
        if (!/^\d{12}$/.test(cleanValue))
            return "Adhar number must be exactly 12 digits.";
    }

    if (field.name === "pan_number") {
        const panValue = field.value.toUpperCase();
        field.value = panValue;
        if (!/^[A-Z]{5}\d{4}[A-Z]$/.test(panValue)) {
            return "PAN number must be 5 letters, 4 digits, 1 letter (e.g., ABCDE1234F).";
        }
    }

    if (field.name === "contact") {
        if (!/^\d{10}$/.test(field.value))
            return "Contact number must be exactly 10 digits.";
    }

    if (field.name === "voter_number") {
        if (field.value && !/^[A-Za-z]{3}\d{7}$/.test(field.value)) {
            return "Voter ID must be 3 letters followed by 7 digits (e.g. ABC1234567).";
        }
    }

    if (field.name === "email") {
        if (field.value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(field.value)) {
            return "Please enter a valid email address.";
        }
    }

    if (field.name === "post_code") {
        if (!/^\d{6}$/.test(field.value))
            return "Post code must be exactly 6 digits.";
    }

    if (field.name === "current_post_code") {
        if (!isSame && !/^\d{6}$/.test(field.value))
            return "Current post code must be exactly 6 digits.";
    }

    if (field.name === "loan_amount") {
        const amount = parseFloat(field.value.replace(/,/g, ""));
        if (isNaN(amount) || amount <= 0)
            return "Please enter a valid loan amount.";
        if (amount < 1000) return "Loan amount must be at least ₹1,000.";
        if (amount > 10000000) return "Loan amount cannot exceed ₹1,00,00,000.";
    }

    // For current address fields, only require if checkbox is unchecked
    if (!isSame) {
        if (
            [
                "current_post_code",
                "current_state",
                "current_address_line_1",
                "current_city_or_town",
                "current_district",
            ].includes(field.name)
        ) {
            if (!field.value) return "This field is required.";
        }
        if (field.name === "residential_proof_type" && !field.value) {
            return "This field is required when current address differs from permanent address.";
        }
        if (
            field.name === "residential_proof_file" &&
            (!field.files || field.files.length === 0)
        ) {
            return "This field is required when current address differs from permanent address.";
        }
    }

    return null;
};

function loanApplication() {
    return {
        currentStep: 0, // Start with category selection
        completedSteps: [],
        otpVerified: false,
        aadhaarPhoto: null,
        aadhaarPopulatedFields: {},

        // Main category data
        mainCategories: [],
        selectedMainCategory: null,
        categoryError: null,

        // Product selection data
        selectedProductMainCategory: null,
        selectedProductSubcategory: null,
        selectedProductType: null,
        productMainCategories: [],
        productSubcategories: [],
        productTypes: [],

        // Shop Account List
        shopBankAccount: [],

        // Processing fees data
        processingFees: [],

        // Loan data
        loanData: {
            shop_id: "",
            loan_category: "",
            loan_amount: "",
            loan_percentage: "",
            tenure_months: "",
            interest_rate: "",
            interest_rate_display: "",
            interest_rate_id: "",
            emi_amount: "",
            loan_purpose: "",
            processing_fee: "",
            down_payment: "",
        },

        // Verification data
        verificationData: {
            mobile: "",
            aadhaar: "",
        },

        // Personal info from Aadhaar
        personalInfo: {
            full_name: "",
            father_name: "",
            date_of_birth: "",
            gender: "",
            address: "",
            pincode: "",
            email: "",
            pan_number: "",
            voter_number: "",
            guarantor_name: "",
        },

        // Bank details
        bankDetails: {
            account_number: "",
            confirm_account_number: "",
            ifsc_code: "",
            bank_name: "",
            account_type: "",
        },

        // Address data
        addressData: {
            sameAddress: true,
            permanent: {
                address_line_1: "",
                address_line_2: "",
                landmark: "",
                post_code: "",
                post_office: "",
                city_or_town: "",
                district: "",
                state: "",
                country: "India",
            },
            current: {
                address_line_1: "",
                address_line_2: "",
                landmark: "",
                post_code: "",
                post_office: "",
                city_or_town: "",
                district: "",
                state: "",
                country: "India",
            },
        },

        // Documents
        documents: {
            guarantor_id_proof: null,
            id_proof: null,
            id_proof_back: null,
            pan_card: null,
            photo: null,
            signature: null,
        },

        // Dynamic data
        loanCategories: [],
        loanTenures: [],

        // Errors
        errors: {},

        // Bank verification status
        bankVerificationStatus: null, // null, 'verifying', 'verified', 'failed'
        bankVerificationData: null,
        bankVerificationMessage: null,

        // PAN verification status
        panVerificationStatus: null, // null, 'checking', 'linked', 'not_linked'

        // Customer type toggle
        customerType: {
            guarantor_id_proof: "new",
            id_proof: "new",
            id_proof_back: "new",
            pan_card: "new",
            photo: "new",
            signature: "new",
        }, // 'new' or 'existing'

        // Existing customer data
        selectedCustomerId: null,

        // Submission state
        // isSubmitting: false,
        totalProcessingFees: "",

        init() {
            this.loadMainCategories();
            this.loadLoanTenures();

            if (window.DEFAULT_SHOP_ID) {
                this.loanData.shop_id = window.DEFAULT_SHOP_ID;
                this.loadShopBankAccounts(window.DEFAULT_SHOP_ID);
            }

            // Watch for loan category changes to load relevant tenures
            this.$watch("loanData.loan_category", (newValue) => {
                this.loadTenuresForSubcategory(newValue);
                if (this.isProductCategorySelected()) {
                    this.loadProductMainCategories();
                }
            });

            // Watch for product subcategory changes to update loan amount
            this.$watch("selectedProductSubcategory", (newValue) => {
                this.updateLoanAmountBasedOnProductSelection();
            });

            // Watch for product type changes to update loan amount
            this.$watch("selectedProductType", (newValue) => {
                this.updateLoanAmountBasedOnProductSelection();
            });

            // Watch for shop changes to load bank accounts
            this.$watch("loanData.shop_id", (newValue) => {
                this.loadShopBankAccounts(newValue);
            });
        },

        // async loadLoanCategories() {
        //   try {
        //     const response = await fetch("/agent/api/loan-category");
        //     const categories = await response.json();
        //     this.loanCategories = categories;
        //   } catch (error) {
        //     console.error("Error loading loan categories:", error);
        //   }
        // },

        async loadLoanTenures() {
            try {
                const response = await fetch("/agent/api/loan-tenure");
                const tenures = await response.json();
                this.loanTenures = tenures;
            } catch (error) {
                console.error("Error loading loan tenures:", error);
            }
        },

        async loadTenuresForSubcategory(subcategoryId) {
            if (!subcategoryId) {
                this.loanTenures = [];
                this.loanData.tenure_months = "";
                return;
            }

            try {
                const response = await fetch(
                    `/agent/api/loan-sub-category-tenure?subcategory_id=${subcategoryId}`,
                );
                const tenures = await response.json();

                if (response.ok) {
                    this.loanTenures = tenures;
                    this.loanData.tenure_months = ""; // Reset tenure selection when category changes
                    console.log(
                        "Successfully loaded",
                        tenures.length,
                        "tenures for subcategory",
                    );
                } else {
                    console.error("API Error:", tenures);
                    this.loanTenures = [];
                    this.loanData.tenure_months = "";
                }
            } catch (error) {
                console.error("Error loading tenures for subcategory:", error);
                this.loanTenures = [];
                this.loanData.tenure_months = "";
            }
        },

        async loadMainCategories() {
            try {
                // Determine shop_status based on user type
                // For agents, use "active"; for branches, use "inactive"
                const shopStatus =
                    window.AGENT_SHOPS_COUNT > 0 ? "" : "?shop_status=inactive";
                const response = await fetch(
                    `/agent/api/loan-main-category${shopStatus}`,
                );
                const categories = await response.json();
                this.mainCategories = categories;
                this.categoryError = null;
            } catch (error) {
                console.error("Error loading main categories:", error);
                this.categoryError = "Failed to load categories. Please try again.";
            }
        },

        selectMainCategory(category) {
            this.selectedMainCategory = category;
            if (!this.isShopRequired()) {
                this.loanData.shop_id = "";
            }
            console.log("Selected main category:", category);
        },

        async proceedToLoanDetails() {
            if (!this.selectedMainCategory) {
                return;
            }

            // Load subcategories for the selected main category
            try {
                const response = await fetch(
                    `/agent/api/loan-sub-category?main_category_id=${this.selectedMainCategory.id}`,
                );
                const subcategories = await response.json();

                console.log("API Response status:", response.status);
                console.log("Subcategories loaded:", subcategories);

                if (response.ok) {
                    this.loanCategories = subcategories;
                    this.loanData.loan_category = ""; // Reset loan category selection
                    this.currentStep = 1; // Move to loan details step
                    console.log(
                        "Successfully loaded",
                        subcategories.length,
                        "subcategories",
                    );

                    // Load processing fees for the selected main category
                    this.loadProcessingFees();
                } else {
                    console.error("API Error:", subcategories);
                    this.categoryError =
                        subcategories.error || "Failed to load subcategories";
                }
            } catch (error) {
                console.error("Error loading subcategories:", error);
                this.categoryError =
                    "Failed to load subcategories. Please try again.";
            }
        },

        getStepClass(step) {
            if (this.currentStep > step) {
                return "completed";
            } else if (this.currentStep === step) {
                return "active";
            }
            return "";
        },

        isLoanDetailsValid() {
            this.errors = {};
            if (this.isShopRequired() && Number(window.AGENT_SHOPS_COUNT) > 1) {
                if (!this.loanData.shop_id) {
                    this.errors.shop_id = "Please select shop";
                }
            }
            if (!this.loanData.loan_category) {
                this.errors.loan_category = "Please select loan category";
            }
            if (
                !this.loanData.loan_amount ||
                isNaN(parseFloat(this.loanData.loan_amount))
            ) {
                this.errors.loan_amount = "Please enter a valid loan amount";
            }
            if (!this.loanData.tenure_months) {
                this.errors.tenure_months = "Please select loan tenure";
            }
            if (!this.loanData.loan_purpose) {
                this.errors.loan_purpose = "Please enter loan purpose";
            }
            return Object.keys(this.errors).length === 0;
        },

        isShopRequired() {
            return !!(
                this.selectedMainCategory && this.selectedMainCategory.is_shop_active
            );
        },

        formatLoanAmount() {
            let amount = this.loanData.loan_amount.replace(/[^0-9.]/g, "");
            if (amount) {
                this.loanData.loan_amount =
                    parseFloat(amount).toLocaleString("en-IN");
            }
            this.calculateTotalAmount();
        },

        calculateEMI() {
            console.log("calculating EMI...");
            const amount = (this.loanData.loan_amount || "")
                .toString()
                .replace(/,/g, "")
                .replace(/[^0-9.]/g, "");
            const principal = parseFloat(amount) || 0;
            const rate = parseFloat(this.loanData.interest_rate) || 0;

            // Get actual tenure value, not the ID
            let tenure = 0;
            if (this.loanData.tenure_months) {
                const selectedTenure = this.loanTenures.find(
                    (t) => t.id == this.loanData.tenure_months,
                );
                if (selectedTenure) {
                    tenure = parseInt(selectedTenure.value) || 0;
                    console.log("Found tenure:", selectedTenure);
                }
            }

            const monthlyRate = rate / 12 / 100;

            let emi = 0;

            if (principal > 0 && rate > 0 && tenure > 0) {
                // Calculate EMI using standard formula
                // emi = (principal * monthlyRate * Math.pow(1 + monthlyRate, tenure)) / (Math.pow(1 + monthlyRate, tenure) - 1);
                const interestRatePerMonth = (principal * rate) / 100;
                const totalRepayment = principal + interestRatePerMonth;
                emi = totalRepayment / tenure;

                // Check if calculation resulted in a valid number
                if (isNaN(emi) || emi <= 0 || !isFinite(emi)) {
                    this.loanData.emi_amount = "";
                    console.log("Invalid EMI calculation result");
                    return;
                }

                // Format EMI with Indian number format
                // this.loanData.emi_amount = Math.round(emi).toLocaleString('en-IN');
                this.loanData.emi_amount = Number(emi).toLocaleString("en-IN", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                });
                console.log("calculated -> " + this.loanData.emi_amount);
            } else {
                this.loanData.emi_amount = "";
                console.log("EMI calculation skipped - missing required values");
                console.log(
                    "Principal:",
                    principal,
                    "Rate:",
                    rate,
                    "Tenure:",
                    tenure,
                );
            }
        },

        updateInterestRate() {
            if (this.loanData.loan_category && this.loanData.tenure_months) {
                const selectedTenure = this.loanTenures.find(
                    (t) => t.id == this.loanData.tenure_months,
                );
                if (selectedTenure) {
                    console.log("selectedTenure-", selectedTenure);
                    this.loanData.interest_rate = selectedTenure.interest_rate;
                    this.loanData.interest_rate_display =
                        selectedTenure.interest_rate + "%";
                    this.loanData.interest_rate_id = selectedTenure.interest_id; // Use interest_id, not tenure ID
                }
            }
            this.calculateEMI();
        },

        // Product-related methods

        isProductCategorySelected() {
            const selectedCategory = this.loanCategories.find(
                (cat) => cat.id === this.loanData.loan_category,
            );
            if (selectedCategory == undefined) {
                return false;
            }
            console.log(
                "selectedCategory.has_product_categories-",
                selectedCategory.has_product_categories,
            );
            return selectedCategory && selectedCategory.has_product_categories;
        },

        async loadProductMainCategories() {
            try {
                const selectedCategory = this.loanCategories.find(
                    (cat) => cat.id === this.loanData.loan_category,
                );
                const response = await fetch(
                    `/agent/api/product-category?loan_category_id=${selectedCategory.id}`,
                );
                const categories = await response.json();
                this.productMainCategories = categories;
                console.log("Product main categories loaded:", categories);
            } catch (error) {
                console.error("Error loading product main categories:", error);
            }
        },

        async loadProductSubcategories(mainCategoryId) {
            if (!mainCategoryId) {
                this.productSubcategories = [];
                return;
            }

            try {
                const response = await fetch(
                    `/agent/api/product-sub-category?main_category_id=${mainCategoryId}`,
                );
                const subcategories = await response.json();
                this.productSubcategories = subcategories;
                console.log("Product subcategories loaded:", subcategories);
            } catch (error) {
                console.error("Error loading product subcategories:", error);
                this.productSubcategories = [];
            }
        },

        async loadProductTypes(subcategoryId) {
            if (!subcategoryId) {
                this.productTypes = [];
                return;
            }

            try {
                const response = await fetch(
                    `/agent/api/product-type?subcategory_id=${subcategoryId}`,
                );
                const types = await response.json();
                this.productTypes = types;
                console.log("Product types loaded:", types);
            } catch (error) {
                console.error("Error loading product types:", error);
                this.productTypes = [];
            }
        },

        // Load shop bank accounts for selected shop
        async loadShopBankAccounts(shopId) {
            if (!shopId) {
                this.shopBankAccount = [];
                this.loanData.shop_bank_account_id = "";
                return;
            }

            try {
                const response = await fetch(
                    `/agent/api/shop-bank-accounts/?shop_id=${shopId}`,
                );
                const data = await response.json();
                console.log("Shop bank accounts response:", data);
                console.log("Shop bank accounts response is success:", data.success);

                if (data.success) {
                    this.shopBankAccount = data.bank_accounts || [];
                    console.log(
                        "Loaded shop bank accounts:",
                        this.shopBankAccount.length,
                    );
                } else {
                    this.shopBankAccount = [];
                    console.error("Failed to load shop bank accounts:", data.message);
                }

                // Reset selected bank account when shop changes
                this.loanData.shop_bank_account_id = "";
            } catch (error) {
                console.error("Error loading shop bank accounts:", error);
                this.shopBankAccount = [];
                this.loanData.shop_bank_account_id = "";
            }
        },

        // Load processing fees for selected main category
        async loadProcessingFees() {
            try {
                const response = await fetch(
                    `/agent/api/loan-deductions?main_category_id=${this.selectedMainCategory.id}`,
                );
                const data = await response.json();
                console.log("Raw API response:", data);
                let deductions = data;
                if (!Array.isArray(data)) {
                    deductions =
                        data.data?.deductions || data.data || data.deductions || data;
                    if (!Array.isArray(deductions)) {
                        deductions = [];
                    }
                }
                this.processingFees = (deductions || []).map((fee) => ({
                    ...fee,
                    checked: typeof fee.checked === "undefined" ? true : fee.checked,
                }));
                console.log("Extracted processing fees:", this.processingFees);
                // Calculate total fees after loading
                this.calculateTotalAmount();
            } catch (error) {
                console.error("Error loading processing fees:", error);
                this.processingFees = [];
            }
        },

        // Calculate total amount and down payment based on selected processing fees
        calculateTotalAmount() {
            const loanAmount =
                parseFloat(this.loanData.loan_amount.replace(/,/g, "")) || 0;
            const selectedType = this.productTypes.find(
                (type) => type.id === this.selectedProductType,
            );
            const productPrice = selectedType ? selectedType.price : 0;
            const basePrice = parseFloat(
                this.loanData.sale_price && this.loanData.sale_price > 0
                    ? this.loanData.sale_price
                    : productPrice,
            );

            console.log(
                "calculateTotalAmount - loanAmount:",
                loanAmount,
                "basePrice:",
                basePrice,
                "isProductCategorySelected:",
                this.isProductCategorySelected(),
            );
            console.log(
                "calculateTotalAmount - processingFees:",
                this.processingFees,
            );

            let totalFees = 0;
            if (this.isProductCategorySelected()) {
                console.log("Calculating fees for product category");
                // For product categories, sum all processing fees
                console.log("Processing fees:", this.processingFees);
                this.processingFees.forEach((fee) => {
                    console.log("Processing fee:", fee);
                    if (!fee.checked) {
                        return;
                    }
                    if (fee.deduction_type === "percentage") {
                        const feeAmount = (basePrice * fee.deduction_value) / 100;
                        console.log(
                            "Percentage fee calculation:",
                            basePrice,
                            "*",
                            fee.deduction_value,
                            "/ 100 =",
                            feeAmount,
                        );
                        totalFees += feeAmount;
                    } else {
                        console.log("Fixed fee:", fee.deduction_value);
                        totalFees += fee.deduction_value;
                    }
                });
            } else {
                console.log("Calculating fees for non-product category");
                // For non-product categories, sum all processing fees
                this.processingFees.forEach((fee) => {
                    console.log("Processing fee:", fee);
                    if (!fee.checked) {
                        return;
                    }
                    if (fee.deduction_type === "percentage") {
                        const feeAmount = (loanAmount * fee.deduction_value) / 100;
                        console.log(
                            "Percentage fee calculation:",
                            loanAmount,
                            "*",
                            fee.deduction_value,
                            "/ 100 =",
                            feeAmount,
                        );
                        totalFees += feeAmount;
                    } else {
                        console.log("Fixed fee:", fee.deduction_value);
                        totalFees += fee.deduction_value;
                    }
                });
            }

            console.log("Total fees calculated:", totalFees);
            this.totalProcessingFees = "₹" + totalFees.toLocaleString("en-IN");

            if (this.isProductCategorySelected()) {
                this.loanData.processing_fee = totalFees.toLocaleString("en-IN");
                this.loanData.total_loan_amount = (
                    loanAmount + totalFees
                ).toLocaleString("en-IN");
                this.loanData.down_payment = (
                    basePrice +
                    totalFees -
                    loanAmount
                ).toLocaleString("en-IN");
            }
        },
        // Update loan amount based on sale price or product selection
        updateLoanAmount() {
            if (this.selectedProductType) {
                const selectedType = this.productTypes.find(
                    (type) => type.id === this.selectedProductType,
                );
                if (selectedType) {
                    if (this.loanData.sale_price && this.loanData.sale_price > 0) {
                        this.loanData.loan_amount = this.loanData.sale_price;
                    } else {
                        this.loanData.loan_amount = selectedType.price;
                    }
                    this.loanData.loan_percentage = ""; // Clear percentage when product is selected
                    this.formatLoanAmount();
                    this.calculateEMI();
                }
            }
        },

        updateLoanAmountBasedOnProductSelection() {
            this.updateLoanAmount();
        },

        calculateLoanAmountFromPercentage() {
            if (this.selectedProductType && this.loanData.loan_percentage) {
                const selectedType = this.productTypes.find(
                    (type) => type.id === this.selectedProductType,
                );
                if (selectedType) {
                    const basePrice =
                        this.loanData.sale_price && this.loanData.sale_price > 0
                            ? this.loanData.sale_price
                            : selectedType.price;
                    const percentage = parseFloat(this.loanData.loan_percentage);
                    if (!isNaN(percentage) && percentage > 0 && percentage <= 100) {
                        const calculatedAmount = basePrice * (percentage / 100);
                        console.log(
                            "Calculated amount:",
                            calculatedAmount,
                            "Base price:",
                            basePrice,
                        );
                        this.loanData.loan_amount = calculatedAmount.toFixed(2);
                        this.formatLoanAmount();
                        this.calculateEMI();
                    }
                }
            }
        },

        nextStep() {
            if (this.validateCurrentStep()) {
                this.completedSteps.push(this.currentStep);
                this.currentStep++;
                this.errors = {};
            }
        },

        previousStep() {
            // Prevent going back if Aadhaar is verified and we're past verification step
            if (this.otpVerified && this.currentStep > 2) {
                return;
            }

            // If going back from step 1 to step 0, reset loan categories
            if (this.currentStep === 1) {
                this.loanCategories = []; // Clear categories
                this.loanData.loan_category = ""; // Reset selection
            }

            this.currentStep--;
            this.errors = {};
        },

        formatDateOfBirth(event) {
            const raw =
                event && event.target
                    ? event.target.value
                    : this.personalInfo.date_of_birth;
            const digits = String(raw || "")
                .replace(/\D/g, "")
                .slice(0, 8);
            const d = digits.slice(0, 2);
            const m = digits.slice(2, 4);
            const y = digits.slice(4, 8);

            let formatted = d;
            if (digits.length > 2) formatted += "-" + m;
            if (digits.length > 4) formatted += "-" + y;

            this.personalInfo.date_of_birth = formatted;
        },

        // PAN format validation
        validatePANFormat() {
            this.personalInfo.pan_number =
                this.personalInfo.pan_number.toUpperCase();
            if (this.personalInfo.pan_number.length === 10) {
                if (!/^[A-Z]{5}\d{4}[A-Z]$/.test(this.personalInfo.pan_number)) {
                    this.errors.pan_number =
                        "Invalid PAN format. Format: 5 letters, 4 digits, 1 letter";
                    this.panVerificationStatus = null;
                } else {
                    this.errors.pan_number = null;
                }
            } else {
                this.errors.pan_number = null;
                this.panVerificationStatus = null;
            }
        },

        // Verify PAN-Aadhaar linking
        async verifyPANAadhaarLink() {
            const pan = this.personalInfo.pan_number;

            if (!pan || pan.length !== 10) {
                return;
            }

            if (!/^[A-Z]{5}\d{4}[A-Z]$/.test(pan)) {
                return;
            }

            // Get Aadhaar number from local verification data (entered in step 2)
            const aadhaarRaw = this.verificationData.aadhaar;
            const aadhaar = String(aadhaarRaw || "").replace(/\D/g, "");

            if (!aadhaar || aadhaar.length !== 12) {
                console.error(
                    "Aadhaar number not found/invalid for PAN verification",
                );
                this.panVerificationStatus = null;
                this.errors.pan_number =
                    "Aadhaar number not found/invalid for PAN verification";
                return;
            }
            console.log("Aadhaar number:", aadhaar);
            // Check if we should use mock verification (when Aadhaar verification was mocked)
            if (
                window.aadhaarVerification &&
                window.aadhaarVerification.mockAadhaarVerification
            ) {
                // Use mock PAN verification
                console.log("Using mock PAN verification");
                console.log("this.mockPanVerification:", this.mockPanVerification);
                if (this.mockPanVerification) {
                    this.panVerificationStatus = "checking";
                    setTimeout(() => {
                        this.mockPanVerification();
                    }, 1000); // Simulate API delay
                }
                return;
            }

            this.panVerificationStatus = "checking";

            try {
                const response = await fetch("/agent/api/verify-pan-aadhaar/", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": this.getCSRFToken(),
                    },
                    body: JSON.stringify({
                        pan_number: pan,
                        aadhaar_number: aadhaar,
                    }),
                });

                const data = await response.json();

                if (data.success) {
                    this.panVerificationStatus = data.is_linked
                        ? "linked"
                        : "not_linked";
                    if (data.is_linked) {
                        this.errors.pan_number = null;
                    } else {
                        this.errors.pan_number =
                            "PAN is not linked to Aadhaar, Enter valid PAN number";
                    }
                } else {
                    this.panVerificationStatus = "not_linked";
                    this.errors.pan_number =
                        data.message || "Failed to verify PAN-Aadhaar linking";
                }
            } catch (error) {
                console.error("PAN verification error:", error);
                this.panVerificationStatus = "not_linked";
                this.errors.pan_number = "Failed to verify PAN-Aadhaar linking";
            }
        },

        // Mock PAN verification method (accessible globally)
        mockPanVerification() {
            console.log("Mock PAN verification called");
            // Mock PAN verification - simulate successful PAN-Aadhaar linking
            if (window.Alpine) {
                const appElement = document.querySelector(
                    '[x-data*="loanApplication"]',
                );
                if (appElement) {
                    const alpineData = Alpine.$data(appElement);
                    if (alpineData) {
                        // Set PAN verification status to linked
                        alpineData.panVerificationStatus = "linked";
                        showToast(
                            "PAN verified successfully! PAN is linked to Aadhaar.",
                            "success",
                        );

                        // You could also populate some mock PAN data if needed
                        if (
                            alpineData.personalInfo &&
                            alpineData.personalInfo.pan_number
                        ) {
                            console.log(
                                "PAN verified:",
                                alpineData.personalInfo.pan_number,
                            );
                        }
                    }
                }
            }
        },

        // Get CSRF token
        getCSRFToken() {
            const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]");
            return csrfToken ? csrfToken.value : "";
        },

        isPersonalInfoValidate() {
            const fullName = (this.personalInfo.full_name || "").trim();
            const fatherName = (this.personalInfo.father_name || "").trim();
            const guarantorName = (this.personalInfo.guarantor_name || "").trim();
            const dob = (this.personalInfo.date_of_birth || "").trim();
            const gender = (this.personalInfo.gender || "").trim();
            const address = (this.personalInfo.address || "").trim();
            const pincode = String(this.personalInfo.pincode || "").trim();
            const pan = (this.personalInfo.pan_number || "").trim().toUpperCase();

            if (
                !fullName ||
                !fatherName ||
                !guarantorName ||
                !dob ||
                !gender ||
                !address ||
                !pincode ||
                !pan
            ) {
                this.errors.personal_info = "Please fill all required fields";
                return false;
            }

            // DOB can come as DD-MM-YYYY (from Aadhaar) or YYYY-MM-DD
            if (
                !/^\d{2}-\d{2}-\d{4}$/.test(dob) &&
                !/^\d{4}-\d{2}-\d{2}$/.test(dob)
            ) {
                this.errors.personal_info = "Please enter a valid Date of Birth";
                return false;
            }

            if (!/^\d{6}$/.test(pincode)) {
                this.errors.personal_info = "Please enter a valid 6-digit pincode";
                return false;
            }

            if (!/^[A-Z]{5}\d{4}[A-Z]$/.test(pan)) {
                this.errors.pan_number =
                    "Invalid PAN format. Format: 5 letters, 4 digits, 1 letter";
                return false;
            }

            if (this.panVerificationStatus === "not_linked") {
                this.errors.pan_number = "PAN must be linked to Aadhaar to proceed";
                return false;
            }
            if (this.panVerificationStatus === "checking") {
                this.errors.pan_number =
                    "Please wait for PAN verification to complete";
                return false;
            }
            if (this.panVerificationStatus === null) {
                this.errors.pan_number = "Please verify PAN-Aadhaar linking";
                return false;
            }

            this.errors.personal_info = null;
            this.errors.pan_number = null;
            return true;
        },

        // Bank account verification
        async verifyBankAccount() {
            if (!this.isBankDetailsValid()) {
                return;
            }

            this.bankVerificationStatus = "verifying";
            this.bankVerificationMessage = null;
            this.bankVerificationData = null;

            try {
                const response = await fetch("/agent/api/verify-bank-account/", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": this.getCSRFToken(),
                    },
                    body: JSON.stringify({
                        account_number: this.bankDetails.account_number,
                        ifsc_code: this.bankDetails.ifsc_code,
                        name: this.personalInfo.full_name || this.personalInfo.name,
                        phone: this.verificationData.mobile,
                    }),
                });

                const data = await response.json();

                if (data.success) {
                    this.bankVerificationStatus = "verified";
                    this.bankVerificationData = data.data;
                    this.bankVerificationMessage = data.message;
                    showToast(data.message, "success");

                    // Auto-populate bank details from verification
                    if (data.data) {
                        this.bankDetails.bank_name =
                            data.data.bank_name || this.bankDetails.bank_name;
                        this.bankDetails.account_type = data.data.account_type
                            ? data.data.account_type.toLowerCase()
                            : this.bankDetails.account_type;
                    }
                } else {
                    this.bankVerificationStatus = "failed";
                    this.bankVerificationMessage = data.message;
                }
            } catch (error) {
                console.error("Bank verification error:", error);
                this.bankVerificationStatus = "failed";
                this.bankVerificationMessage =
                    "Network error occurred during verification";
            }
        },

        // Validate bank details for verification
        isBankDetailsValid() {
            return (
                this.bankDetails.account_number &&
                this.bankDetails.account_number.length >= 9 &&
                this.bankDetails.account_number.length <= 18 &&
                this.bankDetails.ifsc_code &&
                this.bankDetails.ifsc_code.length === 11 &&
                /^[A-Z]{4}0[A-Z0-9]{6}$/.test(this.bankDetails.ifsc_code) &&
                this.bankDetails.confirm_account_number ===
                this.bankDetails.account_number
            );
        },

        validateCurrentStep() {
            this.errors = {};

            if (this.currentStep === 1) {
                return this.isLoanDetailsValid();
            }

            if (this.currentStep === 2) {
                // Check if Aadhaar is verified using the external verification
                if (
                    window.aadhaarVerification &&
                    typeof window.aadhaarVerification.isVerified === "function"
                ) {
                    if (!window.aadhaarVerification.isVerified()) {
                        this.errors.verification =
                            "Please verify Aadhaar OTP to continue";
                        return false;
                    }
                } else {
                    this.errors.verification =
                        "Aadhaar verification is not available. Please refresh the page.";
                    return false;
                }
                return true;
            }

            if (this.currentStep === 3) {
                // Validate personal info step - check required fields are populated
                return this.isPersonalInfoValidate();
            }

            if (this.currentStep === 4) {
                // Validate address step
                if (
                    !this.addressData.permanent.address_line_1 ||
                    !this.addressData.permanent.post_code ||
                    !this.addressData.permanent.city_or_town ||
                    !this.addressData.permanent.district ||
                    !this.addressData.permanent.state
                ) {
                    this.errors.address =
                        "Please fill all required permanent address fields";
                    return false;
                }

                // If same address is not checked, validate current address
                if (!this.addressData.sameAddress) {
                    if (
                        !this.addressData.current.address_line_1 ||
                        !this.addressData.current.post_code ||
                        !this.addressData.current.city_or_town ||
                        !this.addressData.current.district ||
                        !this.addressData.current.state
                    ) {
                        this.errors.current_address =
                            "Please fill all required current address fields";
                        return false;
                    }
                }

                return true;
            }

            if (this.currentStep === 5) {
                // Validate bank details step
                return this.isBankDetailsVeryfied();
            }

            return true;
        },

        isBankDetailsVeryfied() {
            if (!this.bankDetails.account_number || !this.bankDetails.ifsc_code) {
                this.errors.bank_details = "Please fill all required bank details";
                return false;
            }
            if (this.bankVerificationStatus != "verified") {
                this.errors.bank_details = "Please verify your bank account";
                return false;
            }
            return true;
        },

        toggleCurrentAddress() {
            if (this.addressData.sameAddress) {
                // Copy permanent address to current address
                Object.assign(this.addressData.current, this.addressData.permanent);
            }
        },

        // Handle file uploads
        handleFileUpload(event, documentType) {
            const file = event.target.files[0];
            if (file) {
                // Store file in documents object
                this.documents[documentType] = file;

                // Clear any existing error for this document type
                if (this.errors[documentType]) {
                    this.errors[documentType] = null;
                }

                console.log(`File uploaded: ${documentType}`, file);
            }
        },

        // Submit application
        async submitApplication() {
            if (this.isSubmitting) {
                return;
            }

            this.errors = {};

            try {
                // Show preview before submission and stop here
                this.showPreview();
                return; // Stop here - actual submission will happen from confirmSubmit
            } catch (error) {
                console.error("Submit error:", error);
                alert("Network error occurred. Please try again.");
            }
        },

        // Show preview modal
        showPreview() {
            const modal = document.getElementById("preview-modal");
            if (!modal) return;

            // Get Alpine data instance of the modal
            const modalData = Alpine.$data(modal);

            if (modalData) {
                // Directly update the existing Alpine data
                modalData.processingFees = this.processingFees || [];
                modalData.totalProcessingFees = this.totalProcessingFees || "₹0";
            } else {
                console.warn("Preview modal Alpine data not found");
            }

            // Populate all other fields
            this.populatePreviewFields();

            // Show modal
            modal.classList.remove("hidden");
        },

        // Populate preview fields with form data
        populatePreviewFields() {
            // Personal Information
            this.setPreviewValue("preview_full_name", this.personalInfo.full_name);
            this.setPreviewValue(
                "preview_date_of_birth",
                this.personalInfo.date_of_birth,
            );
            this.setPreviewValue("preview_gender", this.personalInfo.gender);
            this.setPreviewValue("preview_contact", this.verificationData.mobile);
            this.setPreviewValue("preview_email", this.personalInfo.email);
            this.setPreviewValue(
                "preview_adhar_number",
                this.verificationData.aadhaar,
            );
            this.setPreviewValue(
                "preview_pan_number",
                this.personalInfo.pan_number,
            );
            this.setPreviewValue(
                "preview_voter_number",
                this.personalInfo.voter_number,
            );
            this.setPreviewValue(
                "preview_guarantor_name",
                this.personalInfo.guarantor_name,
            );

            // Permanent Address
            this.setPreviewValue(
                "preview_address_line_1",
                this.addressData.permanent.address_line_1,
            );
            this.setPreviewValue(
                "preview_address_line_2",
                this.addressData.permanent.address_line_2,
            );
            this.setPreviewValue(
                "preview_landmark",
                this.addressData.permanent.landmark,
            );
            this.setPreviewValue(
                "preview_post_office",
                this.addressData.permanent.post_office,
            );
            this.setPreviewValue(
                "preview_city_or_town",
                this.addressData.permanent.city_or_town,
            );
            this.setPreviewValue(
                "preview_district",
                this.addressData.permanent.district,
            );
            this.setPreviewValue("preview_state", this.addressData.permanent.state);
            this.setPreviewValue(
                "preview_country",
                this.addressData.permanent.country,
            );
            this.setPreviewValue(
                "preview_post_code",
                this.addressData.permanent.post_code,
            );

            // Current Address
            this.setPreviewValue(
                "preview_current_address_line_1",
                this.addressData.current.address_line_1,
            );
            this.setPreviewValue(
                "preview_current_address_line_2",
                this.addressData.current.address_line_2,
            );
            this.setPreviewValue(
                "preview_current_landmark",
                this.addressData.current.landmark,
            );
            this.setPreviewValue(
                "preview_current_post_office",
                this.addressData.current.post_office,
            );
            this.setPreviewValue(
                "preview_current_city_or_town",
                this.addressData.current.city_or_town,
            );
            this.setPreviewValue(
                "preview_current_district",
                this.addressData.current.district,
            );
            this.setPreviewValue(
                "preview_current_state",
                this.addressData.current.state,
            );
            this.setPreviewValue(
                "preview_current_country",
                this.addressData.current.country,
            );
            this.setPreviewValue(
                "preview_current_post_code",
                this.addressData.current.post_code,
            );
            this.setPreviewValue(
                "preview_residential_proof_type",
                this.documents.residential_proof_type,
            );
            this.setPreviewDocumentValue(
                "preview_residential_proof_file",
                this.documents.residential_proof_file,
            );

            // Loan Details
            this.setPreviewValue(
                "preview_loan_category",
                this.loanData.loan_category,
            );
            this.setPreviewValue("preview_loan_amount", this.loanData.loan_amount);
            this.setPreviewValue(
                "preview_tenure_months",
                this.loanData.tenure_months,
            );
            this.setPreviewValue(
                "preview_loan_purpose",
                this.loanData.loan_purpose,
            );
            this.setPreviewValue(
                "preview_interest_rate",
                this.loanData.interest_rate,
            );
            this.setPreviewValue("preview_emi_amount", this.loanData.emi_amount);
            const selectedType = this.productTypes.find(
                (type) => type.id === this.selectedProductType,
            );

            this.setPreviewValue(
                "preview_selected_product",
                selectedType ? selectedType.name : "N/A",
            );
            this.setPreviewValue(
                "preview_loan_percentage",
                this.loanData.loan_percentage,
            );
            this.setPreviewValue("preview_sale_price", this.loanData.sale_price);
            this.setPreviewValue(
                "preview_processing_fee",
                this.loanData.processing_fee,
            );
            this.setPreviewValue(
                "preview_down_payment",
                this.loanData.down_payment,
            );
            this.setPreviewValue(
                "preview_total_loan_amount",
                this.loanData.total_loan_amount,
            );

            // Hide/show product-related fields based on selected product
            const selectedProduct = this.productTypes.find(
                (type) => type.id === this.selectedProductType,
            );
            const hasProduct =
                selectedProduct &&
                selectedProduct.name &&
                selectedProduct.name !== "N/A";

            // Product-related containers
            const containers = [
                "preview_loan_percentage_container",
                "preview_sale_price_container",
                "preview_processing_fee_container",
                "preview_down_payment_container",
                "preview_total_loan_amount_container",
                "preview_product_main_category_container",
                "preview_product_subcategory_container",
                "preview_product_type_container",
            ];

            containers.forEach((containerId) => {
                const container = document.getElementById(containerId);
                if (container) {
                    container.style.display = hasProduct ? "block" : "none";
                }
            });

            // Product details
            const selectedMainCategory = this.productMainCategories.find(
                (cat) => cat.id === this.selectedProductMainCategory,
            );
            const selectedSubcategory = this.productSubcategories.find(
                (sub) => sub.id === this.selectedProductSubcategory,
            );
            this.setPreviewValue(
                "preview_product_main_category",
                selectedMainCategory ? selectedMainCategory.name : "N/A",
            );
            this.setPreviewValue(
                "preview_product_subcategory",
                selectedSubcategory ? selectedSubcategory.name : "N/A",
            );
            this.setPreviewValue(
                "preview_product_type",
                selectedType
                    ? `${selectedType.name} (₹${selectedType.price})`
                    : "N/A",
            );

            // Bank Details
            this.setPreviewValue(
                "preview_account_number",
                this.bankDetails.account_number,
            );
            this.setPreviewValue(
                "preview_confirm_account_number",
                this.bankDetails.confirm_account_number,
            );
            this.setPreviewValue("preview_bank_name", this.bankDetails.bank_name);
            this.setPreviewValue(
                "preview_account_type",
                this.bankDetails.account_type,
            );
            this.setPreviewValue("preview_ifsc_code", this.bankDetails.ifsc_code);

            // Documents
            this.setPreviewDocumentValue(
                "preview_guarantor_id_proof",
                this.documents.guarantor_id_proof,
            );
            this.setPreviewDocumentValue(
                "preview_id_proof",
                this.documents.id_proof,
            );
            this.setPreviewDocumentValue(
                "preview_id_proof_back",
                this.documents.id_proof_back,
            );
            this.setPreviewDocumentValue(
                "preview_pan_card_document",
                this.documents.pan_card,
            );
            this.setPreviewDocumentValue(
                "preview_income_proof",
                this.documents.income_proof,
            );
            this.setPreviewDocumentValue("preview_collaterol", "Not uploaded"); // Assuming no collateral field
            this.setPreviewDocumentValue("preview_photo", this.documents.photo);
            this.setPreviewDocumentValue(
                "preview_signature",
                this.documents.signature,
            );

            if (this.addressData.sameAddress) {
                this.hideCurrentAddressSections();
            } else {
                this.hideCurrentAddressSections("flex");
            }
            this.hideEmptyProductSections();
        },

        hideCurrentAddressSections(display = "none") {
            // Check processing fees section - hide entire section if no fees
            const currentAddressLine1Field = document.getElementById(
                "preview_current_address_line_1",
            );
            console.log("******************1");
            if (currentAddressLine1Field) {
                // First check if processing fee field has data
                const currentAddressSection = currentAddressLine1Field.parentElement;
                console.log("******************2");
                if (currentAddressSection) {
                    const currentAddressContainer = currentAddressSection.parentElement;
                    console.log("******************3");
                    if (currentAddressContainer) {
                        currentAddressContainer.style.display = display;
                        const currentAddressSectionHR =
                            currentAddressContainer.previousElementSibling;
                        console.log("******************4");
                        if (currentAddressSectionHR) {
                            currentAddressSectionHR.style.display = display;
                        }
                        const currentAddressSectionDIV =
                            currentAddressSectionHR.previousElementSibling;
                        console.log("******************5");
                        if (currentAddressSectionDIV) {
                            currentAddressSectionDIV.style.display =
                                display == "flex" ? "block" : display;
                        }
                    }
                }
            }
        },

        hideEmptyInputFields(formDataEntries) {
            const extraFieldNames = [
                "guarantor_name",
                "guarantor_id_proof",
                "total_processing_fees_indian",
            ];
            const fieldNames = Array.from(
                formDataEntries,
                ([fieldName]) => fieldName,
            ).concat(extraFieldNames);

            for (const fieldName of fieldNames) {
                const previewField = document.getElementById("preview_" + fieldName);
                if (!previewField) continue;
                container = previewField.parentElement;

                if (container) {
                    const input = container.querySelector("input");
                    if (input && input.value && input.value.trim() !== "") {
                        container.style.display = "block";
                    } else {
                        container.style.display = "none";
                    }
                    if (fieldName === "account_number") {
                        hideEmptyBankSectionHeader(container.style.display);
                    }
                }
            }
        },

        hideEmptyBankSectionHeader(display = "block") {
            const previewField = document.getElementById("preview_account_number");
            if (!previewField) return;
            inputContainer = previewField.parentElement;
            if (!inputContainer) return;
            container = inputContainer.parentElement;
            if (!container) return;
            const sectionHR = container.previousElementSibling;
            if (!sectionHR) return;
            const sectionDIV = sectionHR.previousElementSibling;
            if (!sectionDIV) return;
            sectionHR.style.display = display;
            sectionDIV.style.display = display;
        },

        hideEmptyProductSections() {
            // Hide/show individual product field containers based on data
            const productContainers = [
                "preview_selected_product",
                "preview_loan_percentage_container",
                "preview_sale_price_container",
                "preview_processing_fee_container",
                "preview_down_payment_container",
                "preview_total_loan_amount_container",
                "preview_product_main_category_container",
                "preview_product_subcategory_container",
                "preview_product_type_container",
            ];

            productContainers.forEach((containerId) => {
                let container = document.getElementById(containerId);
                if (!containerId.endsWith("_container")) {
                    container = container.parentElement;
                }
                if (container) {
                    const input = container.querySelector("input");
                    if (
                        input &&
                        input.value &&
                        input.value.trim() !== "" &&
                        input.value.trim() !== "N/A"
                    ) {
                        container.style.display = "block";
                    } else {
                        container.style.display = "none";
                    }
                }
            });

            // Check processing fees section - hide entire section if no fees
            const processingFeesContainer = document.getElementById(
                "preview_processing_fees_container",
            );
            if (processingFeesContainer) {
                // First check if processing fee field has data
                const processingFeeField = document.getElementById(
                    "preview_processing_fee",
                );
                let hasProcessingFee = false;

                if (
                    processingFeeField &&
                    processingFeeField.value &&
                    processingFeeField.value.trim() !== ""
                ) {
                    hasProcessingFee = true;
                }

                // Also check Alpine data for additional fees
                const modal = document.getElementById("preview-modal");
                let hasAlpineFees = false;

                if (modal && window.Alpine) {
                    try {
                        // Try to get Alpine data for the modal
                        const alpineData = window.Alpine.$data(modal);
                        if (
                            alpineData &&
                            alpineData.processingFees &&
                            alpineData.processingFees.length > 0
                        ) {
                            hasAlpineFees = true;
                        }
                    } catch (e) {
                        // Fallback to field checking if Alpine access fails
                    }
                }

                // Show container only if there are any processing fees
                if (hasProcessingFee || hasAlpineFees) {
                    processingFeesContainer.style.display = "block";
                } else {
                    processingFeesContainer.style.display = "none";
                }

                const processingFeesSectionHR =
                    processingFeesContainer.previousElementSibling;
                if (processingFeesSectionHR) {
                    // Show entire section only if there are any processing fees
                    if (hasProcessingFee || hasAlpineFees) {
                        processingFeesSectionHR.style.display = "block";
                    } else {
                        processingFeesSectionHR.style.display = "none";
                    }
                }

                const processingFeesSectionDIV =
                    processingFeesSectionHR.previousElementSibling;
                if (processingFeesSectionDIV) {
                    // Show entire section only if there are any processing fees
                    if (hasProcessingFee || hasAlpineFees) {
                        processingFeesSectionDIV.style.display = "block";
                    } else {
                        processingFeesSectionDIV.style.display = "none";
                    }
                }
            }
        },

        // Helper function to set preview field value
        setPreviewDocumentValue(fieldId, filePath) {
            const field = document.getElementById(fieldId);
            let elementValue = "N/A";
            if (typeof filePath === "string") {
                elementValue =
                    filePath == "Not uploaded" || filePath.includes("cloudinary")
                        ? filePath
                        : "N/A";
            } else if (typeof filePath === "object") {
                elementValue = filePath ? filePath.name : "Not Uploaded";
            }
            if (field) {
                field.value = elementValue;
            }
        },
        // Helper function to set preview field value
        setPreviewValue(fieldId, value) {
            const field = document.getElementById(fieldId);
            if (field) {
                field.value = value || "N/A";
            }
        },

        // Perform actual form submission
        async performActualSubmission() {
            this.isSubmitting = true;

            try {
                // Create FormData for file uploads
                const formData = new FormData();

                if (this.selectedCustomerId) {
                    formData.append("customer_id", this.selectedCustomerId);
                }

                // Add all form data
                if (this.loanData.shop_id) {
                    formData.append("shop_id", this.loanData.shop_id);
                } else {
                    const shopInput = document.querySelector("input[name='shop_id']");
                    if (shopInput && shopInput.value) {
                        formData.append("shop_id", shopInput.value);
                    }
                }
                if (this.loanData.shop_bank_account_id) {
                    formData.append(
                        "shop_bank_account_id",
                        this.loanData.shop_bank_account_id,
                    );
                }

                formData.append("loan_category", this.loanData.loan_category);
                formData.append(
                    "loan_amount",
                    this.loanData.loan_amount.replace(/,/g, ""),
                );
                formData.append("tenure_months", this.loanData.tenure_months);
                formData.append("loan_purpose", this.loanData.loan_purpose);
                formData.append("interest_rate", this.loanData.interest_rate_id);
                formData.append(
                    "emi_amount",
                    this.loanData.emi_amount.replace(/,/g, ""),
                );
                formData.append("sale_price", this.loanData.sale_price || 0);
                //formData.append("processing_fee", this.loanData.processing_fee ? this.loanData.processing_fee.replace(/,/g, "") : "");
                formData.append(
                    "down_payment",
                    this.loanData.down_payment
                        ? this.loanData.down_payment.replace(/,/g, "")
                        : 0,
                );
                formData.append(
                    "total_loan_amount",
                    this.loanData.total_loan_amount
                        ? this.loanData.total_loan_amount.replace(/,/g, "")
                        : 0,
                );
                formData.append("loan_purpose", this.loanData.loan_purpose);
                formData.append(
                    "processing_fees_data",
                    JSON.stringify(this.processingFees),
                );
                formData.append("total_processing_fees", this.totalProcessingFees);

                // Add verification data
                formData.append("adhar_number", this.verificationData.aadhaar);
                formData.append("contact", this.verificationData.mobile);

                // Add personal info
                formData.append("full_name", this.personalInfo.full_name);
                formData.append("father_name", this.personalInfo.father_name);
                formData.append("guarantor_name", this.personalInfo.guarantor_name);
                const dobRaw = String(this.personalInfo.date_of_birth || "").trim();
                const dateParts = dobRaw.split("-");
                let formattedDate = dobRaw;
                if (dateParts.length === 3) {
                    if (dateParts[0] && dateParts[0].length === 4) {
                        formattedDate = dobRaw;
                    } else {
                        formattedDate = `${dateParts[2]}-${dateParts[1]}-${dateParts[0]}`;
                    }
                }
                formData.append("date_of_birth", formattedDate);
                formData.append("gender", this.personalInfo.gender);
                formData.append("email", this.personalInfo.email);
                formData.append("pan_number", this.personalInfo.pan_number);
                formData.append("voter_number", this.personalInfo.voter_number);

                // Add address data
                formData.append(
                    "address_line_1",
                    this.addressData.permanent.address_line_1,
                );
                formData.append(
                    "address_line_2",
                    this.addressData.permanent.address_line_2,
                );
                formData.append("landmark", this.addressData.permanent.landmark);
                formData.append("post_code", this.addressData.permanent.post_code);
                formData.append(
                    "post_office",
                    this.addressData.permanent.post_office,
                );
                formData.append(
                    "city_or_town",
                    this.addressData.permanent.city_or_town,
                );
                formData.append("district", this.addressData.permanent.district);
                formData.append("state", this.addressData.permanent.state);
                formData.append("country", this.addressData.permanent.country);

                formData.append(
                    "same_address",
                    this.addressData.sameAddress ? "on" : "off",
                );

                // Add current address fields (always required by API)
                if (this.addressData.sameAddress) {
                    // Copy permanent address to current address fields
                    formData.append(
                        "current_address_line_1",
                        this.addressData.permanent.address_line_1,
                    );
                    formData.append(
                        "current_address_line_2",
                        this.addressData.permanent.address_line_2,
                    );
                    formData.append(
                        "current_landmark",
                        this.addressData.permanent.landmark,
                    );
                    formData.append(
                        "current_post_code",
                        this.addressData.permanent.post_code,
                    );
                    formData.append(
                        "current_post_office",
                        this.addressData.permanent.post_office,
                    );
                    formData.append(
                        "current_city_or_town",
                        this.addressData.permanent.city_or_town,
                    );
                    formData.append(
                        "current_district",
                        this.addressData.permanent.district,
                    );
                    formData.append("current_state", this.addressData.permanent.state);
                    formData.append(
                        "current_country",
                        this.addressData.permanent.country,
                    );
                    // Add empty residential proof when same address (API requires the field)
                    formData.append("residential_proof_type", "");
                    formData.append("residential_proof_file", "");
                } else {
                    // Use current address fields when different
                    formData.append(
                        "current_address_line_1",
                        this.addressData.current.address_line_1,
                    );
                    formData.append(
                        "current_address_line_2",
                        this.addressData.current.address_line_2,
                    );
                    formData.append(
                        "current_landmark",
                        this.addressData.current.landmark,
                    );
                    formData.append(
                        "current_post_code",
                        this.addressData.current.post_code,
                    );
                    formData.append(
                        "current_post_office",
                        this.addressData.current.post_office,
                    );
                    formData.append(
                        "current_city_or_town",
                        this.addressData.current.city_or_town,
                    );
                    formData.append(
                        "current_district",
                        this.addressData.current.district,
                    );
                    formData.append("current_state", this.addressData.current.state);
                    formData.append(
                        "current_country",
                        this.addressData.current.country,
                    );
                    // Add residential proof fields when different addresses
                    if (this.documents.residential_proof_type) {
                        formData.append(
                            "residential_proof_type",
                            this.documents.residential_proof_type,
                        );
                    }
                    if (this.documents.residential_proof_file) {
                        formData.append(
                            "residential_proof_file",
                            this.documents.residential_proof_file,
                        );
                    }
                }

                // Add bank details
                formData.append("account_number", this.bankDetails.account_number);
                formData.append(
                    "confirm_account_number",
                    this.bankDetails.confirm_account_number,
                );
                formData.append("ifsc_code", this.bankDetails.ifsc_code);
                formData.append("bank_name", this.bankDetails.bank_name);
                formData.append("account_type", this.bankDetails.account_type);

                // Add documents
                if (this.documents.guarantor_id_proof) {
                    formData.append(
                        "guarantor_id_proof",
                        this.documents.guarantor_id_proof,
                    );
                }
                if (this.documents.id_proof) {
                    formData.append("id_proof", this.documents.id_proof);
                }
                if (this.documents.id_proof_back) {
                    formData.append("id_proof_back", this.documents.id_proof_back);
                }
                if (this.documents.pan_card) {
                    formData.append("pan_card_document", this.documents.pan_card);
                }
                formData.append("loan_purpose", this.loanData.loan_purpose);
                formData.append("product_id", this.selectedProductType || "");
                formData.append(
                    "loan_percentage",
                    this.loanData.loan_percentage || "",
                );
                if (this.documents.income_proof) {
                    formData.append("income_proof", this.documents.income_proof);
                }
                if (this.documents.photo) {
                    formData.append("photo", this.documents.photo);
                }
                if (this.documents.signature) {
                    formData.append("signature", this.documents.signature);
                }

                const csrftoken = this.getCSRFToken();

                const response = await fetch("/agent/api/application-v2/", {
                    method: "POST",
                    body: formData,
                    headers: {
                        "X-CSRFToken": csrftoken,
                    },
                });

                const result = await response.json();

                if (response.ok && result.success) {
                    // Handle automatic PDF download
                    if (result.pdf_download) {
                        try {
                            // console.log('[Download] Triggering automatic PDF download:', result.pdf_download.filename);
                            // Create blob from base64
                            const binaryString = atob(result.pdf_download.content);
                            const bytes = new Uint8Array(binaryString.length);
                            for (let i = 0; i < binaryString.length; i++) {
                                bytes[i] = binaryString.charCodeAt(i);
                            }
                            const blob = new Blob([bytes], { type: "application/pdf" });

                            // Trigger automatic download
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement("a");
                            a.href = url;
                            a.download = result.pdf_download.filename;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            URL.revokeObjectURL(url);
                            // console.log('[Download] PDF download triggered successfully');
                        } catch (pdfError) {
                            console.error(
                                "[Download Error] Failed to trigger PDF download:",
                                pdfError,
                            );
                        }
                    } else {
                        console.log("[Download] No PDF download data in response");
                    }
                    const msg =
                        "Application submitted successfully! Customer ID: " +
                        result.customer_id;
                    try {
                        sessionStorage.setItem(
                            "pending_toast",
                            JSON.stringify({ message: msg, type: "success" }),
                        );
                    } catch (e) { }
                    if (typeof window.showToast === "function") {
                        window.showToast(msg, "success");
                    }
                    this.isSubmitting = false;
                    setTimeout(() => {
                        const parts = window.location.pathname.split("/");
                        const firstParam = parts[1] || "";
                        if (firstParam == "agent") {
                            window.location.href = "/agent/application/";
                        }
                        if (firstParam == "branch") {
                            window.location.href = "/branch/loan-pending/";
                        }
                    }, 1000);
                } else {
                    hideLoader();
                    // Show error message
                    const errMsg =
                        (result && result.message) ||
                        (result &&
                            result.errors &&
                            (result.errors.documents || result.errors.non_field_errors)) ||
                        (result &&
                            result.errors &&
                            Object.entries(result.errors)
                                .map(([key, value]) => `${key}: ${value}`)
                                .join(", ")) ||
                        "Failed to submit application";
                    if (typeof window.showToast === "function") {
                        window.showToast(errMsg, "error");
                    } else {
                        alert(errMsg);
                    }
                }
            } catch (error) {
                hideLoader();
                console.error("Submit error:", error);
                const errMsg = "Network error occurred. Please try again.";
                if (typeof window.showToast === "function") {
                    window.showToast(errMsg, "error");
                } else {
                    alert(errMsg);
                }
            } finally {
                this.isSubmitting = false;
                hideLoader();
            }
        },
    };
}

// Close preview modal
function closePreview() {
    const modal = document.getElementById("preview-modal");
    if (modal) {
        modal.classList.add("hidden");
    }
}

// Confirm and submit application
async function confirmSubmit() {
    const modal = document.getElementById("preview-modal");
    if (modal) {
        modal.classList.add("hidden");
    }
    // Get the Alpine.js component and call the actual submission logic
    const appElement = document.querySelector('[x-data*="loanApplication"]');
    if (appElement) {
        const alpineData = Alpine.$data(appElement);
        if (alpineData) {
            await alpineData.performActualSubmission();
        }
    }
}

// Sync Aadhaar verification with form flow
document.addEventListener("DOMContentLoaded", function () {
    // Aadhaar verification now handles automatic step progression
    // No need to manually enable/disable next button
});