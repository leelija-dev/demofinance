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

## Tips for Success

1. **Use the template**: Download the sample Excel template for proper column names
2. **Validate data**: Ensure all dates are in YYYY-MM-DD format
3. **Check references**: Verify that branch names, loan categories, and other references exist in the system
4. **Test with small batches**: Start with a few rows to test your data format
5. **Review error messages**: Carefully review any error messages to fix data issues

## Support

For any issues with the import process:
1. Check the error messages carefully
2. Verify all required columns are present
3. Ensure data formats match the requirements
4. Contact system administrator for system-level issues
