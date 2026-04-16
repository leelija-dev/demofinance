# Excel File Structure Guide for Data Import

This guide describes the required Excel file structure for uploading customer and loan data through the data import system.

## Required Columns

### Customer Information
- **customer_type**: Either "NEW" or "EXISTING"
- **full_name**: Customer's full name (required)
- **date_of_birth**: Date of birth in YYYY-MM-DD format
- **gender**: Gender (MALE/FEMALE/OTHER)
- **contact**: 10-digit mobile number
- **adhar_number**: 12-digit Aadhar number

### Address Information
- **address_line_1**: Permanent address line 1
- **city_or_town**: City/Town
- **district**: District
- **state**: State
- **post_code**: Postal code (6 digits)
- **current_address_line_1**: Current address line 1
- **current_city_or_town**: Current city/town
- **current_district**: Current district
- **current_state**: Current state
- **current_post_code**: Current postal code (6 digits)

### Bank Information
- **account_number**: Bank account number (9-18 digits)
- **bank_name**: Bank name
- **ifsc_code**: IFSC code (11 characters, format: ABCD0XYZ123)
- **account_type**: Account type (savings/current/fixed_deposit/recurring_deposit)

### Loan Information
- **loan_category_name**: Name of the loan category
- **loan_amount**: Loan amount in rupees
- **tenure_value**: Numeric tenure value
- **tenure_unit**: Tenure unit (months/years/weeks/days)
- **loan_purpose**: Purpose of the loan
- **interest_rate**: Interest rate percentage
- **emi_amount**: EMI amount in rupees
- **branch_name**: Branch name where loan is processed

## Optional (Nullable) Columns

### Additional Customer Details
- **father_name**: Father's name
- **guarantor_name**: Guarantor's name
- **email**: Email address
- **pan_number**: PAN card number (10 characters, format: ABCDE1234F)
- **voter_number**: Voter ID number (10 characters, format: ABC1234567)

### Additional Address Details
- **address_line_2**: Permanent address line 2
- **landmark**: Landmark for permanent address
- **post_office**: Post office for permanent address
- **country**: Country (defaults to "India" if not provided)
- **current_address_line_2**: Current address line 2
- **current_landmark**: Landmark for current address
- **current_post_office**: Post office for current address
- **current_country**: Current country (defaults to "India" if not provided)
- **residential_proof_type**: Type of residential proof
  - Options: electricity_bill, water_bill, gas_bill, rental_agreement, bank_passbook, government_certificate, mobile_bill

### Product Information (for product-based loans)
- **product_main_category**: Product main category ID
- **product_subcategory**: Product subcategory ID
- **product_type**: Product type ID
- **sale_price**: Sale price of the product
- **loan_percentage**: Loan percentage (e.g., 80 for 80%)
- **down_payment**: Down payment amount

### Shop Information
- **shop_id**: Shop ID (if applicable)
- **shop_bank_account_id**: Shop bank account ID (if applicable)

### EMI Schedule Information
- **emi_start_date**: EMI start date in YYYY-MM-DD format
- **emi_frequency**: EMI frequency (monthly/weekly/daily)

### Document Upload Information (File Paths)
- **id_proof_path**: File path to ID proof (front) document
- **id_proof_back_path**: File path to ID proof (back) document
- **guarantor_id_proof_path**: File path to guarantor ID proof document
- **pan_card_document_path**: File path to PAN card document
- **photo_path**: File path to customer photograph
- **signature_path**: File path to customer signature
- **income_proof_path**: File path to income proof document
- **collateral_path**: File path to collateral document
- **residential_proof_file_path**: File path to residential proof document

### Agent Information
- **agent_name**: Agent's full name (optional)

## Application Status and Timeline (Optional)

### Status Management
- **application_status**: Current application status
  - Valid values: `pending`, `active`, `success`, `reject`, `rejected_by_branch`, `inactive`, 
    `document_requested`, `resubmitted`, `branch_document_accepted`, `branch_approved`, 
    `branch_resubmitted`, `hq_document_accepted`, `hq_resubmitted`, `hq_approved`, `hq_rejected`, 
    `disbursed`, `disbursed_fund_released`, `document_requested_by_hq`
- **approved_at**: Date when application was approved (YYYY-MM-DD)
- **disbursed_at**: Date when loan was disbursed (YYYY-MM-DD)
- **submitted_at**: Date when application was submitted (YYYY-MM-DD)
- **rejection_reason**: Reason for application rejection
- **document_request_reason**: Reason for document request
- **ever_branch_approved**: Whether application was ever approved by branch (true/false)

## Disbursement Information (Optional)

### Disbursement Details
- **disbursement_amount**: Total disbursement amount
- **disbursement_mode**: Mode of disbursement (Cash/Bank Transfer/UPI/Cheque)
- **disbursement_bank_name**: Destination bank name
- **disbursement_account_number**: Destination account number
- **disbursement_net_amount**: Net amount received by customer
- **disbursement_tax_charges**: Tax/deduction charges
- **disbursement_proof**: Proof of disbursement (file path or reference)
- **disbursement_remarks**: Disbursement remarks
- **disbursement_branch_account_id**: Source branch account ID
- **disbursement_shop_bank_account_id**: Shop bank account ID (for shop loans)
- **disbursement_date**: Disbursement date (YYYY-MM-DD)

## EMI Collection Information (Optional)

### EMI Collection Details
- **emi_collected_amount**: Total EMI amount collected
- **emi_principal_received**: Principal amount received
- **emi_interest_received**: Interest amount received
- **emi_penalty_received**: Penalty amount received
- **emi_payment_mode**: Payment mode (Cash/Bank Transfer/UPI/Cheque)
- **emi_payment_reference**: Payment reference number
- **emi_collected_at**: Collection date/time (YYYY-MM-DD HH:MM:SS)
- **emi_collected_by_agent**: Name of collecting agent
- **emi_collection_remarks**: Collection remarks
- **emi_status**: Collection status (pending/collected/verified/rejected)

