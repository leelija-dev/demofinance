"""
Forms for data_import module
"""
from django import forms
from django.core.exceptions import ValidationError

class ExcelUploadForm(forms.Form):
    """Form for Excel file upload"""
    excel_file = forms.FileField(
        label='Select Excel File',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx,.xls'
        }),
        help_text='Supported formats: .xlsx, .xls'
    )
    
    def clean_excel_file(self):
        """Validate uploaded file"""
        file = self.cleaned_data.get('excel_file')
        
        if not file:
            raise ValidationError('Please select an Excel file to upload.')
        
        # Check file extension
        if not file.name.lower().endswith(('.xlsx', '.xls')):
            raise ValidationError('Please upload a valid Excel file (.xlsx or .xls).')
        
        # Check file size (max 10MB)
        if file.size > 10 * 1024 * 1024:
            raise ValidationError('File size must be less than 10MB.')
        
        return file

class ImportOptionsForm(forms.Form):
    """Form for import options and settings"""
    skip_duplicates = forms.BooleanField(
        required=False,
        initial=True,
        help_text='Skip rows with duplicate Aadhar numbers'
    )
    
    update_existing = forms.BooleanField(
        required=False,
        initial=False,
        help_text='Update existing customer records instead of creating new ones'
    )
    
    validate_references = forms.BooleanField(
        required=False,
        initial=True,
        help_text='Validate all reference data (branches, agents, categories)'
    )
    
    batch_size = forms.IntegerField(
        required=False,
        initial=100,
        min_value=1,
        max_value=1000,
        help_text='Number of records to process in each batch'
    )
    
    continue_on_error = forms.BooleanField(
        required=False,
        initial=True,
        help_text='Continue processing even if some records fail'
    )
