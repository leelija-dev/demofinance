"""
Utility functions for data_import module
"""
import pandas as pd
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
import logging

logger = logging.getLogger(__name__)

def clean_nan_values(data_dict):
    """Clean NaN values from dictionary, converting to None"""
    return {k: (v if pd.notna(v) else None) for k, v in data_dict.items()}

def validate_email_address(email):
    """Validate email address format"""
    if not email:
        return True
    try:
        validate_email(email)
        return True
    except ValidationError:
        return False

def validate_phone_number(phone):
    """Validate phone number (10 digits)"""
    if not phone:
        return True
    phone_str = str(phone)
    return phone_str.isdigit() and len(phone_str) == 10

def validate_aadhar_number(aadhar):
    """Validate Aadhar number (12 digits)"""
    if not aadhar:
        return True
    aadhar_str = str(aadhar)
    return aadhar_str.isdigit() and len(aadhar_str) == 12

def validate_date_format(date_str):
    """Validate date string format (YYYY-MM-DD)"""
    if not date_str:
        return True
    try:
        pd.to_datetime(date_str).date()
        return True
    except:
        return False

def validate_decimal_field(value):
    """Validate decimal field"""
    if not value:
        return True
    try:
        Decimal(str(value))
        return True
    except (InvalidOperation, ValueError):
        return False

def validate_row_data(row_data):
    """Comprehensive row data validation"""
    errors = []
    
    # Validate date of birth
    if row_data.get('date_of_birth'):
        if not validate_date_format(row_data['date_of_birth']):
            errors.append("Invalid date_of_birth format. Use YYYY-MM-DD")
    
    # Validate email if provided
    if row_data.get('email') and not validate_email_address(row_data['email']):
        errors.append("Invalid email format")
    
    # Validate phone number
    if not validate_phone_number(row_data.get('contact')):
        errors.append("Contact must be a valid 10-digit phone number")
    
    # Validate Aadhar number
    if not validate_aadhar_number(row_data.get('adhar_number')):
        errors.append("Aadhar number must be 12 digits")
    
    # Validate monetary values
    monetary_fields = ['loan_amount', 'emi_amount', 'interest_rate']
    for field in monetary_fields:
        if row_data.get(field) and not validate_decimal_field(row_data[field]):
            errors.append(f"Invalid {field} format. Use decimal numbers")
    
    # Validate tenure
    if row_data.get('tenure_value'):
        try:
            int(row_data['tenure_value'])
        except (ValueError, TypeError):
            errors.append("Tenure value must be a whole number")
    
    return errors

def get_safe_string(value):
    """Safely convert value to string, handling None/NaN"""
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()

def get_safe_decimal(value, default=Decimal('0.00')):
    """Safely convert value to decimal"""
    if value is None or pd.isna(value):
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        logger.warning(f"Could not convert {value} to decimal, using default {default}")
        return default

def get_safe_integer(value, default=0):
    """Safely convert value to integer"""
    if value is None or pd.isna(value):
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(f"Could not convert {value} to integer, using default {default}")
        return default

def get_safe_date(value):
    """Safely convert value to date"""
    if value is None or pd.isna(value):
        return None
    try:
        return pd.to_datetime(value).date()
    except:
        logger.warning(f"Could not convert {value} to date")
        return None

def generate_import_summary(successful_imports, failed_imports, error_details):
    """Generate import summary for reporting"""
    total_records = successful_imports + failed_imports
    success_rate = (successful_imports / total_records * 100) if total_records > 0 else 0
    
    return {
        'total_records': total_records,
        'successful_imports': successful_imports,
        'failed_imports': failed_imports,
        'success_rate': round(success_rate, 2),
        'error_count': len(error_details),
        'error_details': error_details[:10],  # Limit to first 10 errors
        'has_more_errors': len(error_details) > 10
    }

def log_import_start(file_name, total_rows):
    """Log the start of import process"""
    logger.info(f"Starting import process for file: {file_name} with {total_rows} rows")

def log_import_end(summary):
    """Log the end of import process"""
    logger.info(f"Import completed: {summary['successful_imports']} successful, "
                f"{summary['failed_imports']} failed, {summary['success_rate']}% success rate")

def log_row_error(row_number, errors):
    """Log row-specific errors"""
    for error in errors:
        logger.error(f"Row {row_number}: {error}")
