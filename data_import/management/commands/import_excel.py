"""
Django management command to import Excel data from command line
"""
from django.core.management.base import BaseCommand
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
import pandas as pd
import os
import json

from data_import.views import process_customer_loan_data
from data_import.utils import log_import_start, log_import_end, generate_import_summary

class Command(BaseCommand):
    help = 'Import customer and loan data from Excel file via command line'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'file_path',
            type=str,
            help='Path to the Excel file to import'
        )
        parser.add_argument(
            '--skip-duplicates',
            action='store_true',
            help='Skip rows with duplicate Aadhar numbers'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing customer records instead of creating new ones'
        )
        parser.add_argument(
            '--no-validate-references',
            action='store_true',
            help='Skip validation of reference data'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of records to process in each batch'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate data without actually importing'
        )
        parser.add_argument(
            '--output-json',
            type=str,
            help='Output results to JSON file'
        )
    
    def handle(self, *args, **options):
        file_path = options['file_path']
        
        if not os.path.exists(file_path):
            self.stdout.write(
                self.style.ERROR(f"File not found: {file_path}")
            )
            return
        
        try:
            # Read Excel file
            df = pd.read_excel(file_path)
            
            if df.empty:
                self.stdout.write(
                    self.style.ERROR("The Excel file is empty.")
                )
                return
            
            self.stdout.write(
                self.style.SUCCESS(f"Loaded {len(df)} rows from {file_path}")
            )
            
            # Process data
            successful_imports = 0
            failed_imports = 0
            error_details = []
            
            log_import_start(file_path, len(df))
            
            for index, row_data in enumerate(df.to_dict('records'), 1):
                try:
                    # Create mock request for processing
                    factory = RequestFactory()
                    request = factory.post('/')
                    request.session = {}
                    
                    # Process row
                    loan_application, errors = process_customer_loan_data(row_data, request)
                    
                    if loan_application:
                        if not options['dry_run']:
                            successful_imports += 1
                        else:
                            self.stdout.write(
                                self.style.SUCCESS(f"Row {index}: Would import successfully")
                            )
                    else:
                        failed_imports += 1
                        error_msg = f"Row {index}: {'; '.join(errors)}"
                        error_details.append(error_msg)
                        self.stdout.write(
                            self.style.ERROR(error_msg)
                        )
                        
                except Exception as e:
                    failed_imports += 1
                    error_msg = f"Row {index}: Unexpected error - {str(e)}"
                    error_details.append(error_msg)
                    self.stdout.write(
                        self.style.ERROR(error_msg)
                    )
            
            # Generate summary
            summary = generate_import_summary(successful_imports, failed_imports, error_details)
            log_import_end(summary)
            
            # Output results
            self.stdout.write("\n" + "="*50)
            self.stdout.write("IMPORT SUMMARY")
            self.stdout.write("="*50)
            self.stdout.write(f"Total Records: {summary['total_records']}")
            self.stdout.write(
                self.style.SUCCESS(f"Successful Imports: {summary['successful_imports']}")
            )
            self.stdout.write(
                self.style.ERROR(f"Failed Imports: {summary['failed_imports']}")
            )
            self.stdout.write(f"Success Rate: {summary['success_rate']}%")
            
            if summary['error_count'] > 0:
                self.stdout.write(f"\nFirst 10 errors:")
                for error in summary['error_details']:
                    self.stdout.write(self.style.ERROR(f"  - {error}"))
                
                if summary['has_more_errors']:
                    self.stdout.write(
                        self.style.WARNING(f"  ... and {summary['error_count'] - 10} more errors")
                    )
            
            # Save to JSON if requested
            if options.get('output_json'):
                with open(options['output_json'], 'w') as f:
                    json.dump(summary, f, indent=2, default=str)
                self.stdout.write(
                    self.style.SUCCESS(f"\nResults saved to {options['output_json']}")
                )
            
            if options['dry_run']:
                self.stdout.write(
                    self.style.WARNING("\nDRY RUN COMPLETED - No data was actually imported")
                )
            else:
                if summary['failed_imports'] == 0:
                    self.stdout.write(
                        self.style.SUCCESS("\nIMPORT COMPLETED SUCCESSFULLY")
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"\nIMPORT COMPLETED WITH {summary['failed_imports']} ERRORS")
                    )
                    
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error processing file: {str(e)}")
            )
