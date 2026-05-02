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

### EMI Schedule Information (Required for EMI Creation)
- **emi_start_date**: EMI start date in YYYY-MM-DD format
- **emi_frequency**: EMI frequency (monthly/weekly/daily)

## Important: Conditional EMI Schedule Creation

### Status-Based EMI Processing
The system creates EMI schedules based on `application_status`:

| Application Status | EMI Schedule Created | EMI Payments Marked |
|------------------|-------------------|-------------------|
| `disbursed_fund_released` | ✅ Yes | ❌ No |
| `closed` | ✅ Yes | ✅ Yes (All) |
| All Other Statuses | ❌ No | ❌ No |

### Required for EMI Creation
To create EMI schedules, you MUST provide:
1. `application_status` = `disbursed_fund_released` OR `closed`
2. `emi_start_date` (YYYY-MM-DD format)
3. `emi_frequency` (monthly/weekly/daily)
4. `tenure_value` and `tenure_unit` (for calculating installments)

### EMI Payment Completion for Closed Loans
When `application_status` = `closed`:
- Creates EMI schedules based on tenure
- Automatically creates `EmiCollectionDetail` records for ALL installments
- Payment status set to `verified`
- Payment reference set to `CLOSED_LOAN`
- No penalties applied

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

## Conditional EMI Schedule Logic

### EMI Schedule Creation Rules
The system creates EMI schedules based on the loan application status:

- **disbursed_fund_released**: EMI schedules are created normally
- **closed**: EMI schedules are created AND all payments are automatically marked as completed
- **All other statuses**: EMI schedules are NOT created

### EMI Payment Completion for Closed Loans
When `application_status` is set to `closed`:
1. EMI schedules are created based on tenure and frequency
2. For each EMI schedule, an `EmiCollectionDetail` record is automatically created
3. Payment status is set to `verified`
4. Payment reference is set to `CLOSED_LOAN`
5. All amounts (principal, interest) are marked as received
6. No penalties are applied

### Example Usage

#### Disbursed Loan with Active EMI Schedule
```
| application_status | emi_start_date | emi_frequency | tenure_value | tenure_unit |
| disbursed_fund_released | 2024-01-01 | monthly | 12 | months |
```
**Result**: Creates 12 EMI schedules, no payments marked as completed

#### Closed Loan with Completed EMI Schedule
```
| application_status | emi_start_date | emi_frequency | tenure_value | tenure_unit |
| closed | 2024-01-01 | monthly | 12 | months |
```
**Result**: Creates 12 EMI schedules + 12 EMI collection records marked as paid

#### Pending Loan (No EMI Schedule)
```
| application_status | emi_start_date | emi_frequency | tenure_value | tenure_unit |
| pending | 2024-01-01 | monthly | 12 | months |
```
**Result**: No EMI schedules created

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

### EMI Collection Information (Optional) - Using EMI Receive Process
- **emi_collected_amount**: EMI amount collected
- **emi_principal_received**: Principal amount received
- **emi_interest_received**: Interest amount received
- **emi_penalty_received**: Penalty amount received
- **emi_payment_mode**: Payment mode (Cash/Bank Transfer/UPI/Cheque)
- **emi_payment_reference**: Payment reference number
- **emi_collected_at**: Collection date and time
- **emi_collected_by_agent**: Name of collecting agent
- **emi_collection_remarks**: Collection remarks
- **emi_status**: Collection status (pending/collected/verified/rejected)
- **multiple_emi_count**: Number of EMIs to process (for multiple EMI payments)

### Agent Deposit Information (Optional for Agent Collections)
- **online_amount**: Online deposited amount (default: 0)

### Automatic Fields (No Excel Input Required)
- **emi_id**: Automatically linked to first unpaid EMI schedule
- **verified_by**: Automatically assigned to branch manager
- **Denomination quantities**: Automatically calculated based on amount
- **Coin amounts**: Automatically calculated (default: 0)

## EMI Receive Process Integration

### Advanced EMI Processing
The Excel import now uses the same EMI receive process as the EMI schedule interface (`emi-scedule.html`), providing complete financial transaction management.

### EMI Receive Logic
When `emi_status` is set to `verified` in the Excel file:

1. **EMI Schedule Update**: 
   - Marks EMI as paid with payment date
   - Updates late fees and payment references
   - Maintains audit trail

2. **Branch Transaction Creation**:
   - Creates `BranchTransaction` records automatically
   - Uses Chart of Accounts (COA) based on frequency:
     - Daily EMI: COA 122 (Installment collection daily)
     - Weekly EMI: COA 123 (Installment collection group)
     - Monthly EMI: General EMI Collection
   - Updates branch account balances