## Branch Transaction Information (Optional)

### Transaction Details
- **branch_transaction_type**: Transaction type (CREDIT/DEBIT)
- **branch_transaction_amount**: Transaction amount
- **branch_transaction_purpose**: Transaction purpose
- **branch_transaction_code**: Transaction code
- **branch_transaction_mode**: Transaction mode
- **branch_transaction_description**: Transaction description
- **branch_transaction_date**: Transaction date (YYYY-MM-DD HH:MM:SS)
- **branch_transaction_account_id**: Branch account ID

## Document Upload Process

### File Path Requirements
- Document columns should contain **full file paths** to existing document files
- Files will be copied from specified paths to appropriate system directories
- Supported file formats: Images (JPG, PNG, GIF), PDFs
- Maximum file size: 5MB per document

### Document Types and Destinations
1. **ID Proof (Front)**: `static/customer/id_proof/`
2. **ID Proof (Back)**: `static/customer/id_proof/`
3. **Guarantor ID Proof**: `static/customer/guarantor_id_proof/`
4. **PAN Card**: `static/customer/pan_card/`
5. **Photograph**: `static/customer/photo/`
6. **Signature**: `static/customer/signature/`
7. **Income Proof**: `static/customer/income_proof/`
8. **Collateral**: `static/customer/collateral/`
9. **Residential Proof**: `static/customer/residential_proof/`

### Document Processing
- Files are automatically renamed with unique UUIDs to prevent conflicts
- Original file extensions are preserved
- All documents are linked to the loan application
- Failed file copies are logged but don't stop the import process

## Data Validation

### Format Requirements
- **Dates**: Must be in YYYY-MM-DD format
- **Phone**: Must be 10 digits
- **Aadhar**: Must be 12 digits
- **PAN**: Must follow format ABCDE1234F
- **IFSC**: Must follow format ABCD0XYZ123
- **Email**: Must be valid email format if provided

### Business Rules
- All required columns must be present
- Optional columns can be left empty
- Existing customers must have matching Aadhar number
- Branch, loan category, interest rate, and tenure combinations must exist in the system
- Product information is only required for product-based loan categories

## Sample Data Structure

| customer_type | full_name | date_of_birth | gender | contact | adhar_number | father_name | email | ... |
|--------------|-----------|----------------|--------|---------|--------------|-------------|-------|-----|
| NEW | John Doe | 1990-01-15 | MALE | 9876543210 | 123456789012 | Robert Doe | john@email.com | ... |

## Error Handling

The import system will:
1. Validate all required columns are present
2. Check data formats and business rules
3. Process each row individually
4. Roll back all changes if any critical error occurs
5. Provide detailed error messages for failed rows

## Workflow Examples

### Example 1: New Loan Application with Disbursement
```
| customer_type | full_name | ... | application_status | approved_at | disbursement_amount | disbursement_mode | disbursement_date |
| NEW | John Doe | ... | disbursed | 2024-01-15 | 50000 | Bank Transfer | 2024-01-16 |
```

### Example 2: Existing Loan with EMI Collection
```
| customer_type | full_name | ... | application_status | emi_collected_amount | emi_payment_mode | emi_collected_at | emi_collected_by_agent |
| EXISTING | Jane Smith | ... | active | 5000 | Cash | 2024-01-20 10:30:00 | Agent Name |
```

### Example 3: Branch Transaction Recording
```
| customer_type | full_name | ... | branch_transaction_type | branch_transaction_amount | branch_transaction_purpose |
| NEW | Bob Johnson | ... | DEBIT | 1000 | Processing Fee |
```

## Import Processing Order

The system processes data in the following order:
1. **Customer & Loan Creation** - Basic loan application setup
2. **Document Upload** - Copy and link document files
3. **Status Updates** - Application status and timeline
4. **Disbursement Processing** - Create disbursement logs and transactions
5. **EMI Collection** - Record EMI collections
6. **Branch Transactions** - Create additional branch transactions
7. **Relationship Updates** - Link all related models

## Important Notes

### Status Management
- Status changes are validated against available choices
- Timeline dates (approved_at, disbursed_at) are optional but recommended
- Rejection and document request reasons are stored for audit trail

### Disbursement Processing
- Disbursement automatically creates `DisbursementLog` record
- Updates loan status to 'disbursed'
- Creates corresponding `BranchTransaction` if account specified
- Tax charges calculated automatically: `tax_charges = amount - net_amount`

### EMI Collections
- Creates `EmiCollectionDetail` records
- Links to collecting agent if specified
- Supports all payment modes (Cash, Bank Transfer, UPI, Cheque)

### Branch Transactions
- Can be standalone or linked to disbursement
- Supports both CREDIT and DEBIT transactions
- Links to branch accounts for proper fund tracking

## Tips for Success

1. **Use the template**: Download the sample Excel template for proper column names
2. **Validate data**: Ensure all dates are in YYYY-MM-DD format
3. **Check references**: Verify that branch names, loan categories, and other references exist in the system
4. **Test with small batches**: Start with a few rows to test your data format
5. **Review error messages**: Carefully review any error messages to fix data issues
6. **Status consistency**: Ensure status values match the workflow progression
7. **Amount validation**: Verify all monetary amounts are positive numbers
8. **Date logic**: Ensure timeline dates are in logical order (submitted < approved < disbursed)

## Support

For any issues with the import process:
1. Check the error messages carefully
2. Verify all required columns are present
3. Ensure data formats match the requirements
4. Contact system administrator for system-level issues
