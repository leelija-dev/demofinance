"""
Tests for data_import module
"""
import unittest
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.messages import get_messages
from unittest.mock import patch, MagicMock
import pandas as pd
from decimal import Decimal

from data_import.views import validate_required_columns, validate_data_types, process_customer_loan_data
from data_import.utils import clean_nan_values, validate_row_data, generate_import_summary
from loan.models import LoanCategory, LoanInterest, LoanTenure
from headquater.models import Branch
from agent.models import Agent

class ImportValidationTests(TestCase):
    """Test validation functions"""
    
    def setUp(self):
        """Set up test data"""
        self.valid_row = {
            'customer_type': 'NEW',
            'full_name': 'Test Customer',
            'date_of_birth': '1990-01-01',
            'gender': 'Male',
            'contact': '9876543210',
            'adhar_number': '123456789012',
            'address_line_1': '123 Test St',
            'city_or_town': 'Test City',
            'district': 'Test District',
            'state': 'Test State',
            'post_code': '123456',
            'current_address_line_1': '123 Test St',
            'current_city_or_town': 'Test City',
            'current_district': 'Test District',
            'current_state': 'Test State',
            'current_post_code': '123456',
            'account_number': '1234567890',
            'bank_name': 'Test Bank',
            'ifsc_code': 'TEST0001234',
            'account_type': 'savings',
            'loan_category_name': 'Personal Loan',
            'loan_amount': '10000',
            'tenure_value': '12',
            'tenure_unit': 'months',
            'loan_purpose': 'Test Purpose',
            'interest_rate': '12.5',
            'emi_amount': '1000',
            'branch_name': 'Test Branch'
        }
    
    def test_validate_required_columns_valid(self):
        """Test validation with all required columns"""
        df = pd.DataFrame([self.valid_row])
        missing = validate_required_columns(df)
        self.assertEqual(len(missing), 0)
    
    def test_validate_required_columns_missing(self):
        """Test validation with missing columns"""
        invalid_row = self.valid_row.copy()
        del invalid_row['full_name']
        df = pd.DataFrame([invalid_row])
        missing = validate_required_columns(df)
        self.assertIn('full_name', missing)
    
    def test_validate_data_types_valid(self):
        """Test data type validation with valid data"""
        errors = validate_data_types(self.valid_row)
        self.assertEqual(len(errors), 0)
    
    def test_validate_data_types_invalid_email(self):
        """Test invalid email validation"""
        invalid_row = self.valid_row.copy()
        invalid_row['email'] = 'invalid-email'
        errors = validate_data_types(invalid_row)
        self.assertIn("Invalid email format", errors)
    
    def test_validate_data_types_invalid_phone(self):
        """Test invalid phone validation"""
        invalid_row = self.valid_row.copy()
        invalid_row['contact'] = '123'
        errors = validate_data_types(invalid_row)
        self.assertIn("Contact must be a valid 10-digit phone number", errors)
    
    def test_validate_data_types_invalid_aadhar(self):
        """Test invalid Aadhar validation"""
        invalid_row = self.valid_row.copy()
        invalid_row['adhar_number'] = '123'
        errors = validate_data_types(invalid_row)
        self.assertIn("Aadhar number must be 12 digits", errors)
    
    def test_clean_nan_values(self):
        """Test NaN value cleaning"""
        import numpy as np
        data_with_nan = {
            'name': 'Test',
            'email': np.nan,
            'phone': '1234567890'
        }
        cleaned = clean_nan_values(data_with_nan)
        self.assertEqual(cleaned['email'], None)
        self.assertEqual(cleaned['name'], 'Test')
        self.assertEqual(cleaned['phone'], '1234567890')
    
    def test_validate_row_data(self):
        """Test comprehensive row validation"""
        errors = validate_row_data(self.valid_row)
        self.assertEqual(len(errors), 0)
    
    def test_generate_import_summary(self):
        """Test import summary generation"""
        summary = generate_import_summary(80, 20, ['Error 1', 'Error 2'])
        self.assertEqual(summary['total_records'], 100)
        self.assertEqual(summary['successful_imports'], 80)
        self.assertEqual(summary['failed_imports'], 20)
        self.assertEqual(summary['success_rate'], 80.0)
        self.assertEqual(summary['error_count'], 2)