3. **Financial Integration**:
   - Updates cash account balance
   - Creates complete transaction records
   - Maintains financial data integrity

### EMI Status Processing

| emi_status | EMI Schedule | Branch Transaction | Account Balance |
|------------|-------------|-------------------|----------------|
| `pending` | Unpaid | No transaction | No change |
| `collected` | Unpaid | No transaction | No change |
| `verified` | **Marked Paid** | **Created** | **Updated** |
| `rejected` | Unpaid | No transaction | No change |

### EMI Receive Fields Usage

#### **For Collection Only (emi_status = 'collected')**
```
| emi_collected_amount | emi_principal_received | emi_interest_received | emi_status |
| 5000.00 | 4000.00 | 1000.00 | collected |
```
**Result**: Creates `EmiCollectionDetail` record, EMI remains unpaid

#### **For Full EMI Receive (emi_status = 'verified')**
```
| emi_collected_amount | emi_principal_received | emi_interest_received | emi_status | emi_payment_mode |
| 5000.00 | 4000.00 | 1000.00 | verified | Cash |
```
**Result**: 
- Creates `EmiCollectionDetail` record
- Marks EMI schedule as paid
- Creates branch transaction
- Updates branch account balance

#### **With Penalty and Reference**
```
| emi_collected_amount | emi_principal_received | emi_interest_received | emi_penalty_received | emi_status | emi_payment_reference |
| 5200.00 | 4000.00 | 1000.00 | 200.00 | verified | REF-12345 |
```
**Result**: 
- All standard verification processing
- Penalty amount added to transaction
- Payment reference stored on EMI schedule

### Integration Benefits

#### **Complete Financial Tracking**
- Same logic as manual EMI receive process
- Automatic branch transaction creation
- Proper account balance management

#### **Audit Trail**
- Complete transaction records
- Payment references and timestamps
- Agent assignment and verification

#### **System Consistency**
- Uses same Chart of Accounts codes
- Maintains financial data integrity
- Compatible with existing reporting

## Automatic Collection Type Detection

### Smart Collection Processing
The Excel import system automatically detects whether EMI collections are made by agents or by the branch, without requiring any manual configuration.

### Detection Logic

#### **1. Explicit Agent Specification**
If `emi_collected_by_agent` contains a valid agent name (not 'branch', 'self', 'direct'):
```
| emi_collected_by_agent | emi_status |
| John Smith | verified |
```
**Result**: Agent collection

#### **2. Payment Mode Analysis**
Payment modes suggesting branch collection:
- `branch`, `direct`, `office`, `cash_counter`

```
| emi_payment_mode | emi_status |
| Branch Counter | verified |
```
**Result**: Branch collection

#### **3. Payment Reference Analysis**
References suggesting branch collection:
- `br`, `branch`, `office`, `counter`

```
| emi_payment_reference | emi_status |
| BR-001 | verified |
```
**Result**: Branch collection

#### **4. Remarks Analysis**
Remarks suggesting branch collection:
- `branch`, `office`, `direct`, `counter`

```
| emi_collection_remarks | emi_status |
| Collected at branch office | verified |
```
**Result**: Branch collection

#### **5. Default Logic**
- If loan has assigned agent: **Agent collection**
- If no agent assigned: **Branch collection**

### Processing Differences

#### **Agent Collections:**
- Creates `EmiCollectionDetail` with `collected_by_agent`
- Uses agent-specific verification process
- Creates branch transactions with agent reference
- Remarks: "Agent Collection" or custom + " (Agent Collection)"

#### **Branch Collections:**
- Creates `EmiCollectionDetail` with `collected_by_agent = None`
- Uses branch-specific verification process
- Creates branch transactions without agent reference
- Remarks: "Branch Collection" or custom + " (Branch Collection)"

### Usage Examples

#### **Agent Collection (Explicit):**
```
| emi_collected_amount | emi_principal_received | emi_interest_received | emi_status | emi_collected_by_agent |
| 5000.00 | 4000.00 | 1000.00 | verified | John Smith |
```
**Result**: Agent collection with agent assignment

#### **Branch Collection (Payment Mode):**
```
| emi_collected_amount | emi_principal_received | emi_interest_received | emi_status | emi_payment_mode |
| 5000.00 | 4000.00 | 1000.00 | verified | Branch Counter |
```
**Result**: Branch collection, no agent assignment

#### **Branch Collection (Reference):**
```
| emi_collected_amount | emi_principal_received | emi_interest_received | emi_status | emi_payment_reference |
| 5000.00 | 4000.00 | 1000.00 | verified | BR-001 |
```
**Result**: Branch collection, no agent assignment

#### **Default Agent Collection:**
```
| emi_collected_amount | emi_principal_received | emi_interest_received | emi_status |
| 5000.00 | 4000.00 | 1000.00 | verified |
```
**Result**: Agent collection (loan has assigned agent)

### Benefits

#### **Automatic Processing:**
- No manual configuration required
- Intelligent detection based on multiple indicators
- Fallback to loan assignment logic

#### **Data Integrity:**
- Proper agent/branch assignment
- Correct transaction references
- Appropriate verification processes

#### **Audit Trail:**
- Clear collection type identification
- Proper remarks for tracking
- Consistent data structure

## Enhanced EMI Collection Features

### Automatic EMI ID Linking
The system automatically links EMI collections to the first unpaid EMI schedule:

#### **Automatic EMI Detection:**
```
| emi_collected_amount | emi_status |
| 5000.00 | verified |
```
**Result**: Collection automatically linked to first unpaid EMI schedule

#### **EMI ID Benefits:**
- No manual EMI ID specification required
- Automatic schedule-to-collection linking
- Proper payment application sequence

### Automatic Verification Tracking
The system automatically assigns verification to the branch manager:

#### **Automatic Verification Assignment:**
```
| emi_collected_amount | emi_status |
| 5000.00 | verified |
```
**Result**: Collection automatically verified by branch manager

#### **Verification Benefits:**
- Automatic `verified_at` timestamp
- Proper audit trail with branch manager responsibility
- No manual employee ID specification required

### Multiple EMI Payments
Process multiple EMI payments in a single row like the "ready" button:

#### **Multiple EMI Processing:**
```
| emi_collected_amount | emi_status | multiple_emi_count |
| 15000.00 | verified | 3 |
```
**Result**: Creates 3 EMI collection records (5000.00 each)

#### **Amount Distribution:**
- Total amount distributed equally among EMIs
- Individual EMI tracking with remarks
- Sequential EMI schedule processing

#### **Multiple EMI Benefits:**
- Bulk payment processing
- Reduced data entry
- Consistent payment application

### Agent Deposit Integration
Automatic AgentDeposit and AgentDepositDenomination creation for agent collections:

#### **Agent Deposit Creation:**
```
| emi_collected_amount | emi_status | emi_collected_by_agent | online_amount |
| 5000.00 | verified | John Smith | 0 |
```
**Result**: 
- EMI collection with agent tracking
- AgentDeposit record created
- AgentDepositDenomination records automatically calculated (500x10, 200x0, 100x0, 50x0, 20x0, 10x0, 5x0, 2x0, 1x0)

#### **Deposit Features:**
- Automatic category assignment (daily/weekly/others)
- **Automatic denomination calculation** based on amount
- Cash and coin tracking (coins default to 0)
- Online payment support

#### **Automatic Denomination Calculation:**
- **Optimal breakdown**: System calculates best denomination mix
- **No manual input required**: Denominations calculated automatically
- **Standard denominations**: 500, 200, 100, 50, 20, 10, 5, 2, 1
- **Coin handling**: Coins default to 0 (configurable)
- **online_amount**: Online deposited amount (optional, default: 0)

### Advanced Usage Examples

#### **Complete Agent Collection with Deposit:**
```
| emi_collected_amount | emi_principal_received | emi_interest_received | emi_status | emi_collected_by_agent | online_amount |
| 5000.00 | 4000.00 | 1000.00 | verified | John Smith | 0 |
```
**Result**: 
- EMI collection automatically linked to first unpaid EMI
- Automatically verified by branch manager
- Agent deposit with automatic denomination breakdown (500x10)
- Branch transaction created
- Account balance updated

#### **Multiple EMI Processing:**
```
| emi_collected_amount | emi_status | multiple_emi_count | emi_collected_by_agent |
| 15000.00 | verified | 3 | John Smith |
```
**Result**: 
- 3 EMI collections created (5000.00 each)
- Each automatically linked to sequential EMI schedules
- Agent deposit with automatic denominations (500x30 total)
- 3 branch transactions created

#### **Branch Collection:**
```
| emi_collected_amount | emi_status | emi_payment_mode |
| 5000.00 | verified | Branch Counter |
```
**Result**: 
- Branch collection (no agent deposit)
- EMI automatically linked to first unpaid EMI schedule
- Automatically verified by branch manager
- Branch transaction created

### Important Notes
- EMI receive process only activates when `emi_status` = `verified`
- Collection type detection is automatic and requires no manual intervention
- Branch transactions use the same COA codes as manual receive
- Cash account balances are automatically updated
- All financial integration follows the same business rules as the EMI schedule interface
- Collection type is automatically determined and processed accordingly
- Agent deposits are created automatically for verified agent collections
- Multiple EMI processing distributes amounts equally among specified EMIs
- EMI ID linking ensures precise collection-to-schedule relationships

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