class ImportProcessTests(TestCase):
    """Test import processing functions"""
    
    def setUp(self):
        """Set up test environment"""
        self.client = Client()
        
        # Create test branch
        self.branch = Branch.objects.create(
            branch_name='Test Branch',
            branch_code='TB001',
            branch_address='Test Address',
            branch_city='Test City',
            branch_state='Test State'
        )
        
        # Create test agent
        self.agent = Agent.objects.create(
            full_name='Test Agent',
            email='agent@test.com',
            phone='9876543210',
            branch=self.branch
        )
        
        # Create test loan category
        self.loan_category = LoanCategory.objects.create(
            name='Personal Loan',
            main_category='Personal'
        )
        
        # Create test loan interest
        self.loan_interest = LoanInterest.objects.create(
            main_category=self.loan_category.main_category,
            rate_of_interest=12.5
        )
        
        # Create test loan tenure
        self.loan_tenure = LoanTenure.objects.create(
            interest_rate=self.loan_interest,
            value=12,
            unit='months'
        )
    
    def test_upload_excel_get(self):
        """Test GET request to upload page"""
        response = self.client.get('/data_import/upload-excel/')
        self.assertEqual(response.status_code, 200)
    
    def test_upload_excel_post_valid(self):
        """Test POST request with valid Excel file"""
        # Create test Excel file
        df = pd.DataFrame([{
            'customer_type': 'NEW',
            'full_name': 'Test Customer',
            'date_of_birth': '1990-01-01',
            'gender': 'Male',
            'contact': '9876543210',
            'adhar_number': '123456789012',
            'address_line_1': '123 Test St',
            'city_or_town': 'Test City',
            'district': 'Test District',
            'state': 'Test State',
            'post_code': '123456',
            'current_address_line_1': '123 Test St',
            'current_city_or_town': 'Test City',
            'current_district': 'Test District',
            'current_state': 'Test State',
            'current_post_code': '123456',
            'account_number': '1234567890',
            'bank_name': 'Test Bank',
            'ifsc_code': 'TEST0001234',
            'account_type': 'savings',
            'loan_category_name': 'Personal Loan',
            'loan_amount': '10000',
            'tenure_value': '12',
            'tenure_unit': 'months',
            'loan_purpose': 'Test Purpose',
            'interest_rate': '12.5',
            'emi_amount': '1000',
            'branch_name': 'Test Branch'
        }])
        
        # Convert to bytes for upload
        excel_content = df.to_excel(index=False)
        uploaded_file = SimpleUploadedFile(
            "test.xlsx",
            excel_content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        response = self.client.post('/data_import/upload-excel/', {
            'excel_file': uploaded_file
        })
        
        self.assertEqual(response.status_code, 200)
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('Successfully uploaded' in str(message) for message in messages))
    
    def test_upload_excel_post_invalid_file(self):
        """Test POST request with invalid file"""
        uploaded_file = SimpleUploadedFile(
            "test.txt",
            b"not an excel file",
            content_type="text/plain"
        )
        
        response = self.client.post('/data_import/upload-excel/', {
            'excel_file': uploaded_file
        })
        
        self.assertEqual(response.status_code, 200)
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('valid Excel file' in str(message) for message in messages))
    
    def test_process_customer_loan_data_valid(self):
        """Test processing valid customer loan data"""
        mock_request = MagicMock()
        mock_request.session = {}
        
        loan_application, errors = process_customer_loan_data(self.valid_row, mock_request)
        
        self.assertIsNotNone(loan_application)
        self.assertEqual(len(errors), 0)
    
    def test_process_customer_loan_data_invalid_branch(self):
        """Test processing with invalid branch"""
        invalid_row = self.valid_row.copy()
        invalid_row['branch_name'] = 'Non-existent Branch'
        
        mock_request = MagicMock()
        mock_request.session = {}
        
        loan_application, errors = process_customer_loan_data(invalid_row, mock_request)
        
        self.assertIsNone(loan_application)
        self.assertIn("Branch 'Non-existent Branch' not found", errors)

class ImportAPITests(TestCase):
    """Test import API endpoints"""
    
    def setUp(self):
        """Set up test environment"""
        self.client = Client()
        
        # Create test data
        self.branch = Branch.objects.create(
            branch_name='Test Branch',
            branch_code='TB001'
        )
        
        # Set up session data
        session = self.client.session
        session['excel_data'] = [{
            'customer_type': 'NEW',
            'full_name': 'Test Customer',
            'date_of_birth': '1990-01-01',
            'gender': 'Male',
            'contact': '9876543210',
            'adhar_number': '123456789012',
            'address_line_1': '123 Test St',
            'city_or_town': 'Test City',
            'district': 'Test District',
            'state': 'Test State',
            'post_code': '123456',
            'current_address_line_1': '123 Test St',
            'current_city_or_town': 'Test City',
            'current_district': 'Test District',
            'current_state': 'Test State',
            'current_post_code': '123456',
            'account_number': '1234567890',
            'bank_name': 'Test Bank',
            'ifsc_code': 'TEST0001234',
            'account_type': 'savings',
            'loan_category_name': 'Personal Loan',
            'loan_amount': '10000',
            'tenure_value': '12',
            'tenure_unit': 'months',
            'loan_purpose': 'Test Purpose',
            'interest_rate': '12.5',
            'emi_amount': '1000',
            'branch_name': 'Test Branch'
        }]
        session.save()
    
    def test_process_excel_data_api_success(self):
        """Test successful API processing"""
        response = self.client.post('/data_import/process-data/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('successful_imports', data)
        self.assertIn('failed_imports', data)
    
    def test_process_excel_data_api_no_data(self):
        """Test API processing without data"""
        # Clear session
        session = self.client.session
        session.pop('excel_data', None)
        session.save()
        
        response = self.client.post('/data_import/process-data/')
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('No data to process', data['message'])

if __name__ == '__main__':
    unittest.main()
